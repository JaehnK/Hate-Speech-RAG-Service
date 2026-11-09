import {
  BookOpenCheck,
  Boxes,
  CheckCircle2,
  Code2,
  Cpu,
  Database,
  GitBranch,
  Network,
  Scale,
  ServerCog,
  ShieldAlert,
  TriangleAlert,
  Users,
} from "lucide-react";
import { type ReactNode, useEffect, useState } from "react";

import { getMethodology } from "./api";
import { RagPipelineFlow } from "./RagPipelineFlow";
import type { Methodology } from "./types";

const TAXONOMY_GROUPS = [
  {
    title: "누구를 왜 공격했나",
    description: "성별·연령·출신 같은 속성을 이유로 한 공격과, 욕설이라는 표현 방식을 나눠 봅니다. 욕설은 다른 범주와 함께 붙을 수 있습니다.",
    cards: [
      { label: "성별 비하", definition: "성별·성역할·임신·출산·가족 역할을 이유로 깎아내림", include: "여성·남성 집단을 싸잡아 열등하다고 말함, 성별을 이유로 배제·폭력 정당화", exclude: "성별 통계·정책 토론, 성별과 무관한 개인 행동 비판" },
      { label: "연령 비하", definition: "나이·세대를 이유로 깎아내림", include: "특정 세대 전체를 무능·해롭다고 일반화, 나이를 이유로 참여 배제", exclude: "연령별 특성 설명, 세대 정책 비판" },
      { label: "출신·인종·종교·장애 등 비하", definition: "출신지역·인종·국적·종교·성적지향·성별정체성·장애를 이유로 깎아내림", include: "집단 멸칭, 추방·차별·폭력 주장, 비인간화", exclude: "문화·종교 정보, 정치 성향 집단 공격(→ 지지층·진영 비하)" },
      { label: "욕설·모욕·기타 공격", definition: "사람이나 집단을 향한 욕설·모욕·조롱, 그리고 위 범주에 없는 대상(연예인 등 개인, 직업·외모 집단)에 대한 공격", include: "직접 욕설·멸칭, 깎아내리려는 의도가 분명한 개인 조롱, 직업·외모 집단 비하", exclude: "비판 목적의 인용, 가벼운 감상·아쉬움 표현, 모욕 없는 비판" },
    ],
  },
  {
    title: "정치적 공격: 두 가지 질문",
    description: "① 무엇을 겨냥했나? 기관·인물 / 법·제도 / 사람들 무리. ② 공적인 쪽인가, 민간인가? 이 두 답의 조합으로 여섯 범주 중 하나를 고릅니다. 정책 비판이나 강한 반대만으로는 혐오가 아닙니다.",
    cards: [
      { label: "정부·공직자 공격", definition: "① 기관·인물 × ② 공적: 정부·국회·법원·검찰·경찰, 대통령·장관·판사", include: "국가기관·공직자 집단 모욕, 위협·제거 선동", exclude: "결정·수사·판결에 대한 근거 있는 비판" },
      { label: "정당·정치인·언론 공격", definition: "① 기관·인물 × ② 민간: 정당, 정치인·후보, 언론사, 시민단체", include: "조직·지도자를 싸잡아 모욕, 위협", exclude: "공약·보도 내용 비판. 지지자 공격은 지지층·진영 비하" },
      { label: "법·제도 공격", definition: "① 법·제도 × ② 공적: 법, 정책, 선거·재판·행정 제도", include: "제도 전체를 모욕하거나 파괴하자고 선동", exclude: "정책 효과·위헌성 비판과 개정 요구" },
      { label: "정당·단체 운영방식 공격", definition: "① 법·제도 × ② 민간: 공천·경선, 언론 편집 방침, 단체 내부 규칙", include: "내부 절차 전체를 모욕하거나 파괴하자고 선동", exclude: "절차의 불공정성 비판과 개선 요구" },
      { label: "국민 전체 비하", definition: "① 사람들 무리 × ② 공적: 국민·시민·유권자 전체", include: "국민 전체를 싸잡아 무능·무가치하다고 비하", exclude: "여론·투표 결과 비판. 국적·민족 공격은 출신·인종 비하" },
      { label: "지지층·진영 비하", definition: "① 사람들 무리 × ② 민간: 정당 지지자, 정치 팬덤, 좌·우 진영", include: "지지자 전체를 열등·위험하다고 일반화, 멸칭", exclude: "특정 주장·시위 행동 비판" },
    ],
  },
  {
    title: "대상이 불분명하거나 혐오가 아닌 경우",
    description: "누구를 겨냥했는지 알 수 없거나, 판정 기준을 충족하지 않을 때 사용합니다. 위 범주에 맞지 않는 대상에 대한 공격은 욕설·모욕·기타 공격으로 분류합니다.",
    cards: [
      { label: "대상 없는 욕설", definition: "욕설·공격은 분명하지만 누구를 겨냥했는지 알 수 없음", include: "대상 없이 단독으로 쓴 강한 욕설", exclude: "대상이 드러난 경우" },
      { label: "혐오 아님", definition: "판정 기준을 충족하지 않음", include: "모욕 없는 비판, 동조하지 않는 인용·보도, 중립 정보", exclude: "사람·집단을 향한 모욕·조롱·욕설" },
    ],
  },
] as const;

export function RagMethodologyPage() {
  const [methodology, setMethodology] = useState<Methodology | null | undefined>(undefined);
  useEffect(() => {
    let active = true;
    getMethodology().then((value) => { if (active) setMethodology(value); }).catch(() => { if (active) setMethodology(null); });
    return () => { active = false; };
  }, []);

  return (
    <div className="page-wrap rag-method-page">
      <header className="rag-method-header">
        <div>
          <span className="rag-kicker">METHODOLOGY · RESPONSIBLE AI</span>
          <h1>Three-Vector RAG 분류 파이프라인</h1>
          <p>댓글, 답글, 스크립트 세그먼트를 분류 체계, 규범·기준 문서, 유사 사례라는 서로 다른 근거로 검색하고 분류합니다.</p>
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
            rows={[["구성", "카드 21개 (판정 기준·범주·경계)"], ["검색", "4개 + 고정 2개"], ["효과", "판정 기준 일관성"]]}
          >
            혐오 여부를 가르는 판정 기준 카드와 문맥 예외 카드는 매번 고정으로 넣고, 입력과 관련된 범주 정의·경계 카드 4개를 더 검색합니다.
          </EvidenceCard>
          <EvidenceCard
            icon={<Scale size={22} />}
            title="규범·기준 문서"
            subtitle="판정 근거"
            rows={[["국내", "정보통신망법·방미심위 심의규정·형법·인권위"], ["국제", "Rabat·UN·유럽·해외 법제 요약"], ["기타", "YouTube 정책·데이터셋 라벨 기준"]]}
          >
            출처 17개를 조항 단위 58개로 나눠 담았습니다. 유사 사례의 라벨을 참고해 관련 범주의 기준 문서를 문서 종류별로 골라 검색하고, 판정 근거로 조항을 인용합니다. 혐오 여부의 기준은 분류 체계가 정하며, 법령 기준은 가장 심각한 수준만 표시한다는 점을 함께 고려합니다.
          </EvidenceCard>
          <EvidenceCard
            icon={<Boxes size={22} />}
            title="유사 분석 사례"
            subtitle="경험적 근거"
            rows={[["규모", "공개 라벨 데이터 172,157건"], ["검색", "가장 가까운 6건"], ["역할", "판정 보정 + 규범 문서 안내"]]}
            accent
          >
            입력과 의미적으로 가까운 라벨링 사례를 가장 먼저 검색합니다. 사례는 판단을 돕는 비교 근거이며 정답으로 간주하지 않습니다.
          </EvidenceCard>
        </div>
        <ol className="retrieval-order">
          <li><strong>1. 유사 사례 먼저</strong><span>입력과 가장 가까운 라벨링 사례 6건을 찾습니다.</span></li>
          <li><strong>2. 사례가 가리키는 범주 확인</strong><span>사례 2건 이상이 공유하는 범주(예: 성별 비하, 지지층 비하)를 뽑습니다.</span></li>
          <li><strong>3. 그 범주의 규범 문서 검색</strong><span>국내 법령·심의규정 2, 인권위 기준 1, 플랫폼 정책 1은 해당 범주로 좁혀 찾고, 국제 기준 요약 1과 데이터셋 라벨 기준 2는 범주 제한 없이 찾습니다.</span></li>
          <li><strong>4. 판정과 인용</strong><span>모델이 판정 기준 카드에 따라 혐오 여부와 범주를 정하고, 실제로 근거가 된 조항을 보고서에 인용합니다.</span></li>
        </ol>
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
          <p className="method-note">실제 프롬프트 전문과 사용 모델은 아래 "모델과 프롬프트"에 공개합니다.</p>
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

      <MethodSection number="05" title="모델과 프롬프트" icon={<Cpu size={18} />}>
        <ModelsAndPrompt methodology={methodology} />
      </MethodSection>

      <MethodSection number="06" title="Taxonomy 판정 가이드" icon={<Boxes size={18} />}>
        <div className="taxonomy-threshold">
          <strong>공통 판정 기준</strong>
          <p>이 서비스는 두 가지를 모두 혐오·공격 표현으로 봅니다. <b>① 집단 혐오:</b> 성별·연령·출신·인종·종교·장애·정치 성향 등을 이유로 집단을 싸잡아 깎아내리거나, 비인간화·배제·위협·멸칭을 쓰는 표현. <b>② 공격적 표현:</b> 특정 개인이나 집단을 깎아내리거나 망신 주려는 모욕·조롱·욕설. 어조가 공손하거나 질문 형태여도 멸칭·모욕이 있으면 해당합니다.</p>
          <p><b>해당하지 않는 경우:</b> 모욕 없는 행동·정책 비판, 동조하지 않는 인용·보도, 누구도 겨냥하지 않은 가벼운 감탄, 집단에 대한 중립적 언급, 인물에 대한 가벼운 평가·감상·농담.</p>
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

      <MethodSection number="07" title="사회과학적 해석 단위" icon={<Users size={18} />}>
        <p className="section-intro">모델의 판정은 개인의 본질이나 의도를 규정하는 값이 아니라, 수집된 시점의 발화와 답글 관계를 관찰 가능한 지표로 바꾼 결과입니다.</p>
        <div className="social-lens-grid">
          <article><Code2 size={20} /><h3>분석 단위</h3><p>기본 단위는 댓글·답글·자막이라는 <strong>발화</strong>입니다. 자막은 문장 경계를 우선하고 시간·길이 상한을 보조 기준으로 삼습니다. 작성자 단위 수치는 발화 결과를 집계한 값이며 개인의 성향 진단이 아닙니다.</p></article>
          <article><Scale size={20} /><h3>개념의 조작화</h3><p>혐오표현 개념을 12개 범주와 정치적 대상 축으로 조작화합니다. 각 범주는 분석 도구이지 사회집단의 고정된 속성이 아닙니다.</p></article>
          <article><Network size={20} /><h3>관계적 맥락</h3><p>답글 edge와 연결 구조는 상호작용의 집중을 보여줍니다. 연결 자체가 동조·설득·영향 또는 혐오의 전파를 입증하지는 않습니다.</p></article>
          <article><BookOpenCheck size={20} /><h3>근거의 역할</h3><p>검색된 정의와 유사 사례는 판정 경로를 감사하기 위한 근거입니다. 검색 유사도나 모델의 한국어 사유를 사실의 증명으로 취급하지 않습니다.</p></article>
        </div>
      </MethodSection>

      <MethodSection number="08" title="타당도·윤리·주장의 경계" icon={<TriangleAlert size={18} />}>
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

      <MethodSection number="09" title="운영 품질 관리" icon={<ServerCog size={18} />}>
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

function ModelsAndPrompt({ methodology }: { methodology: Methodology | null | undefined }) {
  if (methodology === undefined) return <p className="section-intro">모델과 프롬프트 정보를 불러오는 중입니다.</p>;
  if (methodology === null) return <p className="section-intro">모델과 프롬프트 정보를 불러오지 못했습니다. 잠시 후 다시 시도해주세요.</p>;
  const { models, tiers } = methodology;
  return (
    <>
      <p className="section-intro">아래 내용은 서버가 실제 분석에 쓰는 설정에서 그대로 가져옵니다. 프롬프트는 분류기가 호출하는 함수로 생성하며, 검색된 근거 자리만 설명으로 바꿔 보여줍니다.</p>
      <div className="scope-table-wrap">
        <table className="scope-table model-table">
          <thead><tr><th>역할</th><th>모델</th><th>설명</th></tr></thead>
          <tbody>
            <tr><th>혐오 판정</th><td><code>{models.classifier.join(", ")}</code></td><td>검색 근거를 읽고 혐오 여부·범주·판정 이유를 JSON으로 답합니다.</td></tr>
            <tr><th>검색용 임베딩</th><td><code>{models.embedding}</code></td><td>입력과 근거 문서를 벡터로 바꿔 의미가 가까운 문서를 찾습니다. 비용은 서비스가 부담합니다.</td></tr>
            {models.prefilter && <tr><th>사전 필터 (절약 방식)</th><td><code>{models.prefilter.model}</code></td><td>혐오 확률이 {models.prefilter.threshold} 미만인 댓글은 판정 모델을 부르지 않고 정상으로 처리합니다. 공개 데이터 970건에서 놓친 혐오 댓글은 0건이었습니다.</td></tr>}
          </tbody>
        </table>
      </div>
      {tiers.length > 0 && (
        <div className="model-tiers">
          {tiers.map((tier) => (
            <article key={tier.key}>
              <strong>{tier.label} 방식</strong>
              <small>{tier.model_label}</small>
              <p>{tier.summary}</p>
              <dl>
                {tier.benchmark_accuracy !== null && <div><dt>정확도</dt><dd>{Math.round(tier.benchmark_accuracy * 1000) / 10}%</dd></div>}
                {tier.benchmark_f1 !== null && <div><dt>F1</dt><dd>{tier.benchmark_f1.toFixed(3)}</dd></div>}
                {tier.usd_per_1000_comments !== null && <div><dt>댓글 1,000개당</dt><dd>약 ${tier.usd_per_1000_comments.toFixed(2)}</dd></div>}
              </dl>
            </article>
          ))}
        </div>
      )}
      <p className="method-note">정확도는 튜닝에 쓰지 않은 공개 혐오표현 데이터 970건(K-HATERS·BEEP) 기준입니다. 더 큰 모델(Sonnet 5.5)은 F1 0.830으로 차이가 통계적으로 유의하지 않고 비용이 17배라 제공하지 않습니다.</p>
      {methodology.pinned_cards.map((card) => (
        <details className="prompt-block" key={card.doc_id}>
          <summary>항상 포함되는 기준 카드 <code>{card.doc_id}</code></summary>
          <pre>{card.text}</pre>
        </details>
      ))}
      <details className="prompt-block" open>
        <summary>판정 프롬프트 전문 <code>{methodology.prompt_version}</code></summary>
        <pre>{methodology.prompt}</pre>
      </details>
    </>
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
