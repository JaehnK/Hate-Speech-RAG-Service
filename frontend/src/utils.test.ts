import { describe, expect, it } from "vitest";

import { ratioPercent, reportIdFromPath } from "./utils";

describe("report helpers", () => {
  it("extracts a report id from an API path", () => {
    expect(reportIdFromPath("/api/reports/report-123")).toBe("report-123");
    expect(reportIdFromPath(null)).toBeNull();
  });

  it("calculates safe percentages", () => {
    expect(ratioPercent(4, 10)).toBe(40);
    expect(ratioPercent(4, 0)).toBe(0);
  });
});
