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
    expect(html).toContain("example score ≥ 0.40");
    expect(html).toContain("Chain-of-thought");
    expect(html).toContain("definition_docs_used");
  });
});
