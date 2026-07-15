import { type CSSProperties, type FormEvent, type ReactNode, useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  BarChart3,
  BookOpen,
  Check,
  CircleDashed,
  CloudDownload,
  Download,
  FileText,
  History,
  Link as LinkIcon,
  LoaderCircle,
  Network,
  Play,
  Search,
  ShieldCheck,
  Sparkles,
  Terminal,
  Youtube,
} from "lucide-react";
import { Link, NavLink, Navigate, Outlet, Route, Routes, useNavigate, useParams } from "react-router-dom";

import { ApiError, createExport, createJob, getExport, getJob, getReport } from "./api";
import { getStoredJobs, rememberJob } from "./storage";
import type { Job, JobStep, Report, StoredJob } from "./types";
import { formatDate, formatNumber, ratioPercent, reportIdFromPath, TERMINAL_STATUSES } from "./utils";

const STEP_LABELS: Record<string, string> = {
  validate_input: "입력 검증",
  collect_metadata: "영상 메타데이터 수집",
  collect_comments: "댓글 수집",
  collect_transcript: "스크립트 수집",
  create_analysis_run: "분석 환경 준비",
  analyze_comments: "댓글 RAG 분석",
  analyze_script: "스크립트 RAG 분석",
  build_comment_network: "댓글 네트워크 생성",
  build_report_snapshot: "보고서 생성",
  finalize_job: "분석 완료 처리",
};

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<AnalysisRequestPage />} />
      <Route element={<AppShell />}>
        <Route path="/history" element={<HistoryPage />} />
        <Route path="/jobs/:jobId" element={<JobPage />} />
        <Route path="/reports/:reportId" element={<ReportPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

function Header() {
  return (
    <header className="topbar">
      <Link className="brand" to="/">SENTINEL-YT</Link>
      <nav className="topnav" aria-label="주 메뉴">
        <NavLink to="/" end>분석</NavLink>
        <NavLink to="/history">분석 이력</NavLink>
        <a href="/docs" target="_blank" rel="noreferrer">API 문서</a>
      </nav>
      <div className="engine-state"><span /> API 연결됨</div>
    </header>
  );
}

function AppShell() {
  return (
    <div className="app-shell">
      <Header />
      <div className="shell-body">
        <aside className="sidebar">
          <div className="engine-card">
            <div className="engine-icon"><BarChart3 size={20} /></div>
            <div><strong>Analysis Engine</strong><small>RAG Pipeline Active</small></div>
          </div>
          <nav>
            <NavLink to="/history"><History size={18} /> 분석 이력</NavLink>
            <a href="/api/health/readiness" target="_blank" rel="noreferrer"><Activity size={18} /> API 상태</a>
            <a href="/docs" target="_blank" rel="noreferrer"><BookOpen size={18} /> 문서</a>
          </nav>
          <Link className="new-analysis" to="/"><Play size={16} /> 새 분석</Link>
          <div className="sidebar-note"><ShieldCheck size={18} /><span>정의·유사 사례 기반<br />dual-vector RAG</span></div>
        </aside>
        <main className="shell-content"><Outlet /></main>
      </div>
    </div>
  );
}

function AnalysisRequestPage() {
  const navigate = useNavigate();
  const [input, setInput] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!input.trim()) {
      setError("YouTube URL 또는 영상 ID를 입력해주세요.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const job = await createJob(input.trim());
      rememberJob({ jobId: job.job_id, videoId: job.youtube_video_id, createdAt: job.created_at });
      navigate(`/jobs/${job.job_id}`);
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="landing">
      <Header />
      <main className="hero">
        <div className="hero-grid" />
        <div className="hero-content">
          <span className="eyebrow">Precision Analysis Engine</span>
          <h1><span>YouTube 영상</span><span>혐오표현 분석</span></h1>
          <p className="hero-copy"><span>댓글과 공개 자막을 수집하고,</span><span>RAG 기반 근거와 함께 혐오표현을 분류해 보고서를 생성합니다.</span></p>
          <form className="analysis-form" onSubmit={submit}>
            <div className="analysis-input">
              <LinkIcon size={20} />
              <input
                aria-label="YouTube URL 또는 영상 ID"
                value={input}
                onChange={(event) => setInput(event.target.value)}
                placeholder="YouTube URL 또는 영상 ID를 붙여넣으세요"
                disabled={submitting}
              />
            </div>
            <button type="submit" disabled={submitting}>
              {submitting ? <LoaderCircle className="spin" size={19} /> : <Sparkles size={19} />}
              {submitting ? "요청 중" : "분석 시작"}
            </button>
          </form>
          {error && <div className="inline-error" role="alert">{error}</div>}
          <div className="process-grid">
            <ProcessCard icon={<CloudDownload />} number="01" title="데이터 수집">영상 정보, 댓글·대댓글과 공개 자막을 안전하게 수집합니다.</ProcessCard>
            <ProcessCard icon={<Sparkles />} number="02" title="RAG 분석">정의 문서와 유사 사례를 함께 검색해 맥락을 분류합니다.</ProcessCard>
            <ProcessCard icon={<BarChart3 />} number="03" title="보고서 생성">분류 결과와 네트워크 요약을 다운로드 가능한 보고서로 만듭니다.</ProcessCard>
          </div>
        </div>
      </main>
      <footer className="landing-footer"><strong>SENTINEL</strong><span>Evidence-based YouTube analysis</span></footer>
    </div>
  );
}

function ProcessCard({ icon, number, title, children }: { icon: ReactNode; number: string; title: string; children: ReactNode }) {
  return (
    <article className="process-card">
      <div><span className="card-icon">{icon}</span><small>STEP {number}</small></div>
      <h2>{title}</h2><p>{children}</p>
    </article>
  );
}

function JobPage() {
  const { jobId = "" } = useParams();
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    let timer: number | undefined;
    const load = async () => {
      try {
        const next = await getJob(jobId);
        if (!active) return;
        setJob(next);
        rememberJob({ jobId: next.job_id, videoId: next.youtube_video_id, createdAt: next.created_at });
        if (!TERMINAL_STATUSES.has(next.status)) timer = window.setTimeout(load, 2000);
      } catch (cause) {
        if (active) setError(errorMessage(cause));
      }
    };
    void load();
    return () => { active = false; if (timer) window.clearTimeout(timer); };
  }, [jobId]);

  if (error) return <ErrorState message={error} />;
  if (!job) return <LoadingState label="분석 작업을 불러오는 중입니다" />;

  const reportId = reportIdFromPath(job.links.report_api);
  return (
    <div className="page-wrap">
      <PageTitle kicker={`JOB · ${job.job_id.slice(0, 8).toUpperCase()}`} title="분석 파이프라인">
        <StatusBadge status={job.status} />
      </PageTitle>
      <div className="job-layout">
        <section className="panel pipeline-panel">
          <div className="panel-heading">
            <div><h2>Pipeline Sequence</h2><p>각 단계는 서버의 실제 작업 상태와 동기화됩니다.</p></div>
            <strong className="progress-number">{job.progress.percent}%</strong>
          </div>
          <div className="progress-track"><span style={{ width: `${job.progress.percent}%` }} /></div>
          <div className="step-list">{job.steps.map((step) => <StepRow key={step.step_key} step={step} />)}</div>
        </section>
        <aside className="job-aside">
          <section className="video-card">
            <div className="video-visual"><Youtube size={42} /><span>{job.youtube_video_id}</span></div>
            <div><small>YOUTUBE VIDEO ID</small><h3>{job.youtube_video_id}</h3><p>요청 시각 {formatDate(job.created_at)}</p></div>
          </section>
          <section className="panel metric-stack">
            <Metric label="진행률" value={`${job.progress.percent}%`} />
            <Metric label="현재 단계" value={job.progress.current_step ? STEP_LABELS[job.progress.current_step] ?? job.progress.current_step : "완료"} />
            <Metric label="작업 상태" value={statusText(job.status)} accent />
          </section>
          {reportId && <Link className="primary-action" to={`/reports/${reportId}`}><FileText size={18} /> 보고서 열기 <ArrowRight size={18} /></Link>}
        </aside>
      </div>
      <section className="terminal-panel">
        <div className="terminal-title"><Terminal size={17} /> LIVE PROCESS LOG</div>
        {job.steps.filter((step) => step.status !== "pending").map((step) => (
          <p key={step.step_key}><span>{step.finished_at ? formatDate(step.finished_at) : "진행 중"}</span> {step.status.toUpperCase()}: {STEP_LABELS[step.step_key] ?? step.step_key}</p>
        ))}
      </section>
    </div>
  );
}

function StepRow({ step }: { step: JobStep }) {
  const running = step.status === "running";
  const complete = ["succeeded", "skipped"].includes(step.status);
  return (
    <div className={`step-row ${running ? "running" : ""}`}>
      <span className={`step-state ${complete ? "complete" : running ? "active" : step.status === "failed" ? "failed" : ""}`}>
        {complete ? <Check size={15} /> : running ? <LoaderCircle className="spin" size={15} /> : <CircleDashed size={15} />}
      </span>
      <div><strong>{STEP_LABELS[step.step_key] ?? step.step_key}</strong><small>{step.error?.message ?? stepStatusText(step.status)}</small></div>
      <code>{step.status}</code>
    </div>
  );
}

function HistoryPage() {
  const stored = useMemo(() => getStoredJobs(), []);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.allSettled(stored.map((item) => getJob(item.jobId))).then((results) => {
      setJobs(results.flatMap((result) => result.status === "fulfilled" ? [result.value] : []));
      setLoading(false);
    });
  }, [stored]);

  const visible = jobs.filter((job) => job.youtube_video_id.toLowerCase().includes(query.toLowerCase()) || job.job_id.includes(query));
  return (
    <div className="page-wrap">
      <PageTitle title="내 분석 이력" kicker="REPORTS"><Link className="button-small" to="/"><Play size={15} /> 새 분석</Link></PageTitle>
      <p className="page-description">이 브라우저에서 요청한 YouTube 분석 작업을 다시 확인합니다.</p>
      <div className="history-toolbar"><Search size={18} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="영상 ID 또는 작업 ID 검색" /></div>
      {loading ? <LoadingState label="분석 이력을 불러오는 중입니다" /> : visible.length === 0 ? (
        <EmptyState stored={stored} />
      ) : (
        <div className="history-grid">{visible.map((job) => <HistoryCard job={job} key={job.job_id} />)}</div>
      )}
    </div>
  );
}

function HistoryCard({ job }: { job: Job }) {
  const reportId = reportIdFromPath(job.links.report_api);
  const destination = reportId ? `/reports/${reportId}` : `/jobs/${job.job_id}`;
  return (
    <article className="history-card">
      <div className="history-thumbnail"><Youtube size={36} /><span>{job.youtube_video_id}</span></div>
      <div className="history-card-body">
        <StatusBadge status={job.status} />
        <h2>YouTube Video · {job.youtube_video_id}</h2>
        <p>{formatDate(job.created_at)}</p>
        <div className="history-meta"><span>진행률 <strong>{job.progress.percent}%</strong></span><span>단계 <strong>{job.steps.length}</strong></span></div>
        <Link to={destination}>{reportId ? "보고서 보기" : "작업 상태 보기"} <ArrowRight size={16} /></Link>
      </div>
    </article>
  );
}

function ReportPage() {
  const { reportId = "" } = useParams();
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState<string | null>(null);

  useEffect(() => { getReport(reportId).then(setReport).catch((cause) => setError(errorMessage(cause))); }, [reportId]);

  async function exportReport(format: "html" | "xlsx") {
    setExporting(format);
    try {
      const created = await createExport(reportId, format);
      const result = await getExport(created.export_id);
      if (!result.download_url) throw new Error("내보내기 파일이 아직 준비되지 않았습니다.");
      window.location.assign(result.download_url);
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setExporting(null);
    }
  }

  if (error && !report) return <ErrorState message={error} />;
  if (!report) return <LoadingState label="분석 보고서를 불러오는 중입니다" />;

  const summary = report.comment_analysis_summary;
  const hateRatio = ratioPercent(summary.hate_speech_count, summary.total);
  const categories = Object.entries(summary.category_distribution).sort((a, b) => b[1] - a[1]);
  const nodeCount = Number(report.network_summary.node_count ?? 0);
  const edgeCount = Number(report.network_summary.edge_count ?? 0);
  return (
    <div className="page-wrap report-page">
      {report.failure_summary.length > 0 && <div className="report-warning"><AlertTriangle size={18} /> 일부 분석이 건너뛰어졌습니다. 아래 결과는 수집 가능한 데이터 기준입니다.</div>}
      <section className="report-hero panel">
        <div className="report-thumbnail">{report.video.thumbnail_url ? <img src={report.video.thumbnail_url} alt="영상 썸네일" /> : <Youtube size={38} />}</div>
        <div className="report-identity"><small>ANALYSIS REPORT</small><h1>{report.video.title ?? report.title}</h1><p>{report.video.channel_title ?? "채널 정보 없음"} · {formatDate(report.created_at)}</p></div>
        <div className="export-actions">
          <button onClick={() => void exportReport("html")} disabled={Boolean(exporting)}><Download size={17} /> {exporting === "html" ? "생성 중" : "HTML"}</button>
          <button onClick={() => void exportReport("xlsx")} disabled={Boolean(exporting)}><Download size={17} /> {exporting === "xlsx" ? "생성 중" : "Excel"}</button>
        </div>
      </section>
      {error && <div className="inline-error">{error}</div>}
      <section className="stat-grid">
        <StatCard label="수집 댓글" value={formatNumber(report.collection_summary.comments_collected + report.collection_summary.replies_collected)} />
        <StatCard label="분석 완료" value={formatNumber(summary.succeeded)} />
        <StatCard label="혐오표현 비율" value={`${hateRatio.toFixed(1)}%`} danger={hateRatio > 0} />
      </section>
      <div className="report-grid">
        <section className="panel distribution-panel">
          <PanelTitle icon={<BarChart3 size={18} />} title="카테고리 분포" />
          <div className="donut-wrap">
            <div className="donut" style={{ "--ratio": `${Math.min(hateRatio, 100) * 3.6}deg` } as CSSProperties}><span><strong>{formatNumber(summary.total)}</strong>분석</span></div>
            <div className="legend"><p><i className="normal" />정상 <strong>{(100 - hateRatio).toFixed(1)}%</strong></p><p><i className="risk" />혐오표현 <strong>{hateRatio.toFixed(1)}%</strong></p></div>
          </div>
          <div className="category-list">{categories.length ? categories.map(([name, count]) => <div key={name}><span>{name}</span><div><i style={{ width: `${ratioPercent(count, summary.total)}%` }} /></div><strong>{formatNumber(count)}</strong></div>) : <p className="muted">분류된 혐오 카테고리가 없습니다.</p>}</div>
        </section>
        <section className="panel cases-panel">
          <PanelTitle icon={<AlertTriangle size={18} />} title="대표 탐지 사례" />
          {report.representative_comments.length ? report.representative_comments.slice(0, 5).map((comment) => (
            <article className="case-card" key={comment.youtube_comment_id}>
              <div><span>FLAGGED</span><code>{comment.youtube_comment_id.slice(0, 12)}</code></div>
              <p>{comment.text}</p>
              <footer><span>{comment.categories.join(", ") || "미분류"}</span><small>좋아요 {formatNumber(comment.like_count)}</small></footer>
            </article>
          )) : <div className="clean-state"><ShieldCheck size={32} /><strong>대표 혐오표현 사례 없음</strong><p>현재 보고서에서 표시할 탐지 사례가 없습니다.</p></div>}
        </section>
      </div>
      <section className="panel network-panel">
        <PanelTitle icon={<Network size={18} />} title="댓글 네트워크 분석" />
        <div className="network-visual" aria-label={`노드 ${nodeCount}개, 연결 ${edgeCount}개`}>
          <span className="network-node node-a" /><span className="network-node node-b" /><span className="network-node node-c" /><span className="network-node node-d" />
          <div><Network size={32} /><strong>Relationship Graph</strong><p>{formatNumber(nodeCount)} Nodes · {formatNumber(edgeCount)} Connections</p></div>
        </div>
      </section>
    </div>
  );
}

function PageTitle({ kicker, title, children }: { kicker?: string; title: string; children?: ReactNode }) {
  return <div className="page-title"><div>{kicker && <small>{kicker}</small>}<h1>{title}</h1></div>{children}</div>;
}

function PanelTitle({ icon, title }: { icon: ReactNode; title: string }) {
  return <div className="panel-title"><span>{icon}</span><h2>{title}</h2></div>;
}

function StatusBadge({ status }: { status: string }) {
  return <span className={`status-badge status-${status}`}><i />{statusText(status)}</span>;
}

function Metric({ label, value, accent = false }: { label: string; value: string; accent?: boolean }) {
  return <div className="metric"><span>{label}</span><strong className={accent ? "accent" : ""}>{value}</strong></div>;
}

function StatCard({ label, value, danger = false }: { label: string; value: string; danger?: boolean }) {
  return <article className="stat-card"><small>{label}</small><strong className={danger ? "danger" : ""}>{value}</strong></article>;
}

function LoadingState({ label }: { label: string }) {
  return <div className="state-card"><LoaderCircle className="spin" size={28} /><strong>{label}</strong></div>;
}

function ErrorState({ message }: { message: string }) {
  return <div className="state-card error-state"><AlertTriangle size={30} /><strong>{message}</strong><Link to="/">새 분석 시작</Link></div>;
}

function EmptyState({ stored }: { stored: StoredJob[] }) {
  return <div className="state-card"><FileText size={32} /><strong>{stored.length ? "조회 가능한 분석 이력이 없습니다." : "아직 분석 이력이 없습니다."}</strong><Link to="/">첫 분석 시작하기</Link></div>;
}

function errorMessage(cause: unknown): string {
  if (cause instanceof ApiError || cause instanceof Error) return cause.message;
  return "알 수 없는 오류가 발생했습니다.";
}

function statusText(status: string): string {
  return ({ pending: "대기 중", running: "분석 중", succeeded: "완료", partial_success: "일부 완료", failed: "실패", skipped: "건너뜀" } as Record<string, string>)[status] ?? status;
}

function stepStatusText(status: string): string {
  return ({ pending: "이전 단계 완료를 기다리고 있습니다.", running: "현재 처리 중입니다.", succeeded: "정상적으로 완료했습니다.", skipped: "사용 가능한 데이터가 없어 건너뛰었습니다.", failed: "처리 중 오류가 발생했습니다." } as Record<string, string>)[status] ?? status;
}
