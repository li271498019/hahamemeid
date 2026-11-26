// Smoke test: exercises every tool against the live haha.meme API,
// then verifies the MCP transport over HTTP with a real client.
// Run:  HAHA_API_BASE=https://haha.meme/api npm run smoke
// A tool PASSES when it returns data or a clean API 404 (no such entry).
// It FAILS on network errors, timeouts or unexpected exceptions.

import { spawn } from "node:child_process";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StreamableHTTPClientTransport } from "@modelcontextprotocol/sdk/client/streamableHttp.js";
import { TOOLS } from "../dist/tools.js";

const BASE = process.env.HAHA_API_BASE ?? "https://haha.meme/api";
process.env.HAHA_API_BASE = BASE;

const HAHA_AIID = "0x17367f0410c1e90ee380b4a47be765a910dbf2be0db717b1da19e1d6f03670ed"; // hahameme.ai
const L_ADDR = "0xe40a0c726fd2f990713ade7380c89800f4e8ac49"; // hahameme.ai wallet

// Representative args per tool (must be valid shapes).
const ARGS = {
  get_season_day: { day: 20783 },
  get_season_leaderboard: { day: 20783 },
  check_season_eligibility: { aiId: HAHA_AIID, day: 20783 },
  get_season_proof: { aiId: HAHA_AIID, day: 20783 },
  get_season_order: { orderId: 1 },
  list_season_orders: { day: 20783, limit: 5 },
  get_season_verify: { aiId: HAHA_AIID, day: 20783 },
  list_season_findings: {},
  get_season_finding: { digest: "0x" + "0".repeat(64) },
  get_season_taskpack: { day: 20783 },
  get_health: {},
  list_listings: { limit: 5 },
  list_trades: { limit: 5 },
  list_names: { limit: 5 },
  list_events: { limit: 5 },
  list_agents: { limit: 5 },
  get_agent_registration_by_name: { name: "ha.haha" },
  get_agent_registration_by_id: { agentId: 30 },
  list_agent_validations: { agentId: 30 },
  get_validation: { requestHash: "0x" + "0".repeat(64) },
  get_reputation_leaderboard: { limit: 5 },
  list_name_generations: { name: "ha.haha" },
  get_name_metadata: { name: "ha.haha" },
  get_name: { name: "ha.haha" },
  list_owner_names: { address: L_ADDR },
  get_owner_primary: { address: L_ADDR },
  list_latest_reviews: { limit: 5 },
  get_points_leaderboard: { limit: 5 },
  get_stats: {},
};

function short(v) {
  const s = typeof v === "string" ? v : JSON.stringify(v);
  return s.length > 220 ? s.slice(0, 220) + "…" : s;
}

async function phaseA() {
  console.log(`\n== Phase A: ${TOOLS.length} tools vs live API (${BASE}) ==`);
  let pass = 0;
  for (const t of TOOLS) {
    const args = ARGS[t.name] ?? {};
    try {
      const out = await t.run(args);
      console.log(`PASS ${t.name}: ${short(out)}`);
      pass++;
    } catch (e) {
      // A clean API 404 (no such entry) means the tool works; the data just isn't there.
      const msg = e instanceof Error ? e.message : String(e);
      if (/API 404/.test(msg)) {
        console.log(`PASS ${t.name}: (clean 404, no such entry) ${short(msg)}`);
        pass++;
      } else {
        console.log(`FAIL ${t.name}: ${short(msg)}`);
      }
    }
  }
  console.log(`Phase A: ${pass}/${TOOLS.length} passed`);
  return pass === TOOLS.length;
}

function waitForHealth(port, timeoutMs = 15000) {
  const start = Date.now();
  return new Promise((resolve, reject) => {
    const tick = async () => {
      try {
        const r = await fetch(`http://127.0.0.1:${port}/health`);
        if (r.ok) return resolve(true);
      } catch { /* not up yet */ }
      if (Date.now() - start > timeoutMs) return reject(new Error("server did not come up"));
      setTimeout(tick, 300);
    };
    tick();
  });
}

async function phaseB() {
  console.log(`\n== Phase B: MCP client over HTTP ==`);
  const port = 3344;
  const child = spawn("node", ["dist/index.js"], {
    env: { ...process.env, PORT: String(port), HOST: "127.0.0.1", HAHA_API_BASE: BASE },
    stdio: ["ignore", "pipe", "pipe"],
  });
  child.stderr.on("data", (d) => process.stderr.write(`[server] ${d}`));
  try {
    await waitForHealth(port);
    const client = new Client({ name: "haha-mcp-smoke", version: "1.0.0" }, { capabilities: {} });
    const transport = new StreamableHTTPClientTransport(new URL(`http://127.0.0.1:${port}/mcp`));
    await client.connect(transport);
    const tools = await client.listTools();
    console.log(`listTools: ${tools.tools.length} tools (expect ${TOOLS.length})`);
    if (tools.tools.length !== TOOLS.length) {
      console.log("FAIL: tool count mismatch");
      return false;
    }
    for (const [name, args] of [
      ["get_stats", {}],
      ["get_name", { name: "ha.haha" }],
      ["get_season_day", { day: 20783 }],
    ]) {
      const res = await client.callTool({ name, arguments: args });
      const text = res.content?.[0]?.text ?? "";
      console.log(`callTool ${name}: isError=${!!res.isError} ${short(text)}`);
      if (res.isError) {
        console.log(`FAIL: ${name} returned isError`);
        return false;
      }
    }
    await client.close();
    console.log("Phase B: passed");
    return true;
  } finally {
    child.kill();
  }
}

const a = await phaseA();
const b = await phaseB();
console.log(`\nSMOKE ${a && b ? "PASSED" : "FAILED"}`);
process.exit(a && b ? 0 : 1);
