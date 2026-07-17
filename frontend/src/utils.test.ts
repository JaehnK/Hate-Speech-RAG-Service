import { describe, expect, it } from "vitest";

import { categoryLabel, formatPlaybackTime, itemProgressText, ratioPercent, reportIdFromPath } from "./utils";

describe("report helpers", () => {
  it("extracts a report id from an API path", () => {
    expect(reportIdFromPath("/api/reports/report-123")).toBe("report-123");
    expect(reportIdFromPath(null)).toBeNull();
  });

  it("calculates safe percentages", () => {
    expect(ratioPercent(4, 10)).toBe(40);
    expect(ratioPercent(4, 0)).toBe(0);
  });

  it("formats transcript timestamps", () => {
    expect(formatPlaybackTime(7.8)).toBe("0:07");
    expect(formatPlaybackTime(3661)).toBe("1:01:01");
  });

  it("formats detailed RAG item progress", () => {
    expect(itemProgressText("analyze_comments", { total: 404, completed: 127, succeeded: 125, failed: 2 }))
      .toBe("댓글·답글 127 / 404 완료 · 성공 125 · 실패 2");
    expect(itemProgressText("analyze_script", { total: 33, completed: 10, succeeded: 10, failed: 0 }))
      .toContain("세그먼트 10 / 33 완료");
  });

  it("translates canonical category codes for display", () => {
    expect(categoryLabel("identity")).toBe("정체성");
    expect(categoryLabel("state_authority")).toBe("국가 권위체");
    expect(categoryLabel("non_state_community")).toBe("비국가 공동체");
    expect(categoryLabel("unclassified")).toBe("미분류");
  });

  it("preserves an unknown category code in the fallback label", () => {
    expect(categoryLabel("future_category")).toBe("알 수 없는 분류 (future_category)");
  });
});
