// Unit tests: tool registry shape + api client behaviour with a mocked fetch.
// These do NOT touch the live API (see scripts/smoke.mjs for live checks).
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { TOOLS } from "../src/tools";
import { apiGet, ApiError } from "../src/api";

describe("tool registry", () => {
  it("has 29 tools, unique names, every tool has a description and a handler", () => {
    expect(TOOLS.length).toBe(29);
    const names = TOOLS.map((t) => t.name);
    expect(new Set(names).size).toBe(names.length);
    for (const t of TOOLS) {
      expect(t.description.length).toBeGreaterThan(20);
      expect(typeof t.run).toBe("function");
      expect(t.inputSchema).toBeDefined();
    }
  });

  it("covers the expected tool names", () => {
    const names = new Set(TOOLS.map((t) => t.name));
    for (const n of [
      "get_name", "get_stats", "get_season_day", "check_season_eligibility",
      "get_season_proof", "list_agents", "get_agent_registration_by_name",
      "list_agent_validations", "get_health", "list_listings",
    ]) {
      expect(names.has(n)).toBe(true);
    }
  });

  it("rejects a bad aiId at the schema level", () => {
    const t = TOOLS.find((x) => x.name === "check_season_eligibility");
    const schema = t.inputSchema.aiId;
    expect(() => schema.parse("not-an-aiid")).toThrow();
    expect(() => schema.parse("0x" + "a".repeat(64))).not.toThrow();
  });
});

describe("apiGet", () => {
  const realFetch = globalThis.fetch;
  beforeEach(() => { process.env.HAHA_API_BASE = "https://example.invalid/api"; });
  afterEach(() => { globalThis.fetch = realFetch; delete process.env.HAHA_API_BASE; });

  it("builds the URL with query params and parses JSON", async () => {
    globalThis.fetch = vi.fn(async (url) => {
      expect(String(url)).toBe("https://example.invalid/api/v1/stats");
      return new Response(JSON.stringify({ ok: true }), { status: 200 });
    });
    await expect(apiGet("/v1/stats")).resolves.toEqual({ ok: true });
  });

  it("omits undefined query params", async () => {
    globalThis.fetch = vi.fn(async (url) => {
      expect(String(url)).toBe("https://example.invalid/api/v1/season1/orders?day=20783");
      return new Response(JSON.stringify({ items: [] }), { status: 200 });
    });
    await apiGet("/v1/season1/orders", { day: 20783, status: undefined });
  });

  it("throws ApiError with status on a 404", async () => {
    globalThis.fetch = vi.fn(async () => new Response(JSON.stringify({ error: "not_found" }), { status: 404 }));
    const err = await apiGet("/v1/names/nope.haha").catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(404);
  });

  it("throws ApiError(0) when fetch itself fails", async () => {
    globalThis.fetch = vi.fn(async () => { throw new Error("boom"); });
    const err = await apiGet("/v1/stats").catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(0);
  });
});
