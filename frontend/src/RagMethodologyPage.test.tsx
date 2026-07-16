import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { RagMethodologyPage } from "./RagMethodologyPage";

describe("RAG methodology page", () => {
  it("publishes the production prompt and retrieval contract", () => {
    const html = renderToStaticMarkup(<RagMethodologyPage />);

    expect(html).toContain("category-rag-v0.3.0");
    expect(html).toContain("definition-corpus-2026-07-16-v0.3");
    expect(html).toContain("Write reasoning in Korean");
    expect(html).toContain("claude-haiku-4-5-20251001");
    expect(html).toContain("hate_speech_definitions");
    expect(html).toContain("hate_speech_examples");
    expect(html).toContain("유사도 0.40 이상?");
    expect(html).toContain("Chain-of-thought");
    expect(html).toContain("definition_docs_used");
    expect(html).toContain("사회과학적 해석 단위");
    expect(html).toContain("구성타당도");
    expect(html).toContain("선택 편향");
    expect(html).toContain("인과관계");
    expect(html).toContain("개인 제재");
    expect(html).toContain("주장하면 안 되는 것");
    expect(html).toContain("Item별 Dual-Vector RAG");
    expect(html).toContain("JSON 계약 통과?");
    expect(html).toContain("재시도 남음?");
    expect(html).toContain("figma.com/board/sGQ5uzigH8gTdLRYVGDM6X");
    expect(html).toContain("Taxonomy 판정 가이드");
    expect(html).toContain("공통 hate threshold");
    expect(html).toContain("포함 기준");
    expect(html).toContain("제외·경계");
    expect(html).toContain("국적·민족 공격은 identity");
    expect(html).toContain("정치적 반대나 정책 비판만으로는 혐오가 아닙니다");
  });
});
