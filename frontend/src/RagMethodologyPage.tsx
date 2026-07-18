import {
  BookOpenCheck,
  Boxes,
  CheckCircle2,
  Code2,
  Database,
  GitBranch,
  Network,
  Scale,
  ServerCog,
  ShieldAlert,
  TriangleAlert,
  Users,
} from "lucide-react";
import type { ReactNode } from "react";

import { RagPipelineFlow } from "./RagPipelineFlow";

const TAXONOMY_GROUPS = [
  {
    title: "보호 속성·표현 방식",
    description: "공격의 근거가 되는 보호 속성과 공격의 표현 방식을 구분합니다. 욕설은 표적 범주와 함께 판단할 수 있습니다.",
    cards: [
      { label: "성별", definition: "성별·성역할·임신·출산·가족 역할을 이유로 한 공격", include: "성별 집단의 열등성 일반화, 성별에 근거한 배제·폭력", exclude: "성별 통계·정책 토론, 개인 행동 비판. 성적지향·성별정체성은 정체성 범주" },
      { label: "연령", definition: "나이·연령대·세대 소속을 이유로 한 공격", include: "세대 전체의 무능·해악 일반화, 연령에 따른 권리 배제", exclude: "연령별 특성 설명, 세대 정책·이해관계 비판" },
      { label: "정체성", definition: "지역·인종·민족·국적·종교·성적지향·성별정체성·장애를 이유로 한 공격", include: "보호 집단 비인간화, 추방·차별·폭력 주장, 집단 멸칭", exclude: "문화·종교 정보, 정치 이념·정당 지지층 공격" },
      { label: "욕설", definition: "대상에게 직접 향하는 욕설·비속어·외설적 모욕이라는 표현 방식", include: "직접 욕설·멸칭, 다른 범주의 공격을 강화하는 비속어", exclude: "비판 목적의 인용, 대상 없는 단순 감탄. 표적이 없으면 대상 없음 범주를 함께 검토" },
    ],
  },
  {
    title: "정치적 표적 2축",
    description: "먼저 국가/비국가를 구분하고, 이어 권위체/제도/공동체를 구분합니다. 정치적 반대나 정책 비판만으로는 혐오가 아닙니다.",
    cards: [
      { label: "국가 권위체", definition: "국가기관·법률상 공직자를 직무 주체로 표적화", include: "정부·국회·법원·경찰·공직자 집단 모욕, 제거·폭력 선동", exclude: "결정·수사·판결 비판. 법·절차 자체는 국가 제도 범주" },
      { label: "비국가 권위체", definition: "정당·후보·언론·기업·시민단체 등 조직과 지도자를 표적화", include: "조직·지도자 집단 모욕, 위협·제거 선동", exclude: "공약·보도 비판. 지지자·구성원은 비국가 공동체 범주" },
      { label: "국가 제도", definition: "법·정책·선거·사법·행정 제도와 공식 절차를 표적화", include: "국가 제도 전체의 악성 일반화, 폭력적 파괴 선동", exclude: "정책 효과·위헌성 비판과 개정 요구" },
      { label: "비국가 제도", definition: "비국가 조직의 규칙·절차·운영 체계를 표적화", include: "경선·공천·편집·플랫폼 규칙 전체의 악성 일반화와 파괴 선동", exclude: "불공정성 비판과 개선 요구. 조직 자체는 비국가 권위체 범주" },
      { label: "국가 공동체", definition: "국민·시민·유권자라는 정치적 구성원 지위를 표적화", include: "국가 구성원 전체의 무가치 일반화, 권리 박탈·배제 주장", exclude: "여론·투표 결과 비판. 국적·민족 공격은 정체성 범주" },
      { label: "비국가 공동체", definition: "정당 지지층·정치 팬덤·이념 집단·운동 진영을 표적화", include: "지지자 전체의 열등성·위험성 일반화, 추방·폭력 주장", exclude: "특정 주장·시위 행동 비판. 정당·후보 자체는 비국가 권위체 범주" },
    ],
  },
  {
    title: "표적·잔여 판단",
    description: "표적 식별 가능성과 기존 범주의 설명 가능성을 확인한 뒤에만 사용합니다.",
    cards: [
      { label: "대상 없음", definition: "공격 강도는 있으나 수집 문맥에서 표적을 식별할 수 없음", include: "선행 대상 없는 단독 욕설·불특정 위협", exclude: "구체적인 표적 범주와 함께 사용하지 않음" },
      { label: "기타", definition: "공통 판정 기준은 충족하지만 현재 범주로 표적 근거를 표현할 수 없음", include: "직업·외모·경제적 지위 등 미정의 속성에 대한 심각한 공격", exclude: "기존 범주로 설명 가능하거나 표적이 없는 사례" },
      { label: "비혐오·미분류", definition: "비혐오이거나 인용·비판·정보 전달로 공통 판정 기준을 충족하지 않음", include: "행위·정책 비판, 비동조 인용, 중립 정보, 공격으로 확정하기 어려운 표현", exclude: "혐오표현으로 판단할 충분한 근거가 있는 사례" },
    ],
  },
] as const;

export function RagMethodologyPage() {
  return (
    <div className="page-wrap rag-method-page">
      <header className="rag-method-header">
        <div>
          <span className="rag-kicker">METHODOLOGY · RESPONSIBLE AI</span>
          <h1>Three-Vector RAG 분류 파이프라인</h1>
          <p>댓글, 답글, 스크립트 세그먼트를 분류 체계, 공식 기준, 유사 사례라는 서로 다른 근거로 검색하고 분류합니다.</p>
        </div>
        <div className="rag-badges">
          <span>Three Evidence</span>
          <span>설명 가능한 판정</span>
          <span>책임 있는 해석</span>
        </div>
      </header>

      <MethodSection number="01" title="호출 파이프라인" icon={<GitBranch size={18} />}>
        <p className="section-intro">데이터 수집부터 세 종류의 근거 검색, 분류 검증, 네트워크 분석과 보고서 생성까지의 흐름을 보여줍니다.</p>
        <RagPipelineFlow />
      </MethodSection>

      <MethodSection number="02" title="Evidence stores" icon={<Database size={18} />}>
        <div className="evidence-grid">
          <EvidenceCard
            icon={<BookOpenCheck size={22} />}
            title="분류 체계"
            subtitle="출력 규칙"
            rows={[["역할", "범주 경계 제공"], ["구성", "정의·경계·예외"], ["효과", "일관성 향상"]]}
          >
            허용 범주, 포함·제외 기준과 인접 범주의 경계를 검색해 결과 형식을 안정화합니다.
          </EvidenceCard>
          <EvidenceCard
            icon={<Scale size={22} />}
            title="공식 기준"
            subtitle="권위 근거"
            rows={[["역할", "외부 기준 제공"], ["구성", "정책·가이드"], ["효과", "기준 순환 완화"]]}
          >
            공식·권위 문서의 판단 요건과 보호 속성 기준을 별도로 검색해 내부 분류 체계에 치우치지 않도록 합니다.
          </EvidenceCard>
          <EvidenceCard
            icon={<Boxes size={22} />}
            title="유사 분석 사례"
            subtitle="경험적 근거"
            rows={[["역할", "비교 사례 제공"], ["선별", "관련성 검토"], ["효과", "경계 사례 보완"]]}
            accent
          >
            입력과 의미적으로 가까운 분석 사례를 참고합니다. 사례는 판단을 돕는 비교 근거이며 정답으로 간주하지 않습니다.
          </EvidenceCard>
        </div>
        <div className="context-behavior">
          <ShieldAlert size={18} />
          <p><strong>근거 중심 설계:</strong> 서로 다른 성격의 근거를 결합하되, 검색 결과를 사실의 증명이나 자동화된 최종 판단으로 취급하지 않습니다.</p>
        </div>
      </MethodSection>

      <div className="method-two-column">
        <MethodSection number="03" title="판정 원칙" icon={<Code2 size={18} />}>
          <ul className="validation-list">
            <li><CheckCircle2 size={15} /> 먼저 혐오 여부를 판단한 뒤 세부 범주를 구분합니다.</li>
            <li><CheckCircle2 size={15} /> 정책·행위 비판과 집단 자체에 대한 공격을 구별합니다.</li>
            <li><CheckCircle2 size={15} /> 인용, 보도, 풍자와 반박의 문맥을 함께 고려합니다.</li>
            <li><CheckCircle2 size={15} /> 판단 근거를 사람이 읽을 수 있는 한국어로 요약합니다.</li>
          </ul>
          <p className="method-note">세부 프롬프트와 모델 설정은 운영 정보이므로 공개하지 않습니다.</p>
        </MethodSection>

        <MethodSection number="04" title="결과 검증" icon={<ShieldAlert size={18} />}>
          <ul className="validation-list">
            <li><CheckCircle2 size={15} /> 정해진 결과 구조와 범주 조합 규칙을 확인합니다.</li>
            <li><CheckCircle2 size={15} /> 비혐오 판정과 혐오 범주가 충돌하지 않도록 검사합니다.</li>
            <li><CheckCircle2 size={15} /> 형식 검증에 실패한 결과는 교정 절차를 거칩니다.</li>
            <li><CheckCircle2 size={15} /> 실패한 분석도 숨기지 않고 작업 상태에 반영합니다.</li>
          </ul>
        </MethodSection>
      </div>

      <MethodSection number="05" title="Taxonomy 판정 가이드" icon={<Boxes size={18} />}>
        <div className="taxonomy-threshold">
          <strong>공통 판정 기준</strong>
          <p>대상의 정체성·소속·지위를 근거로 한 <b>열등성 일반화, 비인간화, 배제·차별, 위협·폭력, 제거·억압 선동, 심각한 직접 모욕</b> 중 하나 이상이 있어야 합니다. 불쾌함, 반대, 풍자, 사실 서술, 정책·행위 비판만으로는 혐오로 분류하지 않습니다.</p>
          <p><b>문맥 예외:</b> 보도·연구·교육·반박 목적으로 혐오표현을 인용하고 화자가 동조하지 않으면 비혐오입니다. 풍자·반어의 실제 표적이나 태도를 확정할 수 없으면 비혐오·미분류로 판단합니다.</p>
        </div>
        <div className="taxonomy-groups">
          {TAXONOMY_GROUPS.map((group) => (
            <section className="taxonomy-group" key={group.title}>
              <div className="taxonomy-group-header"><h3>{group.title}</h3><p>{group.description}</p></div>
              <div className="taxonomy-card-grid">
                {group.cards.map((card) => (
                  <article className="taxonomy-card" key={card.label}>
                    <header><strong>{card.label}</strong></header>
                    <p>{card.definition}</p>
                    <dl>
                      <div><dt>포함 기준</dt><dd>{card.include}</dd></div>
                      <div><dt>제외·경계</dt><dd>{card.exclude}</dd></div>
                    </dl>
                  </article>
                ))}
              </div>
            </section>
          ))}
        </div>
      </MethodSection>

      <MethodSection number="06" title="사회과학적 해석 단위" icon={<Users size={18} />}>
        <p className="section-intro">모델의 판정은 개인의 본질이나 의도를 규정하는 값이 아니라, 수집된 시점의 발화와 답글 관계를 관찰 가능한 지표로 바꾼 결과입니다.</p>
        <div className="social-lens-grid">
          <article><Code2 size={20} /><h3>분석 단위</h3><p>기본 단위는 댓글·답글·자막이라는 <strong>발화</strong>입니다. 자막은 문장 경계를 우선하고 시간·길이 상한을 보조 기준으로 삼습니다. 작성자 단위 수치는 발화 결과를 집계한 값이며 개인의 성향 진단이 아닙니다.</p></article>
          <article><Scale size={20} /><h3>개념의 조작화</h3><p>혐오표현 개념을 13개 범주와 정치적 대상 축으로 조작화합니다. 각 범주는 분석 도구이지 사회집단의 고정된 속성이 아닙니다.</p></article>
          <article><Network size={20} /><h3>관계적 맥락</h3><p>답글 edge와 연결 구조는 상호작용의 집중을 보여줍니다. 연결 자체가 동조·설득·영향 또는 혐오의 전파를 입증하지는 않습니다.</p></article>
          <article><BookOpenCheck size={20} /><h3>근거의 역할</h3><p>검색된 정의와 유사 사례는 판정 경로를 감사하기 위한 근거입니다. 검색 유사도나 모델의 한국어 사유를 사실의 증명으로 취급하지 않습니다.</p></article>
        </div>
      </MethodSection>

      <MethodSection number="07" title="타당도·윤리·주장의 경계" icon={<TriangleAlert size={18} />}>
        <div className="interpretation-boundary"><ShieldAlert size={20} /><p><strong>기술통계의 범위:</strong> 이 보고서는 수집 가능한 공개 댓글 표본을 기술합니다. 모집단 대표성이나 인과관계, 작성자의 고정된 정체성·의도를 추론하지 않습니다.</p></div>
        <div className="scope-table-wrap">
          <table className="scope-table">
            <thead><tr><th>산출값</th><th>해석할 수 있는 것</th><th>주장하면 안 되는 것</th></tr></thead>
            <tbody>
              <tr><th>혐오 댓글 비율</th><td>수집·분석에 성공한 발화 중 모델 판정 비율</td><td>YouTube 전체 또는 사회 전체의 혐오 수준</td></tr>
              <tr><th>카테고리 분포</th><td>모델이 판정한 혐오 발화 내부의 상대적 구성</td><td>특정 집단이 객관적으로 더 공격받는다는 일반화</td></tr>
              <tr><th>답글 빈도·edge</th><td>수집된 답글 관계의 반복과 혐오 발화 포함 정도</td><td>노출, 동조, 설득 또는 혐오 확산의 인과효과</td></tr>
              <tr><th>연결도·중심성</th><td>수집된 댓글 subgraph 안에서의 구조적 위치</td><td>실제 영향력, 극단성, 조직성 또는 개인의 의도</td></tr>
              <tr><th>RAG 사유·근거</th><td>모델 판정이 참조한 설명과 사례의 추적 가능성</td><td>법적 판단, 객관적 진실 또는 사람 검토의 대체</td></tr>
            </tbody>
          </table>
        </div>
        <div className="validity-grid">
          <article><strong>구성타당도</strong><p>taxonomy가 풍자, 은어, 교차정체성처럼 개념의 모든 양상을 포괄하지 못할 수 있습니다.</p></article>
          <article><strong>선택 편향</strong><p>삭제·비공개·수집 누락 댓글은 관찰되지 않으므로 공개 표본을 전체 이용자로 일반화하지 않습니다.</p></article>
          <article><strong>측정 오차</strong><p>방언, 반어, 인용, 맥락 부족에 따라 집단별 오분류율이 달라질 수 있어 사람 표본 검토가 필요합니다.</p></article>
          <article><strong>시간 비교</strong><p>판정 기준·근거 자료·플랫폼 정책을 고정하지 않은 시점 간 증감은 실제 사회 변화와 구분하기 어렵습니다.</p></article>
          <article><strong>인과관계</strong><p>현재 파이프라인은 기술·탐색 분석입니다. 네트워크 연결과 혐오 판정만으로 원인이나 전파 효과를 추정하지 않습니다.</p></article>
          <article><strong>연구 윤리</strong><p>작성자 식별자는 최소화·가명화하고 결과를 개인 제재나 자동 의사결정의 단독 근거로 사용하지 않습니다.</p></article>
        </div>
      </MethodSection>

      <MethodSection number="08" title="운영 품질 관리" icon={<ServerCog size={18} />}>
        <ol className="reproduction-grid">
          <ReproStep number="01" title="근거 자료 관리">출처와 이용 조건이 확인된 정의·사례 자료만 사용합니다.</ReproStep>
          <ReproStep number="02" title="변경 이력 관리">판정 기준과 근거 자료의 변경을 기록해 결과를 비교할 수 있게 합니다.</ReproStep>
          <ReproStep number="03" title="자동 검증">결과 형식, 범주 충돌과 누락 여부를 자동으로 점검합니다.</ReproStep>
          <ReproStep number="04" title="실패 추적">수집·검색·분류 실패를 단계별로 기록하고 부분 성공을 구분합니다.</ReproStep>
          <ReproStep number="05" title="표본 검토">정확도와 편향을 확인하기 위해 사람이 정기적으로 표본을 검토합니다.</ReproStep>
          <ReproStep number="06" title="해석 범위 고지">보고서가 설명할 수 있는 범위와 한계를 결과와 함께 제공합니다.</ReproStep>
        </ol>
      </MethodSection>
    </div>
  );
}

function MethodSection({ number, title, icon, children }: { number: string; title: string; icon: ReactNode; children: ReactNode }) {
  return (
    <section className="method-section panel">
      <div className="method-section-title"><span>{number}</span>{icon}<h2>{title}</h2></div>
      <div className="method-section-body">{children}</div>
    </section>
  );
}

function EvidenceCard({ icon, title, subtitle, rows, accent = false, children }: { icon: ReactNode; title: string; subtitle: string; rows: readonly (readonly [string, string])[]; accent?: boolean; children: ReactNode }) {
  return (
    <article className={`evidence-card ${accent ? "accent" : ""}`}>
      <div className="evidence-title"><span>{icon}</span><div><h3>{title}</h3><small>{subtitle}</small></div></div>
      <p>{children}</p>
      <dl>{rows.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>
    </article>
  );
}

function ReproStep({ number, title, children }: { number: string; title: string; children: ReactNode }) {
  return <li><span>{number}</span><div><strong>{title}</strong><p>{children}</p></div></li>;
}
