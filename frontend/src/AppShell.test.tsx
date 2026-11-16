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

function render(path: string, session: AuthSession | null | undefined) {
  return renderToStaticMarkup(
    <StaticSessionProvider session={session}>
      <MemoryRouter initialEntries={[path]}><AppRoutes /></MemoryRouter>
    </StaticSessionProvider>,
  );
}

describe("app shell", () => {
  it("has no sidebar and shows the analysis form with public samples on the home page", () => {
    const html = render("/", null);

    expect(html).not.toContain("sidebar");
    expect(html).toContain("HateScope");
    expect(html).toContain("영상 주소");
    expect(html).toContain("공개 샘플 보고서");
    expect(html).toContain("Google 로그인 후 분석");
  });

  it("hides personal links from visitors and offers popup login", () => {
    const html = render("/", null);

    expect(html).not.toContain('href="/history"');
    expect(html).not.toContain('href="/settings"');
    expect(html).toContain("Google 로그인");
    expect(html).not.toContain("/api/auth/google/login");
    expect(html).toContain('href="/rag-methodology"');
  });

  it("adds my analyses to the top navigation once signed in", () => {
    const html = render("/", SIGNED_IN);

    expect(html).toContain('href="/history"');
    expect(html).toContain("내 분석");
    expect(html).toContain("분석 시작");
  });

  it("asks visitors to sign in before showing personal pages", () => {
    expect(render("/history", null)).toContain("로그인이 필요합니다");
    expect(render("/settings", null)).toContain("로그인이 필요합니다");
  });

  it("warns signed-in users without an Anthropic key instead of blocking the page", () => {
    const html = render("/", { ...SIGNED_IN, api_keys_registered: { anthropic: false } });

    expect(html).toContain("Anthropic API 키가 필요합니다");
    expect(html).toContain('href="/settings"');
    expect(html).toContain("공개 샘플 보고서");
  });
});
