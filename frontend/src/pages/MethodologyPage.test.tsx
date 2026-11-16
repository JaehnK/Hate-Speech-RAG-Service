import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { MethodologyPage } from "./MethodologyPage";

describe("methodology page", () => {
  it("explains the method in plain language without infrastructure internals", () => {
    const html = renderToStaticMarkup(<MethodologyPage />);

    for (const text of [
      "Three-Vector RAG 판정 방식",
      "분류 체계",
      "법령·심의 기준",
      "비슷한 사례",
      "비슷한 사례 먼저",
      "유형 좁히기",
      "정치적 공격: 두 가지 질문",
      "정부·공직자 공격",
      "판정 원칙",
      "결과 확인",
      "모델과 판정 규칙",
      "유형 판정 기준",
      "공통 판정 기준",
      "포함",
      "제외·경계",
      "국적·민족 공격은 출신·인종 비하",
      "정책 비판이나 강한 반대만으로는 혐오가 아닙니다",
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
