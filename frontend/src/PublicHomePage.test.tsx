import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { AppRoutes } from "./App";
import { StaticSessionProvider } from "./session";
import type { AuthSession } from "./types";

const SIGNED_IN: AuthSession = {
  user_id: "user-id",
  email: "tester@example.com",
  display_name: "Tester",
  avatar_url: null,
  api_keys_registered: { anthropic: true },
};

function render(path: string, session: AuthSession | null) {
  return renderToStaticMarkup(
    <StaticSessionProvider session={session}>
      <MemoryRouter initialEntries={[path]}><AppRoutes /></MemoryRouter>
    </StaticSessionProvider>,
  );
}

function count(html: string, needle: string) {
  return html.split(needle).length - 1;
}

describe("app shell navigation", () => {
  it("renders public samples inside the shared shell with the sidebar", () => {
    const html = render("/samples", null);

    expect(html).toContain('class="sidebar"');
    expect(html).toContain("공개 샘플 보고서");
    expect(html).not.toContain("public-header");
  });

  it("hides personal links from visitors and offers popup login", () => {
    const html = render("/samples", null);

    expect(html).not.toContain('href="/history"');
    expect(html).not.toContain('href="/settings"');
    expect(html).toContain("Google 로그인");
    expect(html).not.toContain("/api/auth/google/login");
  });

  it("shows history and settings in the sidebar once signed in", () => {
    const html = render("/samples", SIGNED_IN);

    expect(html).toContain('href="/history"');
    expect(html).toContain("API 키 설정");
    expect(html).toContain("Tester");
  });

  it("links the methodology page from the top bar only", () => {
    const html = render("/samples", SIGNED_IN);
    const sidebar = html.slice(html.indexOf('class="sidebar"'));

    expect(count(html, 'href="/rag-methodology"')).toBe(2); // desktop + mobile menu
    expect(sidebar).not.toContain('href="/rag-methodology"');
  });
});
