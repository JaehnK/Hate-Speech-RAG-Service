import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import App from "./App";

describe("public navigation", () => {
  it("does not expose developer-only pages", () => {
    const html = renderToStaticMarkup(
      <MemoryRouter initialEntries={["/"]}>
        <App />
      </MemoryRouter>,
    );

    expect(html).not.toContain("RAG 방법론");
    expect(html).not.toContain("API 문서");
    expect(html).not.toContain('href="/docs"');
    expect(html).not.toContain("/api/health/readiness");
  });
});
