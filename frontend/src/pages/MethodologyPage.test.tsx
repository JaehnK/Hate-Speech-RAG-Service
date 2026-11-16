import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { humanize, MethodologyPage } from "./MethodologyPage";

describe("methodology page", () => {
  it("renders live categories with code names replaced by Korean names", () => {
    expect(humanize("다른 category에 맞지 않는 대상, political_camp 공격, message", [
      { code: "political_camp", name: "지지층·진영 비하", definition: "", include: [], exclude: [] },
      { code: "age", name: "연령 비하", definition: "", include: [], exclude: [] },
    ])).toBe("다른 유형에 맞지 않는 대상, 지지층·진영 비하 공격, message");
  });

  it("explains the method in plain language without infrastructure internals", () => {
    const html = renderToStaticMarkup(<MethodologyPage />);

    for (const text of [
      "Three-Vector RAG 판정 방식",
      "분류 체계",
      "법령·심의 기준",
      "비슷한 사례",
      "비슷한 사례 먼저",
      "유형 좁히기",
      "판정 원칙",
      "결과 확인",
      "모델과 판정 규칙",
      "유형 판정 기준",
      "해석 단위",
      "구성타당도",
      "선택 편향",
      "인과관계",
      "개인 제재",
      "주장하면 안 되는 것",
      "형식 + 규칙",
      "운영 품질 관리",
    ]) {
      expect(html).toContain(text);
    }
    // Category cards and corpus sizes come from the server, so nothing stale is hardcoded.
    for (const stale of ["정부·공직자 공격", "두 가지 질문", "항목 21개", "출처 17개", "12개 유형"]) {
      expect(html).not.toContain(stale);
    }
    for (const awkward of ["범주", "라벨링", "발화", "복호화"]) {
      expect(html).not.toContain(awkward);
    }
    for (const internalDetail of [
      "Embed 2",
      "category-rag-v0.3.1",
      "claude-haiku-4-5-20251001",
      "hate_speech_definitions",
      "hate_speech_taxonomy",
      "hate_speech_authoritative",
      "embedding-passage",
      "definition_docs_used",
      "figma.com/board/",
      "LLM_ERROR",
    ]) {
      expect(html).not.toContain(internalDetail);
    }
  });
});
