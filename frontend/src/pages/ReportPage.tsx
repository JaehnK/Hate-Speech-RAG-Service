import { Banner } from "@astryxdesign/core/Banner";
import { BreadcrumbItem, Breadcrumbs } from "@astryxdesign/core/Breadcrumbs";
import { Button } from "@astryxdesign/core/Button";
import { EmptyState } from "@astryxdesign/core/EmptyState";
import { Heading } from "@astryxdesign/core/Heading";
import { SegmentedControl, SegmentedControlItem } from "@astryxdesign/core/SegmentedControl";
import { Spinner } from "@astryxdesign/core/Spinner";
import { Text } from "@astryxdesign/core/Text";
import { Download, FileText, ShieldCheck, X } from "lucide-react";
import { lazy, Suspense, useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { type CommentFilters, createExport, getExport, getHateComments, getReport, getReportNetwork, getScriptSegments } from "../api";
import { HateCommentCard } from "../report/HateCommentCard";
import { errorMessage } from "../labels";
import { useSession } from "../session";
import type { CommentNetwork, Report, ReportComment, ReportCommentPage, ReportScriptSegment, ReportScriptSegmentPage } from "../types";
import { ErrorState, LoadingState } from "../ui/common";
import { categoryLabel, formatDate, formatNumber, formatPlaybackTime, ratioPercent } from "../utils";

const CommentNetworkGraph = lazy(() => import("../CommentNetworkGraph").then((module) => ({ default: module.CommentNetworkGraph })));

type Scope = "all" | "group" | "individual";
type ActiveFilter = { kind: "category"; value: string } | { kind: "author"; value: string; label: string } | null;

export function ReportPage() {
  const { reportId = "" } = useParams();
  const { session } = useSession();
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);
  const [exporting, setExporting] = useState<string | null>(null);
  const [filter, setFilter] = useState<ActiveFilter>(null);

  useEffect(() => {
    let active = true;
    setReport(null);
    setError(null);
    setFilter(null);
    void getReport(reportId).then((value) => { if (active) setReport(value); }).catch((cause) => { if (active) setError(errorMessage(cause)); });
    return () => { active = false; };
  }, [reportId]);

  async function exportReport(format: "html" | "xlsx") {
    setExporting(format);
    setExportError(null);
    try {
      const created = await createExport(reportId, format);
      const result = await getExport(created.export_id);
      if (!result.download_url) throw new Error("내보내기 파일이 아직 준비되지 않았습니다. 잠시 후 다시 시도해주세요.");
      window.location.assign(result.download_url);
    } catch (cause) {
      setExportError(errorMessage(cause));
    } finally {
      setExporting(null);
    }
  }

  if (error) return <ErrorState message={error} />;
  if (!report) return <LoadingState label="보고서를 불러오는 중입니다" />;

  const title = report.video.title ?? report.title;
  const showAuthor = (authorKey: string, label: string) => {
    if (authorKey.startsWith("anonymous:")) return;
    setFilter({ kind: "author", value: authorKey, label });
    document.getElementById("comments")?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <div className="hs-page">
      <Breadcrumbs label="경로">
        {session ? <BreadcrumbItem href="/history">내 분석</BreadcrumbItem> : <BreadcrumbItem href="/#samples">공개 샘플</BreadcrumbItem>}
        <BreadcrumbItem>보고서</BreadcrumbItem>
      </Breadcrumbs>

      <header className="hs-video-header">
        <div className="hs-thumb hs-thumb--md">{report.video.thumbnail_url ? <img src={report.video.thumbnail_url} alt="" /> : <FileText size={28} aria-hidden />}</div>
        <div className="hs-stack hs-stack--tight hs-grow">
          <Heading level={1} maxLines={2} wordBreak="break-word">{title}</Heading>
          <Text type="supporting">{report.video.channel_title ?? "채널 정보 없음"} · 분석 {formatDate(report.created_at)}</Text>
        </div>
        <div className="hs-row">
          <Button size="sm" label="HTML 내려받기" icon={<Download size={16} aria-hidden />} isLoading={exporting === "html"} isDisabled={exporting !== null && exporting !== "html"} onClick={() => void exportReport("html")} />
          <Button size="sm" label="Excel 내려받기" icon={<Download size={16} aria-hidden />} isLoading={exporting === "xlsx"} isDisabled={exporting !== null && exporting !== "xlsx"} onClick={() => void exportReport("xlsx")} />
        </div>
      </header>

      {exportError && <Banner status="error" title="내려받지 못했습니다" description={exportError} isDismissable onDismiss={() => setExportError(null)} />}
      {report.failure_summary.length > 0 && (
        <Banner status="warning" title="일부 단계를 건너뛰었습니다" description="아래 결과는 모을 수 있었던 데이터만으로 만든 것입니다." />
      )}

      <Overview report={report} onCategory={(category) => { setFilter({ kind: "category", value: category }); document.getElementById("comments")?.scrollIntoView({ behavior: "smooth", block: "start" }); }} />
      <CommentsSection reportId={reportId} report={report} filter={filter} onClearFilter={() => setFilter(null)} />
      <ScriptSection reportId={reportId} report={report} />
      <NetworkSection reportId={reportId} onShowAuthor={showAuthor} />
    </div>
  );
}

function Overview({ report, onCategory }: { report: Report; onCategory: (category: string) => void }) {
  const summary = report.comment_analysis_summary;
  const judged = summary.succeeded;
  const split = summary.group_hate_count !== undefined;
  const group = split ? summary.group_hate_count ?? 0 : summary.hate_speech_count;
  const insult = split ? summary.insult_count ?? 0 : 0;
  // Shares are of judged comments only, so failed comments never count as "normal".
  const groupPct = ratioPercent(group, judged);
  const insultPct = ratioPercent(insult, judged);
  const normalPct = Math.max(0, 100 - groupPct - insultPct);
  const categories = Object.entries(summary.category_distribution).filter(([name]) => name !== "unclassified").sort((a, b) => b[1] - a[1]);
  const maxCount = Math.max(1, ...categories.map(([, count]) => count));
  const collected = report.collection_summary.comments_collected + report.collection_summary.replies_collected;

  return (
    <section className="hs-section" aria-labelledby="overview-title">
      <Heading level={2} id="overview-title" accessibilityLevel={2}>요약</Heading>
      <dl className="hs-stats">
        <div><dt>모은 댓글·답글</dt><dd>{formatNumber(collected)}</dd></div>
        <div><dt>판정 완료</dt><dd>{formatNumber(judged)}</dd></div>
        {split ? (
          <>
            <div><dt>집단 혐오</dt><dd>{groupPct.toFixed(1)}%</dd></div>
            <div><dt>모욕·욕설</dt><dd>{insultPct.toFixed(1)}%</dd></div>
          </>
        ) : <div><dt>혐오표현</dt><dd>{groupPct.toFixed(1)}%</dd></div>}
        {summary.failed > 0 && <div><dt>판정 실패</dt><dd>{formatNumber(summary.failed)}</dd></div>}
      </dl>

      <div className="hs-split">
        <div className="hs-main hs-stack">
          <Heading level={3}>판정 분포</Heading>
          <div className="hs-data-bar hs-data-bar--lg" role="img" aria-label={`판정한 댓글 ${formatNumber(judged)}개 중 집단 혐오 ${groupPct.toFixed(1)}%, 모욕·욕설 ${insultPct.toFixed(1)}%, 혐오 아님 ${normalPct.toFixed(1)}%`}>
            <span className="is-hate" style={{ width: `${groupPct}%` }} />
            <span className="is-insult" style={{ width: `${insultPct}%` }} />
          </div>
          <div className="hs-legend">
            <span><i className="hs-swatch is-hate" />{split ? "집단 혐오" : "혐오표현"} {groupPct.toFixed(1)}%</span>
            {split && <span><i className="hs-swatch is-insult" />모욕·욕설 {insultPct.toFixed(1)}%</span>}
            <span><i className="hs-swatch is-normal" />혐오 아님 {normalPct.toFixed(1)}%</span>
          </div>
          <p className="hs-note">비율은 판정을 마친 댓글 {formatNumber(judged)}개 기준입니다{summary.failed > 0 ? ` (판정 실패 ${formatNumber(summary.failed)}개 제외)` : ""}.</p>
        </div>
        <div className="hs-aside hs-stack">
          <Heading level={3}>유형별 댓글 수</Heading>
          {categories.length ? (
            <ul className="hs-category-list">
              {categories.map(([name, count]) => (
                <li key={name}>
                  <button type="button" onClick={() => onCategory(name)} aria-label={`${categoryLabel(name)} 댓글 ${formatNumber(count)}개 보기`}>
                    <span className="hs-category-name">{categoryLabel(name)}</span>
                    <span className="hs-category-bar"><span style={{ width: `${(count / maxCount) * 100}%` }} /></span>
                    <span className="hs-category-count">{formatNumber(count)}</span>
                  </button>
                </li>
              ))}
            </ul>
          ) : <Text type="supporting">혐오 유형으로 분류된 댓글이 없습니다.</Text>}
        </div>
      </div>
    </section>
  );
}

function CommentsSection({ reportId, report, filter, onClearFilter }: { reportId: string; report: Report; filter: ActiveFilter; onClearFilter: () => void }) {
  const [items, setItems] = useState<ReportComment[]>([]);
  const [page, setPage] = useState<ReportCommentPage | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [scope, setScope] = useState<Scope>("all");
  const split = report.comment_analysis_summary.group_hate_count !== undefined;
  const filters: CommentFilters = filter?.kind === "category" ? { category: filter.value } : filter?.kind === "author" ? { authorChannelId: filter.value } : {};

  useEffect(() => {
    let active = true;
    setItems([]);
    setPage(null);
    setLoading(true);
    setError(null);
    void getHateComments(reportId, 0, filters)
      .then((next) => { if (active) { setItems(next.items); setPage(next); } })
      .catch((cause) => { if (active) setError(errorMessage(cause)); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reportId, filter?.kind, filter?.value]);

  async function loadMore() {
    if (page?.next_cursor == null) return;
    setLoading(true);
    setError(null);
    try {
      const next = await getHateComments(reportId, page.next_cursor, filters);
      setItems((current) => [...current, ...next.items]);
      setPage(next);
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setLoading(false);
    }
  }

  const visible = scope === "all" ? items : items.filter((item) => (item.analysis.target_scope ?? "group") === scope);
  const filterLabel = filter?.kind === "category" ? `유형: ${categoryLabel(filter.value)}` : filter?.kind === "author" ? `작성자: ${filter.label}` : null;

  return (
    <section className="hs-section" id="comments" aria-labelledby="comments-title">
      <div className="hs-section-header">
        <Heading level={2} id="comments-title">{split ? "혐오·모욕 댓글" : "혐오 댓글"}</Heading>
        <Text type="supporting">좋아요 많은 순 · {formatNumber(items.length)} / {formatNumber(page?.total ?? report.comment_analysis_summary.hate_speech_count)}개</Text>
      </div>
      <div className="hs-toolbar">
        {split && (
          <SegmentedControl label="볼 댓글" value={scope} onChange={(value) => setScope(value as Scope)} size="sm">
            <SegmentedControlItem value="all" label="전체" />
            <SegmentedControlItem value="group" label="집단 혐오" />
            <SegmentedControlItem value="individual" label="모욕·욕설" />
          </SegmentedControl>
        )}
        {filterLabel && <Button size="sm" variant="ghost" label={`${filterLabel} 필터 해제`} icon={<X size={14} aria-hidden />} onClick={onClearFilter}>{filterLabel}</Button>}
      </div>
      {error && <Banner status="error" title="댓글을 불러오지 못했습니다" description={error} />}
      <div className="hs-comment-list" aria-live="polite">
        {visible.map((comment) => <HateCommentCard comment={comment} key={comment.comment_snapshot_id} />)}
        {loading && items.length === 0 && <div className="hs-state"><Spinner label="댓글을 불러오는 중입니다" /></div>}
        {!loading && !error && visible.length === 0 && (
          <EmptyState title={filterLabel ? "조건에 맞는 댓글이 없습니다" : "혐오표현으로 판정된 댓글이 없습니다"} icon={<ShieldCheck size={28} aria-hidden />} isCompact />
        )}
      </div>
      {page?.has_more && <Button label="댓글 더 보기" isLoading={loading} onClick={() => void loadMore()} />}
    </section>
  );
}

function ScriptSection({ reportId, report }: { reportId: string; report: Report }) {
  const [items, setItems] = useState<ReportScriptSegment[]>([]);
  const [page, setPage] = useState<ReportScriptSegmentPage | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [onlyFlagged, setOnlyFlagged] = useState("all");

  useEffect(() => {
    let active = true;
    setItems([]);
    setLoading(true);
    setError(null);
    void getScriptSegments(reportId)
      .then((next) => { if (active) { setItems(next.items); setPage(next); } })
      .catch((cause) => { if (active) setError(errorMessage(cause)); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [reportId]);

  async function loadMore() {
    if (page?.next_cursor == null) return;
    setLoading(true);
    try {
      const next = await getScriptSegments(reportId, page.next_cursor);
      setItems((current) => [...current, ...next.items]);
      setPage(next);
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setLoading(false);
    }
  }

  const summary = report.script_analysis_summary;
  const visible = onlyFlagged === "flagged" ? items.filter((item) => item.analysis.is_hate_speech) : items;

  return (
    <section className="hs-section" aria-labelledby="script-title">
      <div className="hs-section-header">
        <Heading level={2} id="script-title">자막 판정</Heading>
        <Text type="supporting">영상 시간순 · {formatNumber(summary.succeeded)}구간 판정 · 혐오표현 {formatNumber(summary.hate_speech_count)}구간</Text>
      </div>
      {items.length > 0 && summary.hate_speech_count > 0 && (
        <div className="hs-toolbar">
          <SegmentedControl label="볼 자막" value={onlyFlagged} onChange={setOnlyFlagged} size="sm">
            <SegmentedControlItem value="all" label="전체" />
            <SegmentedControlItem value="flagged" label="혐오표현만" />
          </SegmentedControl>
        </div>
      )}
      {error && <Banner status="error" title="자막 판정을 불러오지 못했습니다" description={error} />}
      {loading && items.length === 0 ? <div className="hs-state"><Spinner label="자막 판정을 불러오는 중입니다" /></div>
        : !error && items.length === 0 ? <EmptyState title="판정할 공개 자막이 없습니다" description="영상에 공개 자막이 없거나 자막 판정 결과가 없습니다." icon={<FileText size={28} aria-hidden />} isCompact />
        : (
          <ol className="hs-script-list">
            {visible.map((segment) => <ScriptRow segment={segment} key={segment.segment_id} />)}
          </ol>
        )}
      {page?.has_more && <Button label="자막 더 보기" isLoading={loading} onClick={() => void loadMore()} />}
    </section>
  );
}

function ScriptRow({ segment }: { segment: ReportScriptSegment }) {
  const failed = segment.analysis.status === "failed";
  const flagged = segment.analysis.is_hate_speech === true;
  const categories = segment.analysis.categories ?? [];
  return (
    <li className="hs-script-row" data-flagged={flagged || undefined}>
      <Text type="supporting" hasTabularNumbers>{formatPlaybackTime(segment.start_seconds)}–{formatPlaybackTime(segment.end_seconds)}</Text>
      <div className="hs-stack hs-stack--tight">
        <Text as="p">{segment.text}</Text>
        {flagged && (
          <Text type="supporting">
            <span className="hs-swatch is-hate" aria-hidden /> {categories.map(categoryLabel).join(", ") || "혐오표현"}
            {segment.analysis.reasoning ? ` — ${segment.analysis.reasoning}` : ""}
          </Text>
        )}
        {failed && <Text type="supporting">판정 실패</Text>}
      </div>
    </li>
  );
}

function NetworkSection({ reportId, onShowAuthor }: { reportId: string; onShowAuthor: (authorKey: string, label: string) => void }) {
  const [network, setNetwork] = useState<CommentNetwork | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setNetwork(null);
    setError(null);
    void getReportNetwork(reportId).then((value) => { if (active) setNetwork(value); }).catch((cause) => { if (active) setError(errorMessage(cause)); });
    return () => { active = false; };
  }, [reportId]);

  return (
    <section className="hs-section" aria-labelledby="network-title">
      <div className="hs-section-header">
        <Heading level={2} id="network-title">답글 관계</Heading>
        <Text type="supporting">누가 누구에게 답글을 달았는지 보여줍니다.</Text>
      </div>
      {error ? <Banner status="error" title="답글 관계를 표시할 수 없습니다" description={error} />
        : !network ? <div className="hs-state"><Spinner label="답글 관계를 불러오는 중입니다" /></div>
        : (
          <Suspense fallback={<div className="hs-state"><Spinner label="그래프를 준비하는 중입니다" /></div>}>
            <CommentNetworkGraph network={network} onShowAuthor={onShowAuthor} />
          </Suspense>
        )}
    </section>
  );
}
