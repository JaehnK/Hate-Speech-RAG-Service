import { Banner } from "@astryxdesign/core/Banner";
import { Heading } from "@astryxdesign/core/Heading";
import { Spinner } from "@astryxdesign/core/Spinner";
import { Table } from "@astryxdesign/core/Table";
import { Text } from "@astryxdesign/core/Text";
import { type ReactNode, useEffect, useState } from "react";

import { getMethodology } from "../api";
import { RagPipelineFlow } from "../RagPipelineFlow";
import type { Methodology } from "../types";
import { PageHeader } from "../ui/common";

const TAXONOMY_GROUPS = [
  {
    title: "누구를 왜 공격했나",
    description: "성별·연령·출신 같은 속성을 이유로 한 공격과, 욕설이라는 표현 방식을 나눠 봅니다. 욕설은 다른 유형과 함께 붙을 수 있습니다.",
    cards: [
      { label: "성별 비하", definition: "성별·성역할·임신·출산·가족 역할을 이유로 깎아내림", include: "여성·남성 집단을 싸잡아 열등하다고 말함, 성별을 이유로 배제·폭력 정당화", exclude: "성별 통계·정책 토론, 성별과 무관한 개인 행동 비판" },
      { label: "연령 비하", definition: "나이·세대를 이유로 깎아내림", include: "특정 세대 전체를 무능·해롭다고 일반화, 나이를 이유로 참여 배제", exclude: "연령별 특성 설명, 세대 정책 비판" },
      { label: "출신·인종·종교·장애 등 비하", definition: "출신지역·인종·국적·종교·성적지향·성별정체성·장애를 이유로 깎아내림", include: "집단 멸칭, 추방·차별·폭력 주장, 비인간화", exclude: "문화·종교 정보, 정치 성향 집단 공격(→ 지지층·진영 비하)" },
      { label: "욕설·모욕·기타 공격", definition: "사람이나 집단을 향한 욕설·모욕·조롱, 그리고 위 유형에 없는 대상(연예인 등 개인, 직업·외모 집단)에 대한 공격", include: "직접 욕설·멸칭, 깎아내리려는 의도가 분명한 개인 조롱, 직업·외모 집단 비하", exclude: "비판 목적의 인용, 가벼운 감상·아쉬움 표현, 모욕 없는 비판" },
    ],
  },
  {
    title: "정치적 공격: 두 가지 질문",
    description: "① 무엇을 겨냥했나? 기관·인물 / 법·제도 / 사람들 무리. ② 공적인 쪽인가, 민간인가? 이 두 답의 조합으로 여섯 유형 중 하나를 고릅니다. 정책 비판이나 강한 반대만으로는 혐오가 아닙니다.",
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
    description: "누구를 겨냥했는지 알 수 없거나, 판정 기준을 충족하지 않을 때 사용합니다. 위 유형에 맞지 않는 대상에 대한 공격은 욕설·모욕·기타 공격으로 분류합니다.",
    cards: [
      { label: "대상 없는 욕설", definition: "욕설·공격은 분명하지만 누구를 겨냥했는지 알 수 없음", include: "대상 없이 단독으로 쓴 강한 욕설", exclude: "대상이 드러난 경우" },
      { label: "혐오 아님", definition: "판정 기준을 충족하지 않음", include: "모욕 없는 비판, 동조하지 않는 인용·보도, 중립 정보", exclude: "사람·집단을 향한 모욕·조롱·욕설" },
    ],
  },
] as const;

const TOC = [
  ["flow", "판정 흐름"],
  ["evidence", "세 가지 근거"],
  ["principles", "판정 원칙과 확인"],
  ["models", "모델과 판정 규칙"],
  ["taxonomy", "유형 판정 기준"],
  ["interpretation", "해석 단위"],
  ["limits", "타당도·윤리·주장의 경계"],
  ["operations", "운영 품질 관리"],
] as const;

export function MethodologyPage() {
  const [methodology, setMethodology] = useState<Methodology | null | undefined>(undefined);
  useEffect(() => {
    let active = true;
    getMethodology().then((value) => { if (active) setMethodology(value); }).catch(() => { if (active) setMethodology(null); });
    return () => { active = false; };
  }, []);

  return (
    <div className="hs-page hs-method">
      <PageHeader
        title="Three-Vector RAG 판정 방식"
        description="댓글·답글·자막 구간마다 분류 기준, 법령과 심의 기준, 비슷한 사례라는 세 가지 근거를 따로 찾아 판정합니다. 이 페이지는 판정 과정과 결과를 어디까지 해석할 수 있는지 설명합니다."
      />
      <nav className="hs-toc" aria-label="이 페이지의 목차">
        {TOC.map(([id, label]) => <a key={id} href={`#${id}`}>{label}</a>)}
      </nav>

      <MethodSection id="flow" title="판정 흐름" intro="데이터 수집부터 세 가지 근거 찾기, 결과 확인, 답글 네트워크와 보고서 생성까지의 흐름입니다.">
        <RagPipelineFlow />
      </MethodSection>

      <MethodSection id="evidence" title="세 가지 근거">
        <div className="hs-columns">
          <EvidenceItem
            title="분류 체계"
            role="판정 기준"
            rows={[["구성", "항목 21개 (판정 기준·유형·경계)"], ["검색", "4개 검색 + 항상 2개"], ["효과", "판정 기준을 일관되게 유지"]]}
          >
            혐오 여부를 가르는 판정 기준과 예외 규칙은 매번 넣고, 입력과 관련된 유형 정의·경계 항목 4개를 더 찾습니다.
          </EvidenceItem>
          <EvidenceItem
            title="법령·심의 기준"
            role="판정 근거"
            rows={[["국내", "정보통신망법·방미심위 심의규정·형법·인권위"], ["국제", "Rabat·UN·유럽·해외 법제 요약"], ["기타", "YouTube 정책·데이터셋 라벨 기준"]]}
          >
            출처 17개를 조항 단위 58개로 나눠 담았습니다. 비슷한 사례가 가리키는 유형에 맞춰 문서 종류별로 골라 찾고, 판정 근거로 조항을 인용합니다. 혐오 여부의 기준은 분류 체계가 정하며, 법령은 가장 심각한 수준만 다룬다는 점을 함께 고려합니다.
          </EvidenceItem>
          <EvidenceItem
            title="비슷한 사례"
            role="경험적 근거"
            rows={[["규모", "공개 데이터 172,157건"], ["검색", "가장 가까운 6건"], ["역할", "판정 보정 + 기준 문서 안내"]]}
          >
            입력과 의미가 가까운, 사람이 판정해 둔 사례를 가장 먼저 찾습니다. 사례는 판단을 돕는 비교 자료이며 정답으로 보지 않습니다.
          </EvidenceItem>
        </div>
        <ol className="hs-numbered">
          <li><Text weight="semibold">비슷한 사례 먼저</Text><Text type="supporting">입력과 가장 가까운, 사람이 판정해 둔 사례 6건을 찾습니다.</Text></li>
          <li><Text weight="semibold">유형 좁히기</Text><Text type="supporting">사례 2건 이상이 공유하는 유형(예: 성별 비하, 지지층 비하)을 뽑습니다.</Text></li>
          <li><Text weight="semibold">심의 기준 찾기</Text><Text type="supporting">국내 법령·심의규정 2, 인권위 기준 1, 플랫폼 정책 1은 그 유형으로 좁혀 찾고, 국제 기준 요약 1과 데이터셋 라벨 기준 2는 유형과 상관없이 찾습니다.</Text></li>
          <li><Text weight="semibold">판정과 인용</Text><Text type="supporting">모델이 판정 기준에 따라 혐오 여부와 유형을 정하고, 실제로 근거가 된 조항을 보고서에 인용합니다.</Text></li>
        </ol>
        <p className="hs-note">성격이 다른 근거를 함께 쓰지만, 검색 결과를 사실의 증명이나 자동화된 최종 판단으로 취급하지 않습니다.</p>
      </MethodSection>

      <MethodSection id="principles" title="판정 원칙과 확인">
        <div className="hs-columns hs-columns--2">
          <div className="hs-stack">
            <Heading level={3}>판정 원칙</Heading>
            <ul className="hs-list">
              <li>먼저 혐오 여부를 판단한 뒤 세부 유형을 나눕니다.</li>
              <li>정책·행위 비판과 집단 자체에 대한 공격을 구별합니다.</li>
              <li>인용, 보도, 풍자와 반박의 문맥을 함께 봅니다.</li>
              <li>판정 이유를 사람이 읽을 수 있는 한국어로 요약합니다.</li>
            </ul>
          </div>
          <div className="hs-stack">
            <Heading level={3}>결과 확인</Heading>
            <ul className="hs-list">
              <li>정해진 결과 형식과 유형 조합 규칙을 지켰는지 확인합니다.</li>
              <li>"혐오 아님"인데 혐오 유형이 붙는 모순이 없는지 검사합니다.</li>
              <li>형식이 맞지 않는 결과는 한 번 더 고쳐 받습니다.</li>
              <li>판정에 실패한 댓글도 숨기지 않고 작업 상태에 남깁니다.</li>
            </ul>
          </div>
        </div>
      </MethodSection>

      <MethodSection id="models" title="모델과 판정 규칙">
        <ModelsAndPrompt methodology={methodology} />
      </MethodSection>

      <MethodSection id="taxonomy" title="유형 판정 기준">
        <div className="hs-callout">
          <Text weight="semibold" as="div">공통 판정 기준</Text>
          <Text as="p">이 서비스는 두 가지를 모두 혐오·공격 표현으로 봅니다. <b>① 집단 혐오:</b> 성별·연령·출신·인종·종교·장애·정치 성향 등을 이유로 집단을 싸잡아 깎아내리거나, 비인간화·배제·위협·멸칭을 쓰는 표현. <b>② 공격적 표현:</b> 특정 개인이나 집단을 깎아내리거나 망신 주려는 모욕·조롱·욕설. 어조가 공손하거나 질문 형태여도 멸칭·모욕이 있으면 해당합니다.</Text>
          <Text as="p"><b>해당하지 않는 경우:</b> 모욕 없는 행동·정책 비판, 동조하지 않는 인용·보도, 누구도 겨냥하지 않은 가벼운 감탄, 집단에 대한 중립적 언급, 인물에 대한 가벼운 평가·감상·농담.</Text>
        </div>
        {TAXONOMY_GROUPS.map((group) => (
          <div className="hs-stack" key={group.title}>
            <div className="hs-stack hs-stack--tight">
              <Heading level={3}>{group.title}</Heading>
              <Text type="supporting" as="p">{group.description}</Text>
            </div>
            <dl className="hs-definitions">
              {group.cards.map((card) => (
                <div key={card.label}>
                  <dt><Text weight="semibold">{card.label}</Text><Text type="supporting">{card.definition}</Text></dt>
                  <dd><Text type="supporting">포함</Text><Text>{card.include}</Text></dd>
                  <dd><Text type="supporting">제외·경계</Text><Text>{card.exclude}</Text></dd>
                </div>
              ))}
            </dl>
          </div>
        ))}
      </MethodSection>

      <MethodSection id="interpretation" title="해석 단위" intro="모델의 판정은 개인의 본질이나 의도를 규정하는 값이 아니라, 모은 시점의 댓글과 답글 관계를 관찰 가능한 지표로 바꾼 결과입니다.">
        <div className="hs-columns hs-columns--2">
          <TextBlock title="분석 단위">기본 단위는 댓글 하나, 답글 하나, 자막 한 구간입니다. 자막은 문장 경계를 우선하고 시간·길이 상한을 보조 기준으로 삼습니다. 작성자 단위 수치는 댓글 판정을 합친 값이며 개인의 성향 진단이 아닙니다.</TextBlock>
          <TextBlock title="개념의 조작화">혐오표현 개념을 12개 유형과 정치적 대상 축으로 조작화합니다. 각 유형은 분석 도구이지 사회집단의 고정된 속성이 아닙니다.</TextBlock>
          <TextBlock title="관계적 맥락">답글 엣지와 연결 구조는 대화가 어디에 몰렸는지 보여줍니다. 연결 자체가 동조·설득·영향이나 혐오가 퍼졌다는 증거는 아닙니다.</TextBlock>
          <TextBlock title="근거의 역할">찾은 정의와 비슷한 사례는 판정 경로를 점검하기 위한 근거입니다. 검색 유사도나 모델이 쓴 판정 이유를 사실의 증명으로 보지 않습니다.</TextBlock>
        </div>
      </MethodSection>

      <MethodSection id="limits" title="타당도·윤리·주장의 경계">
        <Banner status="info" title="기술통계의 범위" description="보고서는 모을 수 있었던 공개 댓글 표본을 기술합니다. 모집단 대표성이나 인과관계, 작성자의 고정된 정체성·의도를 추론하지 않습니다." />
        <div className="hs-table-scroll">
          <Table
            density="compact"
            verticalAlign="top"
            idKey="output"
            data={SCOPE_ROWS}
            columns={[
              { key: "output", header: "산출값" },
              { key: "can", header: "해석할 수 있는 것" },
              { key: "cannot", header: "주장하면 안 되는 것" },
            ]}
          />
        </div>
        <div className="hs-columns">
          <TextBlock title="구성타당도">분류 체계가 풍자, 은어, 교차정체성처럼 개념의 모든 양상을 포괄하지 못할 수 있습니다.</TextBlock>
          <TextBlock title="선택 편향">삭제·비공개·수집 누락 댓글은 관찰되지 않으므로 공개 표본을 전체 이용자로 일반화하지 않습니다.</TextBlock>
          <TextBlock title="측정 오차">방언, 반어, 인용, 맥락 부족에 따라 집단별 오분류율이 달라질 수 있어 사람이 표본을 검토해야 합니다.</TextBlock>
          <TextBlock title="시간 비교">판정 기준·근거 자료·플랫폼 정책을 고정하지 않은 시점 간 증감은 실제 사회 변화와 구분하기 어렵습니다.</TextBlock>
          <TextBlock title="인과관계">현재 파이프라인은 기술·탐색 분석입니다. 네트워크 연결과 혐오 판정만으로 원인이나 전파 효과를 추정하지 않습니다.</TextBlock>
          <TextBlock title="연구 윤리">작성자 식별자는 최소화·가명화하고, 결과를 개인 제재나 자동 의사결정의 단독 근거로 쓰지 않습니다.</TextBlock>
        </div>
      </MethodSection>

      <MethodSection id="operations" title="운영 품질 관리">
        <ol className="hs-numbered hs-columns">
          <li><Text weight="semibold">근거 자료 관리</Text><Text type="supporting">출처와 이용 조건이 확인된 정의·사례 자료만 씁니다.</Text></li>
          <li><Text weight="semibold">변경 이력 관리</Text><Text type="supporting">판정 기준과 근거 자료의 변경을 기록해 결과를 비교할 수 있게 합니다.</Text></li>
          <li><Text weight="semibold">자동 확인</Text><Text type="supporting">결과 형식, 유형 충돌과 누락 여부를 자동으로 점검합니다.</Text></li>
          <li><Text weight="semibold">실패 추적</Text><Text type="supporting">수집·검색·판정 실패를 단계별로 기록하고 부분 성공을 구분합니다.</Text></li>
          <li><Text weight="semibold">표본 검토</Text><Text type="supporting">정확도와 편향을 확인하기 위해 사람이 정기적으로 표본을 검토합니다.</Text></li>
          <li><Text weight="semibold">해석 범위 고지</Text><Text type="supporting">보고서가 설명할 수 있는 범위와 한계를 결과와 함께 제공합니다.</Text></li>
        </ol>
      </MethodSection>
    </div>
  );
}

interface ScopeRow extends Record<string, unknown> { output: string; can: string; cannot: string }

const SCOPE_ROWS: ScopeRow[] = [
  { output: "혐오 댓글 비율", can: "모아서 판정에 성공한 댓글 중 모델이 혐오로 판정한 비율", cannot: "YouTube 전체 또는 사회 전체의 혐오 수준" },
  { output: "유형 분포", can: "모델이 혐오로 판정한 댓글 안에서의 상대적 구성", cannot: "특정 집단이 객관적으로 더 공격받는다는 일반화" },
  { output: "답글 수·관계", can: "모은 답글 관계의 반복과 혐오표현이 담긴 정도", cannot: "노출, 동조, 설득 또는 혐오 확산의 인과효과" },
  { output: "연결 수·중심성", can: "모은 댓글 네트워크 안에서의 구조적 위치", cannot: "실제 영향력, 극단성, 조직성 또는 개인의 의도" },
  { output: "판정 이유·근거", can: "모델 판정이 참조한 설명과 사례를 거슬러 확인할 수 있음", cannot: "법적 판단, 객관적 진실 또는 사람 검토의 대체" },
];

function ModelsAndPrompt({ methodology }: { methodology: Methodology | null | undefined }) {
  if (methodology === undefined) return <Spinner label="모델과 판정 규칙을 불러오는 중입니다" />;
  if (methodology === null) return <Banner status="error" title="모델과 판정 규칙을 불러오지 못했습니다" description="잠시 후 다시 시도해주세요." />;
  const { models, tiers } = methodology;
  const rows = [
    { role: "혐오 판정", model: models.classifier.join(", "), note: "찾은 근거를 읽고 혐오 여부·유형·판정 이유를 JSON으로 답합니다." },
    { role: "검색용 모델 (임베딩)", model: models.embedding, note: "입력과 근거 문서를 벡터로 바꿔 의미가 가까운 문서를 찾습니다. 비용은 서비스가 부담합니다." },
    ...(models.prefilter ? [{ role: "먼저 걸러내는 모델 (절약 방식)", model: models.prefilter.model, note: `혐오 확률이 기준점 ${models.prefilter.threshold} 미만인 댓글은 판정 모델을 부르지 않고 혐오 아님으로 처리합니다. 공개 데이터 970건에서 놓친 혐오 댓글은 0건이었습니다.` }] : []),
  ];
  return (
    <div className="hs-stack">
      <Text type="supporting" as="p">아래 내용은 서버가 실제 분석에 쓰는 설정에서 그대로 가져옵니다. 판정 규칙(프롬프트)은 분류기가 호출하는 함수로 만들며, 찾은 근거가 들어갈 자리만 설명으로 바꿔 보여줍니다.</Text>
      <div className="hs-table-scroll">
        <Table
          density="compact"
          verticalAlign="top"
          idKey="role"
          data={rows}
          columns={[
            { key: "role", header: "역할" },
            { key: "model", header: "모델", renderCell: (row) => <span className="hs-code">{row.model}</span> },
            { key: "note", header: "설명" },
          ]}
        />
      </div>
      {tiers.length > 0 && (
        <div className="hs-columns">
          {tiers.map((tier) => (
            <div className="hs-stack hs-stack--tight" key={tier.key}>
              <Heading level={3}>{tier.label} 방식</Heading>
              <Text type="supporting">{tier.model_label}</Text>
              <Text as="p">{tier.summary}</Text>
              <dl className="hs-kv">
                {tier.benchmark_accuracy !== null && <div><dt>정확도</dt><dd>{Math.round(tier.benchmark_accuracy * 1000) / 10}%</dd></div>}
                {tier.benchmark_f1 !== null && <div><dt>F1</dt><dd>{tier.benchmark_f1.toFixed(3)}</dd></div>}
                {tier.usd_per_1000_comments !== null && <div><dt>댓글 1,000개당</dt><dd>약 ${tier.usd_per_1000_comments.toFixed(2)}</dd></div>}
              </dl>
            </div>
          ))}
        </div>
      )}
      <p className="hs-note">정확도는 학습·튜닝에 쓰지 않은 공개 혐오표현 데이터 970건(K-HATERS·BEEP)으로 잰 값입니다. 더 큰 모델(Sonnet 5.5)은 F1 0.830으로 차이가 통계적으로 유의하지 않고 비용이 17배라 제공하지 않습니다.</p>
      {methodology.pinned_cards.map((card) => (
        <details className="hs-prompt" key={card.doc_id}>
          <summary>항상 넣는 기준 항목 <span className="hs-code">{card.doc_id}</span></summary>
          <pre>{card.text}</pre>
        </details>
      ))}
      <details className="hs-prompt" open>
        <summary>판정 규칙 전문 <span className="hs-code">{methodology.prompt_version}</span></summary>
        <pre>{methodology.prompt}</pre>
      </details>
    </div>
  );
}

function MethodSection({ id, title, intro, children }: { id: string; title: string; intro?: string; children: ReactNode }) {
  return (
    <section className="hs-section" id={id} aria-labelledby={`${id}-title`}>
      <Heading level={2} id={`${id}-title`}>{title}</Heading>
      {intro && <Text type="supporting" as="p">{intro}</Text>}
      {children}
    </section>
  );
}

function EvidenceItem({ title, role, rows, children }: { title: string; role: string; rows: readonly (readonly [string, string])[]; children: ReactNode }) {
  return (
    <div className="hs-stack">
      <div className="hs-stack hs-stack--tight">
        <Heading level={3}>{title}</Heading>
        <Text type="supporting">{role}</Text>
      </div>
      <Text as="p">{children}</Text>
      <dl className="hs-kv hs-kv--wrap">{rows.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>
    </div>
  );
}

function TextBlock({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="hs-stack hs-stack--tight">
      <Heading level={3}>{title}</Heading>
      <Text as="p" type="supporting">{children}</Text>
    </div>
  );
}
