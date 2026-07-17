import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import App from "./App";

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
