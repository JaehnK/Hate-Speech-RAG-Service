import { describe, expect, it } from "vitest";

import { itemProgressText, ratioPercent, reportIdFromPath } from "./utils";

describe("report helpers", () => {
  it("extracts a report id from an API path", () => {
    expect(reportIdFromPath("/api/reports/report-123")).toBe("report-123");
    expect(reportIdFromPath(null)).toBeNull();
  });

  it("calculates safe percentages", () => {
    expect(ratioPercent(4, 10)).toBe(40);
    expect(ratioPercent(4, 0)).toBe(0);
  });

  it("formats detailed RAG item progress", () => {
    expect(itemProgressText("analyze_comments", { total: 404, completed: 127, succeeded: 125, failed: 2 }))
      .toBe("댓글·답글 127 / 404 완료 · 성공 125 · 실패 2");
    expect(itemProgressText("analyze_script", { total: 33, completed: 10, succeeded: 10, failed: 0 }))
      .toContain("세그먼트 10 / 33 완료");
  });
});
