// Session + daily-usage stats for haha-meme-mcp.
// Purpose: record daily active users (DAU) and usage detail.
// - DAU = distinct client IPs seen on a UTC day (one IP ~= one user/device;
//   a client reconnecting from the same IP counts once).
// - sessions = distinct MCP session ids on that day (a reconnect = new session).
// - toolCalls / requests / top tools per day.
// Data lives in a small JSON file (default data/daily-stats.json under the
// working dir) so a restart does not lose the day's counts. Only aggregates
// are ever exposed over HTTP; raw IPs stay in this file on the server.
import fs from "node:fs";
import path from "node:path";

export interface SessionInfo {
  id: string;
  createdAt: string; // ISO
  lastSeenAt: string; // ISO
  ip: string;
  userAgent: string;
  requests: number;
  toolCalls: number;
  tools: Record<string, number>;
}

export interface DayStats {
  sessions: string[]; // distinct MCP session ids
  ips: string[]; // distinct client IPs
  requests: number;
  toolCalls: number;
  tools: Record<string, number>;
}

export function utcDate(d = new Date()): string {
  return d.toISOString().slice(0, 10);
}

const KEEP_DAYS = 90;
const HISTORY_LIMIT = 30;

function emptyDay(): DayStats {
  return { sessions: [], ips: [], requests: 0, toolCalls: 0, tools: {} };
}

function topTools(tools: Record<string, number>, n = 5): [string, number][] {
  return Object.entries(tools)
    .sort((a, b) => b[1] - a[1])
    .slice(0, n);
}

export class StatsStore {
  private file: string;
  private days: Record<string, DayStats> = {};

  constructor(file: string) {
    this.file = file;
    this.load();
  }

  private load(): void {
    try {
      if (!fs.existsSync(this.file)) return;
      const raw = JSON.parse(fs.readFileSync(this.file, "utf-8")) as {
        days?: Record<string, DayStats>;
      };
      if (raw && typeof raw.days === "object") {
        for (const [date, d] of Object.entries(raw.days)) {
          if (!d || typeof d !== "object") continue;
          this.days[date] = {
            sessions: Array.isArray(d.sessions) ? d.sessions : [],
            ips: Array.isArray(d.ips) ? d.ips : [],
            requests: typeof d.requests === "number" ? d.requests : 0,
            toolCalls: typeof d.toolCalls === "number" ? d.toolCalls : 0,
            tools: d.tools && typeof d.tools === "object" ? d.tools : {},
          };
        }
      }
    } catch {
      // Corrupt / unreadable file: start fresh rather than crash the server.
      this.days = {};
    }
  }

  private save(): void {
    try {
      const dir = path.dirname(this.file);
      fs.mkdirSync(dir, { recursive: true });
      // Prune days older than KEEP_DAYS.
      const cutoff = new Date(Date.now() - KEEP_DAYS * 24 * 3600 * 1000)
        .toISOString()
        .slice(0, 10);
      for (const date of Object.keys(this.days)) {
        if (date < cutoff) delete this.days[date];
      }
      const tmp = `${this.file}.tmp`;
      fs.writeFileSync(tmp, JSON.stringify({ days: this.days }, null, 2));
      fs.renameSync(tmp, this.file);
    } catch {
      // Stats must never break serving. A failed save just loses this event.
    }
  }

  private day(date: string): DayStats {
    if (!this.days[date]) this.days[date] = emptyDay();
    return this.days[date];
  }

  recordSessionOpen(info: SessionInfo): void {
    const d = this.day(utcDate(new Date(info.createdAt)));
    if (!d.sessions.includes(info.id)) d.sessions.push(info.id);
    if (info.ip && info.ip !== "unknown" && !d.ips.includes(info.ip)) {
      d.ips.push(info.ip);
    }
    this.save();
  }

  recordRequest(info: SessionInfo): void {
    const d = this.day(utcDate());
    d.requests += 1;
    this.save();
  }

  recordToolCall(info: SessionInfo, tool: string): void {
    const d = this.day(utcDate());
    d.toolCalls += 1;
    d.tools[tool] = (d.tools[tool] ?? 0) + 1;
    this.save();
  }

  today(date = utcDate()): {
    date: string;
    dau: number;
    sessions: number;
    requests: number;
    toolCalls: number;
    topTools: [string, number][];
  } {
    const d = this.days[date] ?? emptyDay();
    return {
      date,
      dau: d.ips.length,
      sessions: d.sessions.length,
      requests: d.requests,
      toolCalls: d.toolCalls,
      topTools: topTools(d.tools),
    };
  }

  history(limit = HISTORY_LIMIT): {
    date: string;
    dau: number;
    sessions: number;
    requests: number;
    toolCalls: number;
  }[] {
    return Object.keys(this.days)
      .sort()
      .slice(-limit)
      .map((date) => {
        const d = this.days[date];
        return {
          date,
          dau: d.ips.length,
          sessions: d.sessions.length,
          requests: d.requests,
          toolCalls: d.toolCalls,
        };
      });
  }
}

export function summarizeSession(info: SessionInfo): {
  id: string;
  since: string;
  lastSeen: string;
  client: string;
  requests: number;
  toolCalls: number;
  topTool: string | null;
} {
  const top = topTools(info.tools, 1)[0];
  return {
    id: info.id.slice(0, 8),
    since: info.createdAt,
    lastSeen: info.lastSeenAt,
    client: (info.userAgent || "unknown").slice(0, 80),
    requests: info.requests,
    toolCalls: info.toolCalls,
    topTool: top ? top[0] : null,
  };
}
