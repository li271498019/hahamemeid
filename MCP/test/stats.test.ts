// Unit tests: StatsStore (DAU / session / tool-call counting + persistence).
// No network, no live API.
import { describe, it, expect, beforeEach, afterEach } from "vitest";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { StatsStore, utcDate, type SessionInfo } from "../src/stats";

function mkInfo(id: string, ip: string): SessionInfo {
  const now = new Date().toISOString();
  return {
    id, createdAt: now, lastSeenAt: now, ip,
    userAgent: "node", requests: 0, toolCalls: 0, tools: {},
  };
}

let dir: string;
let file: string;
beforeEach(() => {
  dir = fs.mkdtempSync(path.join(os.tmpdir(), "mcp-stats-"));
  file = path.join(dir, "daily-stats.json");
});
afterEach(() => { fs.rmSync(dir, { recursive: true, force: true }); });

describe("StatsStore", () => {
  it("starts empty: dau 0, sessions 0", () => {
    const s = new StatsStore(file);
    const t = s.today();
    expect(t.dau).toBe(0);
    expect(t.sessions).toBe(0);
    expect(t.toolCalls).toBe(0);
    expect(t.date).toBe(utcDate());
  });

  it("DAU counts distinct IPs; a reconnect from the same IP counts once", () => {
    const s = new StatsStore(file);
    s.recordSessionOpen(mkInfo("sess-1", "1.2.3.4"));
    s.recordSessionOpen(mkInfo("sess-2", "1.2.3.4")); // same IP, new session
    s.recordSessionOpen(mkInfo("sess-3", "5.6.7.8"));
    const t = s.today();
    expect(t.dau).toBe(2); // two IPs
    expect(t.sessions).toBe(3); // three sessions
  });

  it("counts tool calls and top tools", () => {
    const s = new StatsStore(file);
    const info = mkInfo("sess-1", "1.2.3.4");
    s.recordSessionOpen(info);
    s.recordToolCall(info, "get_stats");
    s.recordToolCall(info, "get_stats");
    s.recordToolCall(info, "get_name");
    const t = s.today();
    expect(t.toolCalls).toBe(3);
    expect(t.topTools[0]).toEqual(["get_stats", 2]);
    expect(t.topTools[1]).toEqual(["get_name", 1]);
  });

  it("counts requests", () => {
    const s = new StatsStore(file);
    const info = mkInfo("sess-1", "1.2.3.4");
    s.recordSessionOpen(info);
    s.recordRequest(info);
    s.recordRequest(info);
    expect(s.today().requests).toBe(2);
  });

  it("persists across restarts (reload from the same file)", () => {
    const s1 = new StatsStore(file);
    s1.recordSessionOpen(mkInfo("sess-1", "1.2.3.4"));
    s1.recordToolCall(mkInfo("sess-1", "1.2.3.4"), "get_stats");
    const s2 = new StatsStore(file); // new instance, same file
    const t = s2.today();
    expect(t.dau).toBe(1);
    expect(t.sessions).toBe(1);
    expect(t.toolCalls).toBe(1);
  });

  it("history returns one row per day, sorted", () => {
    const s = new StatsStore(file);
    s.recordSessionOpen(mkInfo("sess-1", "1.2.3.4"));
    const h = s.history();
    expect(h.length).toBe(1);
    expect(h[0].date).toBe(utcDate());
    expect(h[0].dau).toBe(1);
  });

  it("ignores a corrupt stats file instead of crashing", () => {
    fs.writeFileSync(file, "{not json");
    const s = new StatsStore(file);
    expect(s.today().dau).toBe(0);
    s.recordSessionOpen(mkInfo("sess-1", "1.2.3.4"));
    expect(s.today().dau).toBe(1);
  });
});
