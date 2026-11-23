import { Banner } from "@astryxdesign/core/Banner";
import { Button } from "@astryxdesign/core/Button";
import { Collapsible } from "@astryxdesign/core/Collapsible";
import { EmptyState } from "@astryxdesign/core/EmptyState";
import { Heading } from "@astryxdesign/core/Heading";
import { Spinner } from "@astryxdesign/core/Spinner";
import { Text } from "@astryxdesign/core/Text";
import { TextInput } from "@astryxdesign/core/TextInput";
import { FileSearch, Link as LinkIcon } from "lucide-react";
import { type FormEvent, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { createJob, getAnalysisTiers, getPublicReports } from "../api";
import { errorMessage } from "../labels";
import { useSession } from "../session";
import type { AnalysisTier, PublicReportSummary } from "../types";
import { categoryLabel, formatNumber } from "../utils";

export function HomePage() {
  return (
    <div className="hs-page">
      <AnalysisForm />
      <SampleReports />
      <HowItWorks />
    </div>
  );
}

function AnalysisForm() {
  const navigate = useNavigate();
  const { session, signIn } = useSession();
  const [input, setInput] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tiers, setTiers] = useState<AnalysisTier[]>([]);
  const [tier, setTier] = useState<string | undefined>(undefined);
  const needsKey = Boolean(session && !session.api_keys_registered.anthropic);

  useEffect(() => {
    void getAnalysisTiers()
      .then((list) => { setTiers(list.items); setTier(list.default); })
      .catch(() => setTiers([]));
  }, []);

  const [resumeAfterLogin, setResumeAfterLogin] = useState(false);

  async function startJob() {
    setSubmitting(true);
    setError(null);
    try {
      const job = await createJob(input.trim(), tier);
      navigate(`/jobs/${job.job_id}`);
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setSubmitting(false);
    }
  }

  // Signing in happens in a popup; once the session arrives, carry on with the URL already typed.
  useEffect(() => {
    if (!resumeAfterLogin || !session) return;
    setResumeAfterLogin(false);
    if (session.api_keys_registered.anthropic) void startJob();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session, resumeAfterLogin]);

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!input.trim()) {
      setError("YouTube 영상 주소나 영상 ID를 입력해주세요.");
      return;
    }
    if (session === null) {
      setResumeAfterLogin(true);
      signIn();
      return;
    }
    if (needsKey) return;
    void startJob();
  }

  const submitLabel = session === null ? "Google 로그인 후 분석" : "분석 시작";

  return (
    <section className="hs-hero" aria-labelledby="home-title">
      <div className="hs-stack">
        <div className="hs-hero-brand">
          <img className="hs-logo" src="/favicon.svg" alt="" width={48} height={48} />
          <Heading level={1} type="display-1" id="home-title">HateScope</Heading>
        </div>
        <Text type="large" color="secondary" as="p">
          YouTube 댓글과 자막의 혐오표현을 한 줄씩 판정하고, 근거를 함께 보여줍니다.
        </Text>
      </div>

      {needsKey && (
        <Banner
          status="warning"
          title="분석하려면 Anthropic API 키가 필요합니다"
          description="댓글 판정에 쓰는 Claude 사용 요금은 등록한 키로 청구됩니다. 검색용 처리 비용은 서비스가 부담합니다."
          endContent={<Button size="sm" label="키 등록하기" href="/settings" />}
        />
      )}

      <form className="hs-analysis-form" onSubmit={submit} noValidate>
        <TextInput
          type="url"
          label="영상 주소"
          value={input}
          onChange={(value) => { setInput(value); if (error) setError(null); }}
          placeholder="https://youtu.be/… 또는 영상 ID"
          startIcon={LinkIcon}
          size="lg"
          isDisabled={submitting}
          status={error ? { type: "error", message: error } : undefined}
          statusVariant="detached"
        />
        {tiers.length > 0 && <TierPicker tiers={tiers} value={tier} onChange={setTier} disabled={submitting} />}
        <div className="hs-form-action">
          <Button type="submit" variant="primary" size="lg" label={submitLabel} isLoading={submitting} isDisabled={needsKey || session === undefined} />
          {session === null && <Text type="supporting">로그인 창에서 로그인하면 입력한 주소로 바로 분석을 시작합니다.</Text>}
        </div>
      </form>
    </section>
  );
}

export function TierPicker({ tiers, value, onChange, disabled }: { tiers: AnalysisTier[]; value?: string; onChange: (key: string) => void; disabled: boolean }) {
  const accuracies = tiers.map((tier) => tier.benchmark_accuracy);
  const sameAccuracy = tiers.length > 1 && accuracies.every((value) => value !== null && value === accuracies[0]) ? accuracies[0] : null;
  const costs = tiers.map((tier) => tier.usd_per_1000_comments).filter((value): value is number => value !== null);
  const maxCost = costs.length ? Math.max(...costs) : null;
  return (
    <fieldset className="hs-tier-picker" disabled={disabled}>
      <legend><Text type="label">분석 방식</Text></legend>
      <div className="hs-tier-options">
        {tiers.map((tier) => {
          const cost = tier.usd_per_1000_comments;
          const saving = cost !== null && maxCost && cost < maxCost ? Math.round((1 - cost / maxCost) * 100) : 0;
          return (
            <label key={tier.key} className="hs-tier-option" data-selected={tier.key === value || undefined}>
              <input type="radio" name="analysis-tier" value={tier.key} checked={tier.key === value} onChange={() => onChange(tier.key)} />
              <span className="hs-tier-head">
                <Text weight="semibold" size="lg">{tier.label}</Text>
                {saving > 0 && <Text type="supporting" weight="medium">약 {saving}% 저렴</Text>}
              </span>
              {cost !== null && <Text weight="semibold">댓글 1,000개당 약 ${cost.toFixed(2)}</Text>}
              <Text type="supporting">{tierMethod(tier)}</Text>
              <Text type="supporting" size="sm">{tier.model_label}{sameAccuracy === null && tier.benchmark_accuracy !== null ? ` · 정확도 ${Math.round(tier.benchmark_accuracy * 100)}%` : ""}</Text>
            </label>
          );
        })}
      </div>
      {sameAccuracy !== null && <p className="hs-note">두 방식의 정확도는 같습니다({Math.round(sameAccuracy * 100)}%). 비용과 처리 방식만 다릅니다.</p>}
      <Collapsible defaultIsOpen={false} trigger={<Text type="label">분석은 어떻게 처리되나요?</Text>}>
        <div className="hs-stack hs-collapsible-body">
          <ol className="hs-list">
            <li>영상의 댓글·답글과 공개 자막을 모읍니다.</li>
            <li>댓글마다 혐오표현 유형 정의, 법령과 심의 기준(방송통신심의위원회·국가인권위원회 등), 비슷한 사례를 찾습니다.</li>
            <li>선택한 AI 모델이 찾은 근거를 참고해 혐오 여부와 유형을 판정합니다. 절약 방식에서는 가벼운 모델(Jev)이 확실히 문제없는 댓글을 먼저 걸러내고, 나머지만 AI가 판정합니다.</li>
          </ol>
          <p className="hs-note">비용은 등록한 Anthropic 키로 청구되며, 댓글 길이에 따라 달라지는 추정치입니다. 정확도는 학습에 쓰지 않은 공개 데이터 970건(K-HATERS·BEEP)으로 잰 값이라 실제 YouTube 댓글에서는 다를 수 있습니다.</p>
        </div>
      </Collapsible>
    </fieldset>
  );
}

/** One plain line on how the tier works; the server summary is longer and uses older wording. */
function tierMethod(tier: AnalysisTier): string {
  return tier.jev_prefilter
    ? "확실히 문제없는 댓글은 가벼운 모델이 먼저 걸러내고, 나머지만 AI가 판정합니다."
    : "모든 댓글을 AI가 판정합니다.";
}

function SampleReports() {
  const [reports, setReports] = useState<PublicReportSummary[] | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let active = true;
    getPublicReports()
      .then((page) => { if (active) setReports(page.items); })
      .catch(() => { if (active) { setReports([]); setFailed(true); } });
    return () => { active = false; };
  }, []);

  return (
    <section className="hs-section" id="samples" aria-labelledby="samples-title">
      <div className="hs-section-header">
        <Heading level={2} id="samples-title">공개 샘플 보고서</Heading>
        <Text type="supporting">로그인 없이 결과 예시를 볼 수 있습니다.</Text>
      </div>
      {reports === null ? (
        <div className="hs-state"><Spinner label="샘플 보고서를 불러오는 중입니다" /></div>
      ) : failed ? (
        <Banner status="error" title="샘플 목록을 불러오지 못했습니다" description="잠시 후 다시 시도해주세요." />
      ) : reports.length === 0 ? (
        <EmptyState title="아직 공개된 샘플이 없습니다" description="운영자 검토를 마친 보고서가 여기에 표시됩니다." icon={<FileSearch size={28} aria-hidden />} />
      ) : (
        <ul className="hs-job-list hs-job-list--keep-end">{reports.map((report) => <SampleCard report={report} key={report.report_id} />)}</ul>
      )}
    </section>
  );
}

function SampleCard({ report }: { report: PublicReportSummary }) {
  return (
    <li>
      <Link className="hs-job-row" to={`/reports/${report.report_id}`}>
        <span className="hs-thumb hs-thumb--xs">{report.thumbnail_url ? <img src={report.thumbnail_url} alt="" /> : <FileSearch size={20} aria-hidden />}</span>
        <span className="hs-job-main">
          <Text weight="semibold" maxLines={1}>{report.title}</Text>
          <Text type="supporting">
            {report.channel_title ?? report.youtube_video_id ?? "YouTube 영상"}, 댓글 {formatNumber(report.comments_collected)}개
            {report.top_categories.length > 0 ? `, 많은 유형: ${report.top_categories.slice(0, 2).map(categoryLabel).join(", ")}` : ""}
          </Text>
        </span>
        <span className="hs-job-status">
          <Text weight="semibold" hasTabularNumbers>{report.hate_speech_ratio.toFixed(1)}%</Text>
          <Text type="supporting">혐오표현</Text>
        </span>
      </Link>
    </li>
  );
}

function HowItWorks() {
  const items = [
    { title: "세 가지 근거로 판단", body: "분류 기준, 법령과 심의 기준, 사람이 판정해 둔 비슷한 사례를 각각 찾아 판정 근거로 함께 보여줍니다." },
    { title: "한 줄씩 판정", body: "댓글 하나, 자막 한 구간씩 따로 판정해 영상 안과 밖의 표현을 구분합니다." },
    { title: "답글 관계", body: "누가 누구에게 답글을 달았는지 네트워크로 그려, 대화가 어디에 몰렸는지 볼 수 있습니다." },
  ];
  return (
    <section className="hs-section" aria-labelledby="how-title">
      <Heading level={2} id="how-title">판정 방식</Heading>
      <div className="hs-feature-list">
        {items.map((item) => (
          <div key={item.title} className="hs-stack hs-stack--tight">
            <Heading level={3}>{item.title}</Heading>
            <Text type="supporting" as="p">{item.body}</Text>
          </div>
        ))}
      </div>
      <p className="hs-note">AI 판정은 법적 판단이 아니며, 작성자의 성향이나 의도를 진단하지 않습니다. 모을 수 있는 공개 데이터와 명시한 분류 기준 안에서만 해석해주세요.</p>
    </section>
  );
}
