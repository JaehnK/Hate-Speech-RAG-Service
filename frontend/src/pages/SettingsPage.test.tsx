import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { StaticSessionProvider } from "../session";
import { SettingsPage } from "./SettingsPage";

describe("account settings", () => {
  it("asks only for the Anthropic key and links its official page with safe external links", () => {
    const html = renderToStaticMarkup(
      <StaticSessionProvider session={null}>
        <MemoryRouter><SettingsPage /></MemoryRouter>
      </StaticSessionProvider>,
    );

    expect(html).toContain('href="https://platform.claude.com/settings/keys"');
    expect(html).not.toContain("console.upstage.ai");
    expect(html.match(/target="_blank"/g)).toHaveLength(1);
    expect(html.match(/rel="noreferrer"/g)).toHaveLength(1);
    expect(html).toContain("API Keys에서 Create Key를 선택");
    expect(html).not.toContain("Upstage");
    expect(html).toContain("Git, 메신저, 스크린샷");
    expect(html).toContain("분석할 때만 꺼내 씁니다");
  });
});
