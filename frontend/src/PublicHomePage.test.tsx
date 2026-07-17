import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { PublicAccount } from "./PublicHomePage";

describe("public sample account control", () => {
  it("shows the signed-in account name instead of Google login", () => {
    const html = renderToStaticMarkup(
      <MemoryRouter>
        <PublicAccount
          session={{
            user_id: "user-id",
            email: "lecielgris1@gmail.com",
            display_name: "Le Ciel Gris",
            avatar_url: null,
            api_keys_registered: { anthropic: true, upstage: true },
          }}
          onSignOut={vi.fn()}
        />
      </MemoryRouter>,
    );

    expect(html).toContain("Le Ciel Gris");
    expect(html).not.toContain("Google로 로그인");
    expect(html).toContain('aria-label="로그아웃"');
  });

  it("keeps Google login for visitors", () => {
    const html = renderToStaticMarkup(
      <MemoryRouter><PublicAccount session={null} onSignOut={vi.fn()} /></MemoryRouter>,
    );

    expect(html).toContain("Google로 로그인");
    expect(html).toContain("return_to=/samples");
  });
});
