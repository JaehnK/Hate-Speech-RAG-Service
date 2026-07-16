import json

import httpx
import pytest

from scripts.live_e2e import LiveE2eRunner, LiveValidationError


VIDEO_CASES = {
    "normal-video": "normal",
    "comments-disabled-video": "comments_disabled",
    "no-caption-video": "no_caption",
}


def test_live_runner_validates_three_cases_exports_admin_and_secret_scan() -> None:
    client = httpx.Client(transport=httpx.MockTransport(_handler))
    runner = LiveE2eRunner("http://test", "admin-secret", client=client, sleep=lambda _seconds: None)

    evidence = [runner.run_case(case, video) for video, case in VIDEO_CASES.items()]
    admin = runner.validate_admin_surface()
    runner.assert_secrets_absent(["admin-secret", "youtube-secret", "llm-secret", "embedding-secret"])

    assert [item.job_status for item in evidence] == ["succeeded", "partial_success", "partial_success"]
    assert all(item.export_bytes == {"html": 4, "xlsx": 4} for item in evidence)
    assert admin["youtube_api_key_configured"]
    assert admin["llm_api_key_configured"]
    assert admin["embedding_api_key_configured"]


def test_live_runner_rejects_wrong_partial_failure_contract() -> None:
    runner = LiveE2eRunner("http://test", "admin-secret", client=httpx.Client(transport=httpx.MockTransport(_handler)))
    job = _job("normal")
    job["status"] = "partial_success"

    with pytest.raises(LiveValidationError):
        runner._validate_job("comments_disabled", job)


def _handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if request.method == "POST" and path == "/api/analysis-jobs":
        case = VIDEO_CASES[json.loads(request.content)["input_value"]]
        return httpx.Response(202, json={"job_id": case, "status_url": f"/api/analysis-jobs/{case}"})
    if request.method == "GET" and path.startswith("/api/analysis-jobs/"):
        return httpx.Response(200, json=_job(path.rsplit("/", 1)[-1]))
    if request.method == "GET" and path.startswith("/api/reports/") and path.count("/") == 3:
        case = path.rsplit("/", 1)[-1]
        return httpx.Response(200, json=_report(case))
    if request.method == "GET" and path.endswith(("/comments", "/script-segments", "/network")):
        return httpx.Response(200, json={"items": []})
    if request.method == "POST" and path.endswith("/exports"):
        case = path.split("/")[3]
        format = json.loads(request.content)["format"]
        export_id = f"{case}-{format}"
        return httpx.Response(202, json={"status": "succeeded", "status_url": f"/api/exports/{export_id}"})
    if request.method == "GET" and path.startswith("/api/exports/") and not path.endswith("/download"):
        export_id = path.rsplit("/", 1)[-1]
        return httpx.Response(200, json={"status": "succeeded", "download_url": f"/api/exports/{export_id}/download"})
    if request.method == "GET" and path.endswith("/download"):
        return httpx.Response(200, content=b"file")
    if request.method == "GET" and path == "/api/admin/settings":
        return httpx.Response(
            200,
            json={
                "youtube_api_key": {"is_configured": True},
                "llm": {"api_key_configured": True},
                "embedding": {"api_key_configured": True},
            },
        )
    if request.method == "GET" and path == "/api/admin/jobs":
        return httpx.Response(200, json={"items": [{"job_id": "normal"}]})
    if request.method == "GET" and path in {"/api/admin/logs", "/api/admin/quota-events"}:
        return httpx.Response(200, json={"items": []})
    raise AssertionError(f"unhandled request: {request.method} {path}")


def _job(case: str) -> dict:
    keys = (
        "validate_input",
        "collect_metadata",
        "collect_comments",
        "collect_transcript",
        "create_analysis_run",
        "analyze_comments",
        "analyze_script",
        "build_comment_network",
        "build_report_snapshot",
        "finalize_job",
    )
    steps = [{"step_key": key, "status": "succeeded", "error": None} for key in keys]
    status = "succeeded"
    if case == "comments_disabled":
        status = "partial_success"
        _set_step(steps, "collect_comments", "skipped", "COMMENTS_DISABLED")
        _set_step(steps, "analyze_comments", "skipped", "COMMENT_COLLECTION_INCOMPLETE")
    elif case == "no_caption":
        status = "partial_success"
        _set_step(steps, "collect_transcript", "skipped", "CAPTION_NOT_AVAILABLE")
        _set_step(steps, "analyze_script", "skipped", "CAPTION_NOT_AVAILABLE")
    return {
        "job_id": case,
        "status": status,
        "progress": {"percent": 100},
        "steps": steps,
        "links": {"report_api": f"/api/reports/{case}"},
        "finished_at": "2026-07-11T00:00:00Z",
    }


def _set_step(steps: list[dict], key: str, status: str, code: str) -> None:
    step = next(item for item in steps if item["step_key"] == key)
    step["status"] = status
    step["error"] = {"code": code, "message": "expected"}


def _report(case: str) -> dict:
    comments = 0 if case == "comments_disabled" else 1
    script_segments = 0 if case == "no_caption" else 1
    return {
        "report_id": case,
        "status": "succeeded" if case == "normal" else "partial_success",
        "video": {"title": "Video"},
        "analysis_config": {
            "llm_model": "model",
            "prompt_versions": {"comment": "category-rag-v0.3.0", "script": "category-rag-v0.3.0"},
            "retriever_config": {"example_min_similarity": 0.4},
        },
        "collection_summary": {
            "comments_collected": comments,
            "replies_collected": 0,
            "transcript_available": bool(script_segments),
        },
        "comment_analysis_summary": {"total": comments},
        "script_analysis_summary": {"total": script_segments},
    }
