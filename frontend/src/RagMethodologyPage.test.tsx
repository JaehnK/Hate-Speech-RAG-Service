import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { RagMethodologyPage } from "./RagMethodologyPage";

describe("RAG methodology page", () => {
  it("publishes the production prompt and retrieval contract", () => {
    const html = renderToStaticMarkup(<RagMethodologyPage />);

    expect(html).toContain("category-rag-v0.3.0");
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
  });
});
