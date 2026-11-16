import { Button } from "@astryxdesign/core/Button";
import { EmptyState } from "@astryxdesign/core/EmptyState";
import { SegmentedControl, SegmentedControlItem } from "@astryxdesign/core/SegmentedControl";
import { Text } from "@astryxdesign/core/Text";
import { TextInput } from "@astryxdesign/core/TextInput";
import { FileText, Search } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { getMyJobs, getReport } from "../api";
import { errorMessage, stepLabel } from "../labels";
import type { Job, Report } from "../types";
import { ErrorState, LoadingState, PageHeader, StatusLabel } from "../ui/common";
import { formatDate, reportIdFromPath, TERMINAL_STATUSES } from "../utils";

type Filter = "all" | "active" | "done" | "failed";

const FILTERS: Record<Filter, (job: Job) => boolean> = {
  all: () => true,
  active: (job) => !TERMINAL_STATUSES.has(job.status),
  done: (job) => job.status === "succeeded" || job.status === "partial_success",
  failed: (job) => job.status === "failed",
};

export function HistoryPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [reports, setReports] = useState<Record<string, Report>>({});
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    getMyJobs().then((page) => {
      if (!active) return;
      setJobs(page.items);
      setLoading(false);
      void Promise.allSettled(page.items.map(async (job) => {
        const reportId = reportIdFromPath(job.links.report_api);
        return reportId ? [job.job_id, await getReport(reportId)] as const : null;
      })).then((results) => {
        if (!active) return;
        setReports(Object.fromEntries(results.flatMap((result) => result.status === "fulfilled" && result.value ? [result.value] : [])));
      });
    }).catch((cause) => { if (active) { setError(errorMessage(cause)); setLoading(false); } });
    return () => { active = false; };
  }, []);

  const needle = query.trim().toLowerCase();
  const visible = jobs.filter((job) => FILTERS[filter](job) && (
    !needle
    || job.youtube_video_id.toLowerCase().includes(needle)
    || job.job_id.toLowerCase().includes(needle)
    || (reports[job.job_id]?.video.title ?? "").toLowerCase().includes(needle)
  ));

  return (
    <div className="hs-page">
      <PageHeader title="내 분석" description="Google 계정으로 요청한 분석을 다시 확인합니다." />
      <div className="hs-toolbar">
        <TextInput type="search" label="검색" isLabelHidden value={query} onChange={setQuery} placeholder="영상 제목, 영상 ID, 작업 번호" startIcon={Search} hasClear width={320} />
        <SegmentedControl label="상태" value={filter} onChange={(value) => setFilter(value as Filter)}>
          <SegmentedControlItem value="all" label="전체" />
          <SegmentedControlItem value="active" label="진행 중" />
          <SegmentedControlItem value="done" label="완료" />
          <SegmentedControlItem value="failed" label="실패" />
        </SegmentedControl>
      </div>
      {error ? <ErrorState message={error} /> : loading ? <LoadingState label="분석 목록을 불러오는 중입니다" /> : jobs.length === 0 ? (
        <EmptyState title="아직 분석한 영상이 없습니다" description="영상 주소를 넣으면 댓글과 자막을 판정해 보고서로 정리합니다." icon={<FileText size={28} aria-hidden />} actions={<Button variant="primary" label="첫 분석 시작" href="/" />} />
      ) : visible.length === 0 ? (
        <EmptyState title="조건에 맞는 분석이 없습니다" description="검색어나 상태 필터를 바꿔보세요." isCompact />
      ) : (
        <ul className="hs-job-list">{visible.map((job) => <JobRow job={job} report={reports[job.job_id]} key={job.job_id} />)}</ul>
      )}
    </div>
  );
}

function JobRow({ job, report }: { job: Job; report?: Report }) {
  const reportId = reportIdFromPath(job.links.report_api);
  const destination = reportId ? `/reports/${reportId}` : `/jobs/${job.job_id}`;
  const title = report?.video.title ?? `YouTube 영상 ${job.youtube_video_id}`;
  const thumbnail = report?.video.thumbnail_url ?? `https://i.ytimg.com/vi/${encodeURIComponent(job.youtube_video_id)}/mqdefault.jpg`;
  const running = !TERMINAL_STATUSES.has(job.status);
  return (
    <li>
      <Link className="hs-job-row" to={destination}>
        <span className="hs-thumb hs-thumb--xs"><img src={thumbnail} alt="" /></span>
        <span className="hs-job-main">
          <Text weight="semibold" maxLines={1}>{title}</Text>
          <Text type="supporting">{report?.video.channel_title ? `${report.video.channel_title} · ` : ""}{formatDate(job.created_at)}</Text>
        </span>
        <span className="hs-job-status">
          <StatusLabel status={job.status} />
          {running && <Text type="supporting">{stepLabel(job.progress.current_step)} · {job.progress.percent}%</Text>}
        </span>
        <Text type="supporting" weight="medium">{reportId ? "보고서" : "진행 상황"}</Text>
      </Link>
    </li>
  );
}
