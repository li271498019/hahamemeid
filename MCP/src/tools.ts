// Tool registry: one entry per indexer read endpoint.
// Adding a new API later = adding one entry here (name, description,
// input schema, handler). Nothing else changes: the transport, the
// server skeleton and the existing tools are untouched.
//
// Descriptions are written for the LLM that calls the tool: what the
// tool answers, when to use it, what each parameter means.
// All tools are READ-ONLY. No tool can mint, trade, rate, sign or
// move funds. The indexer API itself is public and needs no key.

import { z } from "zod";
import { apiGet } from "./api.js";

export type ToolDef = {
  name: string;
  description: string;
  // Zod raw shape (field name -> zod schema), as McpServer.registerTool expects.
  inputSchema: Record<string, z.ZodTypeAny>;
  run: (args: Record<string, unknown>) => Promise<unknown>;
};

const aiId = z
  .string()
  .regex(/^0x[0-9a-fA-F]{64}$/, "aiId must be 0x followed by 64 hex chars (keccak256 of the .ai handle)")
  .describe("The .ai identity id: 0x followed by 64 hex chars (keccak256 of the .ai handle, e.g. hahameme.ai)");

const dayIndex = z
  .number()
  .int()
  .min(20781)
  .max(20795)
  .describe("Season 1 dayIndex, 20781 (2026-11-24) to 20795 (2026-12-09)");

const fullName = z
  .string()
  .describe("Full haha name with suffix, e.g. ha.haha or alice.meme");

const limit = z
  .number()
  .int()
  .min(1)
  .max(100)
  .optional()
  .describe("Max rows to return (1-100, default is the API default)");

const cursor = z
  .string()
  .optional()
  .describe("Pagination cursor from a previous response; omit for the first page");

const optDay = dayIndex
  .optional()
  .describe("Season 1 dayIndex; omit to use the current day");

export const TOOLS: ToolDef[] = [
  // ---- Season 1 ----
  {
    name: "get_season_day",
    description:
      "Season 1 status for one day: whether redemption is open, the Merkle root (on-chain vs recomputed), how many of the 20 daily slots are filled, and the snapshot block.",
    inputSchema: { day: dayIndex },
    run: (a) => apiGet(`/v1/season1/days/${a.day as number}`),
  },
  {
    name: "get_season_leaderboard",
    description:
      "Season 1 leaderboard for one day: the eligible .ai handles ranked by points, with their balances and tiers.",
    inputSchema: { day: dayIndex },
    run: (a) => apiGet(`/v1/season1/leaderboard/${a.day as number}`),
  },
  {
    name: "check_season_eligibility",
    description:
      "Check whether one .ai (by aiId) is eligible to redeem a 2-letter name on a Season 1 day, and why (balance, tier, quota, rotation rule). Use this before telling a user they can apply.",
    inputSchema: { aiId, day: optDay },
    run: (a) => apiGet(`/v1/season1/eligibility/${a.aiId as string}`, { day: a.day as number | undefined }),
  },
  {
    name: "get_season_proof",
    description:
      "Merkle proof for one .ai on a Season 1 day: balance, tier, root and the proof array the agent needs to call redeem on-chain. Returns 404 when the .ai has no entry that day.",
    inputSchema: { aiId, day: optDay },
    run: (a) => apiGet(`/v1/season1/proof/${a.aiId as string}`, { day: a.day as number | undefined }),
  },
  {
    name: "get_season_order",
    description:
      "One Season 1 redemption order by orderId: applicant, requested name, points spent, tier and status (Pending / Fulfilled / CreditOpen).",
    inputSchema: {
      orderId: z.number().int().min(1).describe("Order id, e.g. 1 or 2"),
    },
    run: (a) => apiGet(`/v1/season1/orders/${a.orderId as number}`),
  },
  {
    name: "list_season_orders",
    description:
      "Season 1 redemption orders for one day, newest first. Filter by status (Pending / Fulfilled / CreditOpen).",
    inputSchema: {
      day: dayIndex,
      status: z.string().optional().describe("Filter: Pending, Fulfilled or CreditOpen; omit for all"),
      limit,
      cursor,
    },
    run: (a) =>
      apiGet("/v1/season1/orders", {
        day: a.day as number,
        status: a.status as string | undefined,
        limit: a.limit as number | undefined,
        cursor: a.cursor as string | undefined,
      }),
  },
  {
    name: "get_season_verify",
    description:
      "Daily verification status for one .ai on a Season 1 day: whether the 30-point daily verification was already claimed and the nonce.",
    inputSchema: { aiId, day: optDay },
    run: (a) => apiGet(`/v1/season1/verify/${a.aiId as string}`, { day: a.day as number | undefined }),
  },
  {
    name: "list_season_findings",
    description:
      "Season 1 bug / finding reports: the adjudicated findings board (digest, title, status, reward).",
    inputSchema: {},
    run: () => apiGet("/v1/season1/findings"),
  },
  {
    name: "get_season_finding",
    description: "One Season 1 finding by its digest (0x + 64 hex chars).",
    inputSchema: {
      digest: z
        .string()
        .regex(/^0x[0-9a-fA-F]{64}$/, "digest must be 0x followed by 64 hex chars")
        .describe("Finding digest: 0x followed by 64 hex chars"),
    },
    run: (a) => apiGet(`/v1/season1/findings/${a.digest as string}`),
  },
  {
    name: "get_season_taskpack",
    description:
      "The task pack for one Season 1 day: the agent (agentId) and expected rating count/sum the daily verification checks against.",
    inputSchema: { day: dayIndex },
    run: (a) => apiGet(`/v1/season1/taskpack/${a.day as number}`),
  },

  // ---- Health ----
  {
    name: "get_health",
    description: "Check whether the haha.meme indexer API is up. Use this first if other tools fail.",
    inputSchema: {},
    run: () => apiGet("/health"),
  },

  // ---- Market ----
  {
    name: "list_listings",
    description:
      "Market listings (names for sale): price in BNB, seller, listed time. Sort by newest or by price. Search a label with q.",
    inputSchema: {
      limit,
      sort: z
        .string()
        .optional()
        .describe("Sort: listed_desc (newest), price_asc, price_desc; default listed_desc"),
      tld: z.string().optional().describe("Filter by suffix: haha or meme"),
      q: z.string().optional().describe("Search text for the name label"),
      cursor,
    },
    run: (a) =>
      apiGet("/v1/listings", {
        limit: a.limit as number | undefined,
        sort: a.sort as string | undefined,
        tld: a.tld as string | undefined,
        q: a.q as string | undefined,
        cursor: a.cursor as string | undefined,
      }),
  },
  {
    name: "list_trades",
    description: "Recent marketplace trades (completed name sales): name, price in BNB, buyer, seller, time.",
    inputSchema: { limit, cursor },
    run: (a) =>
      apiGet("/v1/trades", {
        limit: a.limit as number | undefined,
        cursor: a.cursor as string | undefined,
      }),
  },

  // ---- Names / agents ----
  {
    name: "list_names",
    description: "Recently minted .haha / .meme names, newest first.",
    inputSchema: { limit, cursor },
    run: (a) =>
      apiGet("/v1/names", {
        limit: a.limit as number | undefined,
        cursor: a.cursor as string | undefined,
      }),
  },
  {
    name: "list_events",
    description:
      "Recent on-chain events (mints, transfers, activations, ratings, listings, trades, validations) with plain-language details.",
    inputSchema: { limit, cursor },
    run: (a) =>
      apiGet("/v1/events", {
        limit: a.limit as number | undefined,
        cursor: a.cursor as string | undefined,
      }),
  },
  {
    name: "list_agents",
    description:
      "Agents (ERC-8004 identities), sorted by activation time, stars or review count. Each row carries the agent id, name, stars sum/count and generation.",
    inputSchema: {
      limit,
      sort: z
        .string()
        .optional()
        .describe("Sort: activated_desc, stars_desc, reviews_desc; default activated_desc"),
      cursor,
    },
    run: (a) =>
      apiGet("/v1/agents", {
        limit: a.limit as number | undefined,
        sort: a.sort as string | undefined,
        cursor: a.cursor as string | undefined,
      }),
  },
  {
    name: "get_agent_registration_by_name",
    description:
      "The standard EIP-8004 registration file for the agent that owns a name (by full name, e.g. ha.haha). Returns the agentId, identity, reputation and service endpoints in the standard format.",
    inputSchema: { name: fullName },
    run: (a) => apiGet(`/v1/agents/by-name/${encodeURIComponent(a.name as string)}/registration.json`),
  },
  {
    name: "get_agent_registration_by_id",
    description:
      "The standard EIP-8004 registration file for one agent by agentId (number). Returns the agentId, identity, reputation and service endpoints in the standard format.",
    inputSchema: {
      agentId: z.number().int().min(1).describe("Agent id as a number, e.g. 30"),
    },
    run: (a) => apiGet(`/v1/agents/${a.agentId as number}/registration.json`),
  },
  {
    name: "list_agent_validations",
    description:
      "Validation records for one agent by agentId: each request, the validator response (score 0-100), and any dispute state.",
    inputSchema: {
      agentId: z.number().int().min(1).describe("Agent id as a number, e.g. 30"),
    },
    run: (a) => apiGet(`/v1/agents/${a.agentId as number}/validations`),
  },
  {
    name: "get_validation",
    description: "One validation record by requestHash (0x + 64 hex chars): request, response score and dispute state.",
    inputSchema: {
      requestHash: z
        .string()
        .regex(/^0x[0-9a-fA-F]{64}$/, "requestHash must be 0x followed by 64 hex chars")
        .describe("Validation request hash: 0x followed by 64 hex chars"),
    },
    run: (a) => apiGet(`/v1/validations/${a.requestHash as string}`),
  },
  {
    name: "get_reputation_leaderboard",
    description: "Reputation leaderboard: agents ranked by star rating (count and sum).",
    inputSchema: { limit, cursor },
    run: (a) =>
      apiGet("/v1/leaderboard/reputation", {
        limit: a.limit as number | undefined,
        cursor: a.cursor as string | undefined,
      }),
  },
  {
    name: "list_name_generations",
    description:
      "All generations of one name: every agent generation that ever lived on this name (AgentActivated / AgentReset history). Reputation does NOT transfer between generations; a new generation starts at 0.",
    inputSchema: { name: fullName },
    run: (a) => apiGet(`/v1/names/${encodeURIComponent(a.name as string)}/generations`),
  },
  {
    name: "get_name_metadata",
    description: "Metadata for one name (tokenURI content): name, description and image.",
    inputSchema: { name: fullName },
    run: (a) => apiGet(`/v1/names/${encodeURIComponent(a.name as string)}/metadata`),
  },
  {
    name: "get_name",
    description:
      "One .haha / .meme name in full: owner (.ai first when known, else address), whether it is minted, primary name, resolver records, active agent and image URL. Returns 200 even when the name is not minted (check the minted field).",
    inputSchema: { name: fullName },
    run: (a) => apiGet(`/v1/names/${encodeURIComponent(a.name as string)}`),
  },
  {
    name: "list_owner_names",
    description: "All .haha / .meme names owned by one wallet address.",
    inputSchema: {
      address: z
        .string()
        .regex(/^0x[0-9a-fA-F]{40}$/, "address must be 0x followed by 40 hex chars")
        .describe("Wallet address: 0x followed by 40 hex chars"),
    },
    run: (a) => apiGet(`/v1/owners/${a.address as string}/names`),
  },
  {
    name: "get_owner_primary",
    description: "The primary (main) name of one wallet address, if the owner set one.",
    inputSchema: {
      address: z
        .string()
        .regex(/^0x[0-9a-fA-F]{40}$/, "address must be 0x followed by 40 hex chars")
        .describe("Wallet address: 0x followed by 40 hex chars"),
    },
    run: (a) => apiGet(`/v1/owners/${a.address as string}/primary`),
  },
  {
    name: "list_latest_reviews",
    description:
      "Latest reputation reviews: name, stars, text, reviewer haha id / .ai and date. The newest reviews first.",
    inputSchema: { limit, cursor },
    run: (a) =>
      apiGet("/v1/reviews/latest", {
        limit: a.limit as number | undefined,
        cursor: a.cursor as string | undefined,
      }),
  },
  {
    name: "get_points_leaderboard",
    description: "Points leaderboard: haha ids ranked by points (points are keyed by .ai, non-transferable).",
    inputSchema: { limit, cursor },
    run: (a) =>
      apiGet("/v1/leaderboard/points", {
        limit: a.limit as number | undefined,
        cursor: a.cursor as string | undefined,
      }),
  },
  {
    name: "get_stats",
    description:
      "Platform totals: agent interactions, participating .ai count, active agents, and registered .haha / .meme / total name counts. Start here for 'how big is haha.meme' questions.",
    inputSchema: {},
    run: () => apiGet("/v1/stats"),
  },
];
