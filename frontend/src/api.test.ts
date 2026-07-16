import { afterEach, describe, expect, it, vi } from "vitest";

import { getHateComments } from "./api";

afterEach(() => vi.unstubAllGlobals());

describe("report comments API", () => {
  it("requests successful hate comments in descending like order", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ items: [], total: 0, next_cursor: null, has_more: false }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await getHateComments("report/id", 200);

    const url = new URL(fetchMock.mock.calls[0][0], "http://localhost");
    expect(url.pathname).toBe("/api/reports/report%2Fid/comments");
    expect(Object.fromEntries(url.searchParams)).toMatchObject({
      is_hate_speech: "true",
      status: "succeeded",
      sort: "like_count",
      limit: "200",
      cursor: "200",
    });
  });
});
