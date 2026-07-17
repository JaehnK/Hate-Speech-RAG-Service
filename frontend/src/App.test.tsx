import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import App, { HateCommentCard } from "./App";

describe("public navigation", () => {
  it("uses the analysis workspace as the main page", () => {
    const html = renderToStaticMarkup(
      <MemoryRouter initialEntries={["/"]}>
        <App />
      </MemoryRouter>,
    );

    expect(html).toContain("HateScope");
    expect(html).toContain("로그인 상태를 확인하는 중입니다");
    expect(html).toContain('href="/samples"');
  });

  it("publishes the portfolio methodology without API developer links", () => {
    const html = renderToStaticMarkup(
      <MemoryRouter initialEntries={["/samples"]}>
        <App />
      </MemoryRouter>,
    );

    expect(html).toContain("HateScope");
    expect(html).toContain("RAG 방법론");
    expect(html).not.toContain("API 문서");
    expect(html).not.toContain('href="/docs"');
    expect(html).not.toContain("/api/health/readiness");
  });
});

describe("hate comment evidence", () => {
  it("renders expandable reasoning and RAG document references", () => {
    const html = renderToStaticMarkup(
      <HateCommentCard comment={{
        comment_snapshot_id: "snapshot-id",
        youtube_comment_id: "youtube-comment-id",
        is_reply: false,
        parent_youtube_comment_id: null,
        author_display_name: null,
        author_channel_id: null,
        text_original: "표현 원문",
        like_count: 10,
        published_at: null,
        analysis: {
          status: "succeeded",
          is_hate_speech: true,
          categories: ["age"],
          target_group: "노년층",
          hate_type: "집단 일반화",
          reasoning: "연령을 이유로 집단 전체를 비하합니다.",
          rag_context_status: "complete",
          similar_cases_used: [{ doc_id: "k-haters:train:42", source_dataset: "k-haters", mapped_categories: ["age"], score: 0.8 }],
          definition_docs_used: [{ doc_id: "category:age:0", source_id: "internal_taxonomy", retrieval_tags: ["age"] }],
        },
      }} />,
    );

    expect(html).toContain("<details>");
    expect(html).toContain("<summary>");
    expect(html).toContain("분석 근거 보기");
    expect(html).toContain("연령을 이유로 집단 전체를 비하합니다.");
    expect(html).toContain("k-haters:train:42");
    expect(html).toContain("category:age:0");
    expect(html).toContain("정의·유사 사례 사용");
  });
});
