// MCP Prompts (v1.2.0): a menu that teaches users what to ask.
// The server exposes Tools (what the agent can do) and Prompts (what the
// user can ask). A client that supports prompts (Claude Desktop, Claude Code)
// shows them as a menu / slash commands; picking one inserts the prompt text
// into the conversation, and the agent then uses the tools to answer.
// Prompts are only text — they never call tools themselves, never move funds.
//
// Season dayIndex: Season 1 day 20781 = 2026-11-24 (UTC), +1 per day.
// The server computes today's dayIndex at render time so the season prompts
// always ask about the right day without the user knowing the number.
import { z } from "zod";

export interface PromptMessage {
  role: "user";
  content: { type: "text"; text: string };
}

export interface PromptDef {
  name: string;
  title: string;
  description: string;
  argsSchema?: Record<string, z.ZodTypeAny>;
  render: (args: Record<string, string | undefined>) => PromptMessage[];
}

const SEASON_START_DAY = 20781; // 2026-11-24 (UTC)
const SEASON_START_UTC = Date.UTC(2026, 10, 24); // month 0-indexed: 10 = Nov

export function todaySeasonDay(d = new Date()): number {
  const todayUtc = Date.UTC(
    d.getUTCFullYear(),
    d.getUTCMonth(),
    d.getUTCDate(),
  );
  return SEASON_START_DAY + Math.floor((todayUtc - SEASON_START_UTC) / 86400000);
}

export function todayDate(d = new Date()): string {
  return d.toISOString().slice(0, 10);
}

function msg(text: string): PromptMessage[] {
  return [{ role: "user", content: { type: "text", text } }];
}

const nameArg = {
  name: z
    .string()
    .min(1)
    .describe("要查的 .haha / .meme 名字，如 ha.haha"),
};

export const PROMPTS: PromptDef[] = [
  {
    name: "getting_started",
    title: "上手指南",
    description:
      "第一次用？先看这个：通过 haha.meme 能查到哪些数据、该怎么问，附示例问题。",
    render: () =>
      msg(
        "请用中文介绍一下，通过 haha.meme MCP Server 可以查到哪些数据（名字、agent、信誉、验证、积分、市场、第一季），每一类各给 1-2 个示例问题，让我知道该怎么问你。回答要简短，只列出能查的东西和示例问题。",
      ),
  },
  {
    name: "platform_stats",
    title: "平台总数据",
    description: "平台现在有多少个名字、多少 .ai 参与过、多少活跃 agent。",
    render: () =>
      msg(
        "请告诉我 haha.meme 平台现在的数据：已注册的名字总数（.haha 和 .meme 各多少）、参与过的 .ai 数量、活跃 agent 数量、累计 agent 互动次数。",
      ),
  },
  {
    name: "check_name",
    title: "查一个名字",
    description: "查一个 .haha / .meme 名字：是否已铸造、持有人、活跃 agent、信誉。",
    argsSchema: nameArg,
    render: (args) =>
      msg(
        `请查询 ${args.name} 的详细信息：是否已铸造、持有人是谁、有没有设置主名、当前活跃的 agent 是谁、这个 agent 的信誉评分怎么样。`,
      ),
  },
  {
    name: "check_agent",
    title: "查一个 agent 的信誉与注册信息",
    description:
      "查一个 agent（用它的 .haha / .meme 名字）：注册文件、信誉评分、验证记录。",
    argsSchema: nameArg,
    render: (args) =>
      msg(
        `请查询 agent ${args.name} 的完整信息：它的注册文件（EIP-8004）写了什么、信誉评分怎么样（多少条评价、总分多少）、有没有通过验证、验证分数是多少。`,
      ),
  },
  {
    name: "reputation_leaderboard",
    title: "信誉榜",
    description: "信誉最高的 agent 是谁，前 10 名。",
    render: () =>
      msg(
        "请列出 haha.meme 上信誉最高的 agent（前 10 名），包括名字、星级、评价数量。",
      ),
  },
  {
    name: "season_today",
    title: "今天第一季",
    description: "今天第一季开没开、多少人有资格兑换、任务包是哪个 agent。",
    render: () => {
      const day = todaySeasonDay();
      return msg(
        `今天是 ${todayDate()}，第一季 dayIndex 是 ${day}。请告诉我今天第一季的情况：兑换开了吗、链上根匹配吗、有多少人有资格兑换、今天的任务包是哪个 agent。`,
      );
    },
  },
  {
    name: "season_leaderboard",
    title: "第一季资格榜",
    description: "今天第一季积分最高、最有资格兑换的人，前 10 名。",
    render: () => {
      const day = todaySeasonDay();
      return msg(
        `请列出今天第一季（dayIndex ${day}）积分最高的 10 个人，包括他们的 .ai、积分、是否有资格兑换。`,
      );
    },
  },
  {
    name: "season_eligibility",
    title: "查我的第一季兑换资格",
    description:
      "用你的 aiId 查今天有没有资格兑换 2 位名字。aiId 是你的 .ai 名字取 keccak256 得到的 0x 开头 64 位哈希，可在 haha.meme 赛季页的资格查询里看到。",
    argsSchema: {
      aiId: z
        .string()
        .regex(/^0x[0-9a-fA-F]{64}$/)
        .describe("你的 aiId（0x 开头 64 位，如 0x1736…70ed）"),
    },
    render: (args) => {
      const day = todaySeasonDay();
      return msg(
        `请查询 aiId ${args.aiId} 在今天第一季（dayIndex ${day}）有没有兑换资格：积分多少、排第几、能不能兑换、如果能兑换该怎么操作。`,
      );
    },
  },
  {
    name: "market_listings",
    title: "市场在售",
    description: "市场上有在卖的名字吗，最便宜的是哪个。",
    render: () =>
      msg(
        "请告诉我 haha.meme 市场上现在在售的名字，按价格从低到高列出前 10 个，包括名字、价格（BNB）、卖家。",
      ),
  },
  {
    name: "points_leaderboard",
    title: "积分榜",
    description: "积分最高的人是谁，前 10 名。",
    render: () =>
      msg(
        "请列出 haha.meme 上积分最高的 10 个人，包括他们的 haha id 和积分。",
      ),
  },
  {
    name: "latest_reviews",
    title: "最新评价",
    description: "最近谁给谁打了分、打了几星、说了什么。",
    render: () =>
      msg(
        "请列出 haha.meme 上最新的 5 条信誉评价，包括被评的 agent、打了几星、评价内容、评价人是谁、什么时候。",
      ),
  },
];
