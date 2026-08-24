import { afterEach, describe, expect, it, vi } from "vitest";
import { API_BASE, fetchAllPages } from "./api";

interface Item {
  id: number;
}

function jsonResponse(body: unknown) {
  return {
    ok: true,
    json: () => Promise.resolve(body),
  } as Response;
}

function mockFetch(pages: { items: Item[]; next_cursor: string | null }[]) {
  const calls: string[] = [];
  const fetchMock = vi.fn((_input: string | URL) => {
    const url = String(_input);
    const index = calls.length;
    calls.push(url);
    return Promise.resolve(jsonResponse(pages[index]));
  });
  vi.stubGlobal("fetch", fetchMock);
  return { calls, fetchMock };
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("fetchAllPages", () => {
  it("follows next_cursor until exhausted", async () => {
    const { calls, fetchMock } = mockFetch([
      { items: [{ id: 1 }, { id: 2 }], next_cursor: "abc" },
      { items: [{ id: 3 }], next_cursor: null },
    ]);

    const items = await fetchAllPages<Item>(
      (cursor) => `/things${cursor ? `?cursor=${cursor}` : ""}`,
    );

    expect(items).toEqual([{ id: 1 }, { id: 2 }, { id: 3 }]);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(calls[0]).toBe(`${API_BASE}/things`);
    expect(calls[1]).toBe(`${API_BASE}/things?cursor=abc`);
  });

  it("stops at maxPages even when more cursors remain", async () => {
    const page = { items: [{ id: 1 }], next_cursor: "next" };
    const { fetchMock } = mockFetch([page, page, page]);

    const items = await fetchAllPages<Item>(() => "/things", 3);

    expect(items).toEqual([{ id: 1 }, { id: 1 }, { id: 1 }]);
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it("returns a single page untouched when there is no cursor", async () => {
    const { calls, fetchMock } = mockFetch([
      { items: [{ id: 7 }], next_cursor: null },
    ]);

    const items = await fetchAllPages<Item>(() => "/things?page_size=500");

    expect(items).toEqual([{ id: 7 }]);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(calls[0]).toBe(`${API_BASE}/things?page_size=500`);
  });
});
