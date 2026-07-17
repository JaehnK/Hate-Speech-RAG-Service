import { ArrowRight, BarChart3, FileSearch, LogIn, Network, ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { getPublicReports } from "./api";
import type { PublicReportSummary } from "./types";
import { categoryLabel, formatDate, formatNumber } from "./utils";

export function PublicHomePage() {
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
    <div className="public-home">
      <header className="public-header">
        <Link className="brand" to="/">SENTINEL-YT</Link>
        <nav aria-label="공개 메뉴"><a href="#samples">공개 샘플</a><Link to="/rag-methodology">RAG 방법론</Link><a href="#principles">해석 원칙</a></nav>
        <a className="google-login" href="/api/auth/google/login?return_to=/analyze"><LogIn size={17} /> Google로 로그인</a>
      </header>
      <main>
        <section className="public-hero">
          <div>
            <span className="eyebrow">Evidence before sign-in</span>
            <h1>로그인 전에,<br />분석 결과를 먼저 확인하세요</h1>
            <p>공개 댓글과 자막을 발화 단위로 분류하고, 정의 문서와 유사 사례를 근거로 연결합니다. 운영자가 검토한 실제 샘플 보고서는 로그인 없이 열 수 있습니다.</p>
            <div className="public-actions"><a className="google-login primary" href="/api/auth/google/login?return_to=/analyze">새 분석 시작 <ArrowRight size={17} /></a><a href="#samples">샘플 둘러보기</a></div>
          </div>
          <div className="preview-card" aria-label="분석 보고서 구성 미리보기">
            <header><span>REPORT PREVIEW</span><ShieldCheck size={20} /></header>
            <div className="preview-metric"><strong>발화 단위 분석</strong><small>댓글 · 대댓글 · 공개 자막</small></div>
            <div className="preview-bars"><i /><i /><i /><i /></div>
            <div className="preview-features"><span><BarChart3 />카테고리 분포</span><span><Network />상호작용 네트워크</span></div>
          </div>
        </section>

        <section className="sample-section" id="samples">
          <div className="public-section-title"><div><small>PUBLIC REPORTS</small><h2>공개 샘플 보고서</h2></div><p>표시되는 자료는 운영자가 공개 범위를 검토한 보고서입니다.</p></div>
          {reports === null ? <div className="sample-state">샘플 보고서를 불러오는 중입니다.</div> : failed ? <div className="sample-state error">샘플 목록을 불러오지 못했습니다. 잠시 후 다시 시도해주세요.</div> : reports.length === 0 ? <div className="sample-state"><FileSearch size={30} /><strong>현재 공개된 샘플이 없습니다.</strong><span>운영자 검토가 완료된 보고서가 여기에 표시됩니다.</span></div> : (
            <div className="sample-grid">{reports.map((report) => <SampleCard report={report} key={report.report_id} />)}</div>
          )}
        </section>

        <section className="public-principles" id="principles">
          <article><strong>01</strong><h3>이중 근거 검색</h3><p>혐오표현 정의와 유사 판정 사례를 분리 검색해 문맥과 기준을 함께 제시합니다.</p></article>
          <article><strong>02</strong><h3>발화 단위 분석</h3><p>댓글과 공개 자막을 각각 분석해 영상 안팎의 표현 양상을 구분합니다.</p></article>
          <article><strong>03</strong><h3>상호작용 구조</h3><p>답글 관계를 네트워크로 구성해 빈도와 연결 구조를 탐색할 수 있습니다.</p></article>
          <aside>모델 판정은 법적 판단이나 개인의 성향·의도를 진단하는 결과가 아닙니다. 수집 가능한 공개 데이터와 명시된 분류 기준 안에서 해석해야 합니다.</aside>
        </section>
      </main>
    </div>
  );
}

function SampleCard({ report }: { report: PublicReportSummary }) {
  return (
    <article className="sample-card">
      <div className="sample-thumbnail">{report.thumbnail_url ? <img src={report.thumbnail_url} alt="" /> : <FileSearch size={32} />}<span>운영자 검토 공개본</span></div>
      <div className="sample-body">
        <small>{formatDate(report.created_at)}</small><h3>{report.title}</h3><p>{report.channel_title ?? report.youtube_video_id ?? "YouTube 영상"}</p>
        <dl><div><dt>수집 댓글</dt><dd>{formatNumber(report.comments_collected)}</dd></div><div><dt>혐오표현</dt><dd>{report.hate_speech_ratio.toFixed(1)}%</dd></div><div><dt>공개 자막</dt><dd>{report.transcript_available ? "분석" : "없음"}</dd></div></dl>
        <div className="sample-categories">{report.top_categories.map((category) => <span key={category}>{categoryLabel(category)}</span>)}</div>
        <Link to={`/reports/${report.report_id}`}>보고서 열기 <ArrowRight size={16} /></Link>
      </div>
    </article>
  );
}
