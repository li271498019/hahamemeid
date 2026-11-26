// Unit tests: prompt registry shape + season dayIndex math + render output.
// No network, no live API.
import { describe, it, expect } from "vitest";
import { PROMPTS, todaySeasonDay, todayDate } from "../src/prompts";

describe("prompt registry", () => {
  it("has 11 prompts, unique names, every prompt has a title and description", () => {
    expect(PROMPTS.length).toBe(11);
    const names = PROMPTS.map((p) => p.name);
    expect(new Set(names).size).toBe(names.length);
    for (const p of PROMPTS) {
      expect(p.title.length).toBeGreaterThan(1);
      expect(p.description.length).toBeGreaterThan(10);
      expect(typeof p.render).toBe("function");
    }
  });

  it("covers the expected prompt names", () => {
    const names = new Set(PROMPTS.map((p) => p.name));
    for (const n of [
      "getting_started", "platform_stats", "check_name", "check_agent",
      "reputation_leaderboard", "season_today", "season_leaderboard",
      "season_eligibility", "market_listings", "points_leaderboard",
      "latest_reviews",
    ]) {
      expect(names.has(n)).toBe(true);
    }
  });

  it("every render returns exactly one user text message", () => {
    for (const p of PROMPTS) {
      const args: Record<string, string> = {};
      if (p.argsSchema) {
        for (const key of Object.keys(p.argsSchema)) {
          args[key] =
            key === "aiId" ? "0x" + "a".repeat(64) : "ha.haha";
        }
      }
      const messages = p.render(args);
      expect(messages.length).toBe(1);
      expect(messages[0].role).toBe("user");
      expect(messages[0].content.type).toBe("text");
      expect(messages[0].content.text.length).toBeGreaterThan(10);
    }
  });

  it("check_name render fills in the name", () => {
    const p = PROMPTS.find((x) => x.name === "check_name")!;
    const text = p.render({ name: "ha.haha" })[0].content.text;
    expect(text).toContain("ha.haha");
  });

  it("season_eligibility requires a 0x + 64 hex aiId", () => {
    const p = PROMPTS.find((x) => x.name === "season_eligibility")!;
    const schema = p.argsSchema!.aiId;
    expect(() => schema.parse("not-an-aiid")).toThrow();
    expect(() => schema.parse("0x" + "a".repeat(64))).not.toThrow();
    expect(() => schema.parse("0x" + "a".repeat(63))).toThrow();
  });
});

describe("todaySeasonDay", () => {
  it("2026-11-24 is day 20781, 2026-11-26 is day 20783", () => {
    expect(todaySeasonDay(new Date("2026-11-24T00:00:00Z"))).toBe(20781);
    expect(todaySeasonDay(new Date("2026-11-25T12:00:00Z"))).toBe(20782);
    expect(todaySeasonDay(new Date("2026-11-26T00:00:00Z"))).toBe(20783);
    expect(todaySeasonDay(new Date("2026-12-09T00:00:00Z"))).toBe(20796);
  });

  it("season_today render contains today's dayIndex", () => {
    const p = PROMPTS.find((x) => x.name === "season_today")!;
    const text = p.render({})[0].content.text;
    expect(text).toContain(String(todaySeasonDay()));
    expect(text).toContain(todayDate());
  });
});
