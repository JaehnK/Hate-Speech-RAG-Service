from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
import time
from typing import Any, Callable

import httpx

from app.analysis.prompt_template import PROMPT_VERSION
from app.analysis.rag_classifier import DEFAULT_EXAMPLE_MIN_SIMILARITY
from app.core.config import load_settings


TERMINAL_STATUSES = {"succeeded", "partial_success", "failed"}


@dataclass(frozen=True)
class CaseEvidence:
    case: str
    video_id: str
    job_id: str
    job_status: str
    report_id: str
    step_statuses: dict[str, str]
    source_counts: dict[str, int]
    export_bytes: dict[str, int]
    elapsed_seconds: float


class LiveValidationError(RuntimeError):
    pass


class LiveE2eRunner:
    def __init__(
        self,
        base_url: str,
        admin_token: str,
        timeout_seconds: int = 3600,
        poll_seconds: float = 3,
        client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.admin_token = admin_token
        self.timeout_seconds = timeout_seconds
        self.poll_seconds = poll_seconds
        self.client = client or httpx.Client(timeout=60)
        self.sleep = sleep
        self.response_bodies: list[str] = []

    def run_case(self, case: str, video_id: str) -> CaseEvidence:
        started = time.monotonic()
        created = self._json("POST", "/api/analysis-jobs", json={"input_value": video_id}, expected=202)
        job = self._wait_for_job(created["status_url"])
        self._validate_job(case, job)
        report_url = job["links"].get("report_api")
        if not report_url:
            raise LiveValidationError(f"{case}: report link is missing")
        report = self._json("GET", report_url)
        report_id = str(report["report_id"])
        self._validate_report(case, report)
        self._json("GET", f"/api/reports/{report_id}/comments")
        self._json("GET", f"/api/reports/{report_id}/script-segments")
        self._json("GET", f"/api/reports/{report_id}/network")
        export_bytes = {
            format: self._create_export(report_id, format)
            for format in ("html", "xlsx")
        }
        counts = report.get("source_counts") or {
            "comments": int(report.get("collection_summary", {}).get("comments_collected", 0))
            + int(report.get("collection_summary", {}).get("replies_collected", 0)),
            "script_segments": int(report.get("script_analysis_summary", {}).get("total", 0)),
        }
        return CaseEvidence(
            case=case,
            video_id=video_id,
            job_id=str(job["job_id"]),
            job_status=str(job["status"]),
            report_id=report_id,
            step_statuses={step["step_key"]: step["status"] for step in job["steps"]},
            source_counts={key: int(value) for key, value in counts.items()},
            export_bytes=export_bytes,
            elapsed_seconds=round(time.monotonic() - started, 3),
        )

    def validate_admin_surface(self) -> dict[str, Any]:
        headers = {"X-Admin-Token": self.admin_token}
        settings = self._json("GET", "/api/admin/settings", headers=headers)
        jobs = self._json("GET", "/api/admin/jobs", headers=headers)
        self._json("GET", "/api/admin/logs", headers=headers)
        self._json("GET", "/api/admin/quota-events", headers=headers)
        return {
            "youtube_api_key_configured": bool(settings["youtube_api_key"]["is_configured"]),
            "llm_api_key_configured": bool(settings["llm"]["api_key_configured"]),
            "embedding_api_key_configured": bool(settings["embedding"]["api_key_configured"]),
            "job_count_observed": len(jobs.get("items", [])),
        }

    def assert_secrets_absent(self, secrets: list[str]) -> None:
        combined = "\n".join(self.response_bodies)
        leaked = [name for name, value in _named_secrets(secrets) if value and value in combined]
        if leaked:
            raise LiveValidationError(f"secret values found in API responses: {', '.join(leaked)}")

    def _wait_for_job(self, status_url: str) -> dict[str, Any]:
        deadline = time.monotonic() + self.timeout_seconds
        while time.monotonic() < deadline:
            payload = self._json("GET", status_url)
            if payload["status"] in TERMINAL_STATUSES:
                return payload
            self.sleep(self.poll_seconds)
        raise LiveValidationError(f"job did not finish within {self.timeout_seconds} seconds")

    def _create_export(self, report_id: str, format: str) -> int:
        export = self._json(
            "POST",
            f"/api/reports/{report_id}/exports",
            json={"format": format},
            expected=202,
        )
        status = self._json("GET", export["status_url"])
        if status["status"] != "succeeded" or not status.get("download_url"):
            raise LiveValidationError(f"{format} export failed: {status}")
        response = self._request("GET", status["download_url"])
        if not response.content:
            raise LiveValidationError(f"{format} export is empty")
        return len(response.content)

    def _validate_job(self, case: str, job: dict[str, Any]) -> None:
        steps = {step["step_key"]: step for step in job["steps"]}
        if not job.get("finished_at") or job.get("progress", {}).get("percent") != 100:
            raise LiveValidationError(f"{case}: terminal job is not fully finalized")
        if case == "normal":
            if job["status"] != "succeeded":
                raise LiveValidationError(f"normal: expected succeeded, got {job['status']}")
            required = ("collect_metadata", "collect_comments", "collect_transcript", "analyze_comments", "analyze_script", "build_report_snapshot")
            failed = [key for key in required if steps.get(key, {}).get("status") != "succeeded"]
            if failed:
                raise LiveValidationError(f"normal: steps not succeeded: {failed}")
        elif case == "comments_disabled":
            _expect_partial(job, steps, "collect_comments", "COMMENTS_DISABLED")
            if steps.get("analyze_comments", {}).get("status") != "skipped":
                raise LiveValidationError("comments_disabled: analyze_comments must be skipped")
        elif case == "no_caption":
            _expect_partial(job, steps, "collect_transcript", "CAPTION_NOT_AVAILABLE")
            if steps.get("analyze_script", {}).get("status") != "skipped":
                raise LiveValidationError("no_caption: analyze_script must be skipped")
        else:
            raise LiveValidationError(f"unsupported case: {case}")

    def _validate_report(self, case: str, report: dict[str, Any]) -> None:
        if case == "normal" and report["status"] != "succeeded":
            raise LiveValidationError(f"normal: report status is {report['status']}")
        if case != "normal" and report["status"] != "partial_success":
            raise LiveValidationError(f"{case}: report must expose partial_success")
        if not report.get("video") or not report.get("analysis_config"):
            raise LiveValidationError(f"{case}: report is missing video or analysis config")
        analysis_config = report["analysis_config"]
        prompt_versions = analysis_config.get("prompt_versions", {})
        if prompt_versions.get("comment") != PROMPT_VERSION or prompt_versions.get("script") != PROMPT_VERSION:
            raise LiveValidationError(f"{case}: report prompt version is stale")
        retriever_config = analysis_config.get("retriever_config", {})
        if retriever_config.get("example_min_similarity") != DEFAULT_EXAMPLE_MIN_SIMILARITY:
            raise LiveValidationError(f"{case}: report retriever threshold is stale")
        collection = report.get("collection_summary", {})
        collected_comments = int(collection.get("comments_collected", 0)) + int(collection.get("replies_collected", 0))
        analyzed_comments = int(report.get("comment_analysis_summary", {}).get("total", 0))
        script_total = int(report.get("script_analysis_summary", {}).get("total", 0))
        if analyzed_comments != collected_comments:
            raise LiveValidationError(f"{case}: comment snapshot/analysis count mismatch: {collected_comments} != {analyzed_comments}")
        if bool(collection.get("transcript_available")) != bool(script_total):
            raise LiveValidationError(f"{case}: transcript availability/analysis count mismatch")
        if case == "normal" and (analyzed_comments == 0 or script_total == 0):
            raise LiveValidationError("normal: comments and script must both be analyzed")
        if case == "comments_disabled" and analyzed_comments != 0:
            raise LiveValidationError("comments_disabled: comment analysis must be empty")
        if case == "no_caption" and script_total != 0:
            raise LiveValidationError("no_caption: script analysis must be empty")

    def _json(self, method: str, path: str, expected: int = 200, **kwargs) -> dict[str, Any]:
        response = self._request(method, path, **kwargs)
        if response.status_code != expected:
            raise LiveValidationError(f"{method} {path}: expected {expected}, got {response.status_code}: {response.text[:500]}")
        try:
            return response.json()
        except ValueError as exc:
            raise LiveValidationError(f"{method} {path}: invalid JSON response") from exc

    def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        url = path if path.startswith("http") else f"{self.base_url}{path}"
        response = self.client.request(method, url, **kwargs)
        self.response_bodies.append(response.text if response.headers.get("content-type", "").startswith("application/json") else "")
        return response


def _expect_partial(job: dict[str, Any], steps: dict[str, dict[str, Any]], step_key: str, error_code: str) -> None:
    if job["status"] != "partial_success":
        raise LiveValidationError(f"{step_key}: expected partial_success, got {job['status']}")
    step = steps.get(step_key, {})
    actual_error = (step.get("error") or {}).get("code")
    if step.get("status") not in {"skipped", "failed"} or actual_error != error_code:
        raise LiveValidationError(f"{step_key}: expected {error_code}, got {step}")


def _named_secrets(values: list[str]) -> list[tuple[str, str]]:
    names = ("admin_token", "youtube_api_key", "anthropic_api_key", "upstage_api_key")
    return list(zip(names, values, strict=True))


def main() -> None:
    parser = argparse.ArgumentParser(description="Run live predeploy E2E validation against a running service.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--normal-video", required=True)
    parser.add_argument("--comments-disabled-video", required=True)
    parser.add_argument("--no-caption-video", required=True)
    parser.add_argument("--timeout-seconds", type=int, default=3600)
    parser.add_argument("--evidence-path", default="experiments/outputs/live_e2e_evidence.json")
    args = parser.parse_args()

    settings = load_settings()
    admin_token = settings.admin_token
    if not admin_token or admin_token == "change-me":
        raise SystemExit("A non-default ADMIN_TOKEN is required")
    runner = LiveE2eRunner(args.base_url, admin_token, timeout_seconds=args.timeout_seconds)
    evidence = [
        runner.run_case("normal", args.normal_video),
        runner.run_case("comments_disabled", args.comments_disabled_video),
        runner.run_case("no_caption", args.no_caption_video),
    ]
    admin = runner.validate_admin_surface()
    secrets = [
        admin_token,
        settings.youtube_api_key or "",
        settings.llm_api_key or "",
        settings.embedding_api_key or "",
    ]
    runner.assert_secrets_absent(secrets)
    output = {
        "validated_at": datetime.now(UTC).isoformat(),
        "base_url": args.base_url,
        "cases": [asdict(item) for item in evidence],
        "admin": admin,
        "secret_scan": "passed",
        "raw_content_included": False,
    }
    path = Path(args.evidence_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    main()
