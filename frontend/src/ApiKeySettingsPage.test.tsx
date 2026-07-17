import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { ApiKeySettingsPage } from "./ApiKeySettingsPage";

describe("API key issuance guidance", () => {
  it("links both providers to their official key pages with safe external links", () => {
    const html = renderToStaticMarkup(<ApiKeySettingsPage />);

    expect(html).toContain('href="https://platform.claude.com/settings/keys"');
    expect(html).toContain('href="https://console.upstage.ai/api-keys"');
    expect(html.match(/target="_blank"/g)).toHaveLength(2);
    expect(html.match(/rel="noreferrer"/g)).toHaveLength(2);
    expect(html).toContain("API Keys에서 Create Key를 선택");
    expect(html).toContain("Upstage Console에 가입하거나 로그인");
    expect(html).toContain("Git, 메신저, 스크린샷에는 남기지 마세요");
  });
});
