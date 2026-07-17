import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { RagMethodologyPage } from "./RagMethodologyPage";

describe("RAG methodology page", () => {
  it("explains the portfolio methodology without operational details", () => {
    const html = renderToStaticMarkup(<RagMethodologyPage />);

    expect(html).toContain("Dual-Vector RAG 분류 파이프라인");
    expect(html).toContain("정의·분류 기준");
    expect(html).toContain("유사 분석 사례");
    expect(html).toContain("판정 원칙");
    expect(html).toContain("결과 검증");
    expect(html).toContain("사회과학적 해석 단위");
    expect(html).toContain("구성타당도");
    expect(html).toContain("선택 편향");
    expect(html).toContain("인과관계");
    expect(html).toContain("개인 제재");
    expect(html).toContain("주장하면 안 되는 것");
    expect(html).toContain("Dual-Vector RAG 분석");
    expect(html).toContain("형식 + 규칙");
    expect(html).toContain("운영 품질 관리");
    expect(html).toContain("Taxonomy 판정 가이드");
    expect(html).toContain("공통 판정 기준");
    expect(html).toContain("포함 기준");
    expect(html).toContain("제외·경계");
    expect(html).toContain("국적·민족 공격은 정체성 범주");
    expect(html).toContain("정치적 반대나 정책 비판만으로는 혐오가 아닙니다");

    for (const internalDetail of [
      "Embed 2",
      "Embedding 비용·마이그레이션",
      "category-rag-v0.3.0",
      "claude-haiku-4-5-20251001",
      "hate_speech_definitions",
      "embedding-passage",
      "4096",
      "172,157",
      "0.40",
      "definition_docs_used",
      "figma.com/board/",
      "LLM_ERROR",
    ]) {
      expect(html).not.toContain(internalDetail);
    }
  });
});
