import { Banner } from "@astryxdesign/core/Banner";
import { BreadcrumbItem, Breadcrumbs } from "@astryxdesign/core/Breadcrumbs";
import { Button } from "@astryxdesign/core/Button";
import { Heading } from "@astryxdesign/core/Heading";
import { ProgressBar } from "@astryxdesign/core/ProgressBar";
import { Text } from "@astryxdesign/core/Text";
import { AlertCircle, Check, Minus } from "lucide-react";
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { ApiError, getJob } from "../api";
import { errorMessage, stepLabel } from "../labels";
import type { Job, JobStep } from "../types";
import { ErrorState, LoadingState, StatusLabel } from "../ui/common";
import { formatDate, formatNumber, reportIdFromPath, TERMINAL_STATUSES } from "../utils";

const POLL_MS = 2000;
const MAX_BACKOFF_MS = 30000;

export function JobPage() {
  const { jobId = "" } = useParams();
  const { job, fatalError, connectionLost } = useJobPolling(jobId);

  if (fatalError) return <ErrorState message={fatalError} />;
  if (!job) return <LoadingState label="분석 작업을 불러오는 중입니다" />;

  const reportId = reportIdFromPath(job.links.report_api);
  const failedStep = job.steps.find((step) => step.status === "failed");
  const current = job.steps.find((step) => step.step_key === job.progress.current_step);

  return (
    <div className="hs-page">
      <Breadcrumbs label="경로">
        <BreadcrumbItem href="/history">내 분석</BreadcrumbItem>
        <BreadcrumbItem>작업 진행</BreadcrumbItem>
      </Breadcrumbs>

      <header className="hs-video-header">
        <div className="hs-thumb hs-thumb--sm"><img src={`https://i.ytimg.com/vi/${encodeURIComponent(job.youtube_video_id)}/mqdefault.jpg`} alt="" /></div>
        <div className="hs-stack hs-stack--tight">
          <StatusLabel status={job.status} />
          <Heading level={1}>YouTube 영상 {job.youtube_video_id}</Heading>
          <Text type="supporting">요청 {formatDate(job.created_at)} · 작업 번호 <span className="hs-code">{job.job_id.slice(0, 8).toUpperCase()}</span></Text>
        </div>
      </header>

      {connectionLost && (
        <Banner status="warning" title="서버와 연결이 잠시 끊겼습니다" description="분석은 서버에서 계속 진행됩니다. 자동으로 다시 연결하는 중입니다." />
      )}
      {reportId && TERMINAL_STATUSES.has(job.status) && job.status !== "failed" && (
        <Banner
          status="success"
          title={job.status === "partial_success" ? "분석이 끝났습니다 (일부 단계는 건너뜀)" : "분석이 끝났습니다"}
          description={summaryLine(job)}
          endContent={<Button variant="primary" size="sm" label="보고서 열기" href={`/reports/${reportId}`} />}
        />
      )}
      {job.status === "failed" && (
        <div className="hs-failure" role="alert">
          <AlertCircle size={20} aria-hidden />
          <div className="hs-stack hs-stack--tight">
            <Text weight="semibold">{failedStep ? `${stepLabel(failedStep.step_key)} 중에 멈췄습니다` : "분석이 멈췄습니다"}</Text>
            <Text type="supporting">{failedStep?.error?.message ?? "처리 중 오류가 발생했습니다."}</Text>
          </div>
          <Button size="sm" label="새 분석 시작" href="/" />
        </div>
      )}

      <div className="hs-split">
        <section className="hs-main hs-stack" aria-labelledby="steps-title">
          <div className="hs-section-header">
            <Heading level={2} id="steps-title">진행 단계</Heading>
            <Text weight="semibold" size="xl">{job.progress.percent}%</Text>
          </div>
          <ProgressBar label="전체 진행률" isLabelHidden value={job.progress.percent} variant={job.status === "failed" ? "neutral" : "accent"} />
          <ol className="hs-steps">
            {job.steps.map((step, index) => <StepRow key={step.step_key} index={index} step={step} totalHint={itemTotalHint(job, step)} />)}
          </ol>
        </section>

        <aside className="hs-aside hs-aside--ruled">
          <dl className="hs-kv">
            <div><dt>현재 단계</dt><dd>{job.status === "failed" ? "멈춤" : stepLabel(job.progress.current_step)}</dd></div>
            <div><dt>진행률</dt><dd>{job.progress.percent}%</dd></div>
            {typeof job.summary.comments_collected === "number" && <div><dt>모은 댓글·답글</dt><dd>{formatNumber(job.summary.comments_collected)}</dd></div>}
            {current?.item_progress && <div><dt>판정한 댓글</dt><dd>{formatNumber(current.item_progress.completed)} / {formatNumber(current.item_progress.total)}</dd></div>}
            <div><dt>요청 시각</dt><dd>{formatDate(job.created_at)}</dd></div>
            {job.finished_at && <div><dt>끝난 시각</dt><dd>{formatDate(job.finished_at)}</dd></div>}
          </dl>
          {!TERMINAL_STATUSES.has(job.status) && <p className="hs-note">이 창을 닫아도 분석은 계속됩니다. 결과는 내 분석에서 다시 볼 수 있습니다.</p>}
        </aside>
      </div>
    </div>
  );
}

function useJobPolling(jobId: string) {
  const [job, setJob] = useState<Job | null>(null);
  const [fatalError, setFatalError] = useState<string | null>(null);
  const [connectionLost, setConnectionLost] = useState(false);

  useEffect(() => {
    let active = true;
    let timer: number | undefined;
    let failures = 0;
    setJob(null);
    setFatalError(null);
    const load = async () => {
      try {
        const next = await getJob(jobId);
        if (!active) return;
        failures = 0;
        setConnectionLost(false);
        setJob(next);
        if (!TERMINAL_STATUSES.has(next.status)) timer = window.setTimeout(load, POLL_MS);
      } catch (cause) {
        if (!active) return;
        // Not found / forbidden will not fix itself; anything else is retried with backoff.
        if (cause instanceof ApiError && [400, 401, 403, 404, 422].includes(cause.status)) {
          setFatalError(errorMessage(cause));
          return;
        }
        failures += 1;
        setConnectionLost(true);
        timer = window.setTimeout(load, Math.min(MAX_BACKOFF_MS, POLL_MS * 2 ** failures));
      }
    };
    void load();
    return () => { active = false; if (timer) window.clearTimeout(timer); };
  }, [jobId]);

  return { job, fatalError, connectionLost };
}

function StepRow({ step, index, totalHint }: { step: JobStep; index: number; totalHint: number | null }) {
  const kind = step.status === "succeeded" ? "done" : step.status === "skipped" ? "skipped" : step.status;
  const marker = kind === "done" ? <Check size={14} aria-hidden /> : kind === "skipped" ? <Minus size={14} aria-hidden /> : kind === "failed" ? <AlertCircle size={14} aria-hidden /> : index + 1;
  const time = step.finished_at ? new Intl.DateTimeFormat("ko-KR", { timeStyle: "short" }).format(new Date(step.finished_at)) : kind === "running" ? "진행 중" : "";
  return (
    <li className="hs-step" data-state={kind}>
      <span className="hs-step-marker">{marker}</span>
      <div className="hs-stack hs-stack--tight">
        <div className="hs-step-title">
          <Text weight={kind === "pending" ? "medium" : "semibold"} color={kind === "pending" ? "secondary" : "primary"}>{stepLabel(step.step_key)}</Text>
          <Text type="supporting">{time}</Text>
        </div>
        <Text type="supporting">{step.error?.message ?? stepDetail(step, totalHint)}</Text>
        {step.item_progress && kind !== "done" && (
          <ProgressBar label={`${stepLabel(step.step_key)} 진행률`} isLabelHidden value={step.item_progress.percent} variant={kind === "failed" ? "neutral" : "accent"} />
        )}
      </div>
    </li>
  );
}

function itemTotalHint(job: Job, step: JobStep): number | null {
  const value = step.step_key === "analyze_comments" ? job.summary.comments_collected
    : step.step_key === "analyze_script" ? job.summary.segments_collected : null;
  return typeof value === "number" ? value : null;
}

function stepDetail(step: JobStep, totalHint: number | null): string {
  const unit = step.step_key === "analyze_script" ? "구간" : "개";
  const p = step.item_progress;
  if (p) {
    const failed = p.failed > 0 ? ` · ${formatNumber(p.failed)}${unit} 실패` : "";
    return `${formatNumber(p.total)}${unit} 중 ${formatNumber(p.completed)}${unit} 판정${failed}`;
  }
  if (step.status === "succeeded" && totalHint !== null) return `${formatNumber(totalHint)}${unit} 판정`;
  return { pending: "대기", running: "처리 중", succeeded: "완료", skipped: "가져올 데이터가 없어 건너뜀", failed: "오류로 멈춤" }[step.status] ?? step.status;
}

function summaryLine(job: Job): string {
  const parts: string[] = [];
  if (typeof job.summary.comments_collected === "number") parts.push(`댓글·답글 ${formatNumber(job.summary.comments_collected)}개`);
  if (typeof job.summary.segments_collected === "number" && job.summary.segments_collected > 0) parts.push(`자막 ${formatNumber(job.summary.segments_collected)}구간`);
  return parts.length ? `${parts.join(" · ")}을 판정했습니다.` : "보고서를 열어 결과를 확인하세요.";
}
