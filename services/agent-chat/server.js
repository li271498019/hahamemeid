// haha-agent-chat — channel service for the haha agent dialog.
// Frozen spec v1.0 (~/workspace/haha-agent-channel-spec-frozen-v1.md) is the
// sole authority. No behaviour beyond the spec is implemented.
// Stack: Node.js (>=20) + pg + js-sha3, no web framework (built-in http).
// Listens on 127.0.0.1:8899 only; nginx reverse-proxies /agent-chat/ to it.
import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import pg from "pg";
import pkg from "js-sha3";
const { keccak256 } = pkg;
import { renderPersona } from "./persona.js";

// ---------------------------------------------------------------- config
const HOST = process.env.HOST || "127.0.0.1";
const PORT = parseInt(process.env.PORT || "8899", 10);
const CHANNEL_API_KEY = process.env.CHANNEL_API_KEY || "";
const INDEXER_API_BASE = (process.env.INDEXER_API_BASE || "http://127.0.0.1:8787").replace(/\/$/, "");
const IMAGE_DIR = process.env.IMAGE_DIR || "/var/www/haha.meme/agent-images";
const PUBLIC_BASE_URL = (process.env.PUBLIC_BASE_URL || "https://haha.meme/agent-chat").replace(/\/$/, "");
const DB = {
  host: process.env.PGHOST || "127.0.0.1",
  port: parseInt(process.env.PGPORT || "5432", 10),
  database: process.env.PGDATABASE || "haha_indexer",
  user: process.env.PGUSER || "haha",
  password: process.env.PGPASSWORD || "",
  max: parseInt(process.env.PGMAX || "10", 10),
};
if (!CHANNEL_API_KEY) {
  console.error("FATAL: CHANNEL_API_KEY is not set");
  process.exit(2);
}

const pool = new pg.Pool(DB);
pool.on("error", (e) => console.error("pg pool error:", e.message));

// ---------------------------------------------------------------- helpers
function isoNow(d = new Date()) {
  return d.toISOString().replace(/\.\d{3}Z$/, "Z");
}
function num(v) {
  return typeof v === "string" ? Number(v) : v;
}
function sendJson(res, status, obj) {
  const body = JSON.stringify(obj);
  res.writeHead(status, { "Content-Type": "application/json" });
  res.end(body);
}
function sendError(res, status, code, message) {
  sendJson(res, status, { error: code, message });
}
function readBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    let size = 0;
    req.on("data", (c) => {
      size += c.length;
      if (size > 64 * 1024 * 1024) {
        reject(new Error("body too large"));
        req.destroy();
        return;
      }
      chunks.push(c);
    });
    req.on("end", () => resolve(Buffer.concat(chunks).toString("utf8")));
    req.on("error", reject);
  });
}
async function readJson(req, res) {
  let raw;
  try {
    raw = await readBody(req);
  } catch {
    sendError(res, 400, "invalid_field", "Request body could not be read.");
    return null;
  }
  if (!raw.trim()) {
    sendError(res, 400, "missing_field", "Request body is empty.");
    return null;
  }
  try {
    return JSON.parse(raw);
  } catch {
    sendError(res, 400, "invalid_field", "Request body is not valid JSON.");
    return null;
  }
}
function clientIp(req) {
  const xff = req.headers["x-forwarded-for"];
  if (typeof xff === "string" && xff.trim()) return xff.split(",")[0].trim();
  return req.socket.remoteAddress || "unknown";
}
function log(req, status, ms) {
  console.log(`${new Date().toISOString()} ${req.method} ${req.url} -> ${status} ${ms}ms`);
}

// ------------------------------------------------------------ id helpers
// ULID: 26 Crockford base32 chars (lowercase), time-sortable, globally
// unique. questionId = "q_" + ulid (28 chars total, spec §5.0).
const CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ";
function ulid() {
  let time = Date.now();
  let timeChars = "";
  for (let i = 0; i < 10; i++) {
    timeChars = CROCKFORD[time % 32] + timeChars;
    time = Math.floor(time / 32);
  }
  let n = 0n;
  for (const b of crypto.randomBytes(10)) n = (n << 8n) | BigInt(b);
  let randChars = "";
  for (let i = 0; i < 16; i++) {
    randChars = CROCKFORD[Number(n % 32n)] + randChars;
    n = n / 32n;
  }
  return (timeChars + randChars).toLowerCase();
}
function newQuestionId() {
  return "q_" + ulid();
}
// imageId: 22 URL-safe chars (A-Za-z0-9-_), crypto random (spec §13.3).
const IMG_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_";
function newImageId() {
  const bytes = crypto.randomBytes(22);
  let s = "";
  for (const b of bytes) s += IMG_ALPHABET[b % 64];
  return s;
}
function imageUrl(imageId) {
  return `${PUBLIC_BASE_URL}/images/${imageId}`;
}

// ------------------------------------------------------- agent / memory
async function getAgent(agentId) {
  const { rows } = await pool.query(
    `SELECT a.agent_id, a.active, n.full_name
       FROM agents a JOIN names n ON n.token_id = a.name_token_id
      WHERE a.agent_id = $1`,
    [agentId],
  );
  if (!rows.length) return null;
  return { agentId: num(rows[0].agent_id), active: rows[0].active, fullName: rows[0].full_name };
}
async function getOrCreateMemory(agentId, name) {
  const found = await pool.query("SELECT agent_id, name, persona_md, entries FROM agent_memory WHERE agent_id = $1", [agentId]);
  if (found.rows.length) {
    const r = found.rows[0];
    return { agentId: num(r.agent_id), name: r.name, personaMd: r.persona_md, entries: r.entries || [] };
  }
  const personaMd = renderPersona(name, agentId);
  const now = new Date();
  const ins = await pool.query(
    `INSERT INTO agent_memory (agent_id, name, persona_md, entries, updated_at, created_at)
     VALUES ($1, $2, $3, '[]'::jsonb, $4, $4)
     ON CONFLICT (agent_id) DO NOTHING RETURNING agent_id, name, persona_md, entries`,
    [agentId, name, personaMd, now],
  );
  if (ins.rows.length) {
    const r = ins.rows[0];
    return { agentId: num(r.agent_id), name: r.name, personaMd: r.persona_md, entries: r.entries || [] };
  }
  const again = await pool.query("SELECT agent_id, name, persona_md, entries FROM agent_memory WHERE agent_id = $1", [agentId]);
  const r = again.rows[0];
  return { agentId: num(r.agent_id), name: r.name, personaMd: r.persona_md, entries: r.entries || [] };
}
async function applyMemoryUpdates(agentId, updates) {
  if (!updates || !updates.length) return;
  const { rows } = await pool.query("SELECT entries FROM agent_memory WHERE agent_id = $1", [agentId]);
  if (!rows.length) return;
  let entries = Array.isArray(rows[0].entries) ? [...rows[0].entries] : [];
  for (const u of updates) {
    if (u.op === "set") {
      const now = isoNow();
      const i = entries.findIndex((e) => e.key === u.key);
      if (i >= 0) entries[i] = { key: u.key, value: u.value, updated_at: now };
      else entries.push({ key: u.key, value: u.value, updated_at: now });
    } else if (u.op === "delete") {
      entries = entries.filter((e) => e.key !== u.key);
    }
  }
  await pool.query("UPDATE agent_memory SET entries = $1::jsonb, updated_at = $2 WHERE agent_id = $3", [
    JSON.stringify(entries),
    new Date(),
    agentId,
  ]);
}

// ------------------------------------------------- owner verification (§8)
// aiId -> wallet address, via the indexer handle_cache table.
// handle_cache stores (user_address, handle) where handle is the label
// WITHOUT the ".ai" suffix (e.g. "hahameme"), and aiId = keccak256(handle).
// There is no indexer HTTP endpoint for this, so the DB is the source.
// The map is cached in memory and refreshed every 10 minutes and on miss.
let handleCache = new Map();
let handleCacheAt = 0;
const HANDLE_CACHE_TTL_MS = 10 * 60 * 1000;
async function loadHandleCache() {
  const { rows } = await pool.query("SELECT user_address, handle FROM handle_cache");
  const map = new Map();
  for (const r of rows) {
    if (!r.handle) continue;
    const aiIdHex = "0x" + keccak256(r.handle);
    const addr = "0x" + Buffer.from(r.user_address).toString("hex");
    map.set(aiIdHex.toLowerCase(), addr.toLowerCase());
  }
  handleCache = map;
  handleCacheAt = Date.now();
  return map;
}
async function aiIdToAddress(aiIdHex) {
  const key = aiIdHex.toLowerCase();
  if (handleCache.has(key)) return handleCache.get(key);
  if (Date.now() - handleCacheAt > HANDLE_CACHE_TTL_MS) await loadHandleCache();
  else await loadHandleCache(); // miss: refresh once, the cache may be stale
  return handleCache.get(key) || null;
}
// name -> owner address, via the indexer read-only HTTP API (spec §8.1).
async function nameOwner(name) {
  try {
    const res = await fetch(`${INDEXER_API_BASE}/v1/names/${encodeURIComponent(name)}`, {
      signal: AbortSignal.timeout(5000),
    });
    if (!res.ok) return null;
    const body = await res.json();
    if (!body || body.minted !== true || !body.owner) return null;
    return String(body.owner).toLowerCase();
  } catch (e) {
    console.error("nameOwner lookup failed:", e.message);
    return null;
  }
}
// Returns true only when aiId resolves to an address that equals the
// on-chain owner of `name`. Any failure is fail-closed (false -> 403).
async function verifyOwner(aiId, name) {
  if (typeof aiId !== "string" || !/^0x[0-9a-f]{64}$/.test(aiId)) return false;
  const addr = await aiIdToAddress(aiId);
  if (!addr) return false;
  const owner = await nameOwner(name);
  if (!owner) return false;
  return addr === owner;
}

// -------------------------------------------------------- rate limiting
// POST /questions: one submit per agentId per 5s, no daily cap (spec §7.1).
const submitLast = new Map();
function checkSubmitLimit(agentId) {
  const now = Date.now();
  const last = submitLast.get(agentId);
  if (last !== undefined && now - last < 5000) return false;
  submitLast.set(agentId, now);
  return true;
}
// GET /images: 60/min per IP (spec §7.3). Sliding window.
const imageHits = new Map();
function checkImageLimit(ip) {
  const now = Date.now();
  const arr = (imageHits.get(ip) || []).filter((t) => now - t < 60000);
  if (arr.length >= 60) {
    imageHits.set(ip, arr);
    return false;
  }
  arr.push(now);
  imageHits.set(ip, arr);
  return true;
}
// GET /questions/pending: abuse guard — sustained >2/sec is abuse (§7.2).
// Allow 20 requests per 10s per token (normal polling is 1/sec = 10/10s).
const pendingHits = new Map();
function checkPendingLimit(token) {
  const now = Date.now();
  const arr = (pendingHits.get(token) || []).filter((t) => now - t < 10000);
  if (arr.length >= 20) {
    pendingHits.set(token, arr);
    return false;
  }
  arr.push(now);
  pendingHits.set(token, arr);
  return true;
}

// ---------------------------------------------------------------- images
const MAX_IMAGE_B64 = 20971520; // 20MB, spec §13.2
function isValidBase64(s) {
  if (typeof s !== "string" || !s.length) return false;
  if (s.length % 4 !== 0) return false;
  if (!/^[A-Za-z0-9+/]+={0,2}$/.test(s)) return false;
  try {
    const buf = Buffer.from(s, "base64");
    return buf.length > 0;
  } catch {
    return false;
  }
}
function validateImages(images) {
  if (images === undefined || images === null) return { ok: true, list: [] };
  if (!Array.isArray(images)) return { ok: false, code: "invalid_image", message: "images must be an array." };
  if (images.length > 1) return { ok: false, code: "too_many_images", message: "At most one image per answer." };
  for (const im of images) {
    if (!im || typeof im !== "object") return { ok: false, code: "invalid_image", message: "Each image must be an object." };
    if (im.mime !== "image/png" && im.mime !== "image/jpeg") {
      return { ok: false, code: "invalid_image", message: "mime must be image/png or image/jpeg." };
    }
    if (typeof im.data !== "string" || !isValidBase64(im.data)) {
      return { ok: false, code: "invalid_image", message: "data must be valid base64." };
    }
    if (im.data.length > MAX_IMAGE_B64) {
      return { ok: false, code: "image_too_large", message: "A single base64 image must not exceed 20MB." };
    }
  }
  return { ok: true, list: images };
}
function validateMemory(memory) {
  if (memory === undefined || memory === null) return { ok: true, list: [] };
  if (!Array.isArray(memory)) return { ok: false };
  if (memory.length > 10) return { ok: false };
  for (const m of memory) {
    if (!m || typeof m !== "object") return { ok: false };
    if (m.op !== "set" && m.op !== "delete") return { ok: false };
    if (typeof m.key !== "string" || !m.key.trim() || m.key.length > 100) return { ok: false };
    if (m.op === "set" && (typeof m.value !== "string" || !m.value.trim() || m.value.length > 500)) return { ok: false };
  }
  return { ok: true, list: memory };
}

// ---------------------------------------------------------------- timeout
const TIMEOUT_MS = 60000;
function isTimedOut(createdAt) {
  return Date.now() - new Date(createdAt).getTime() > TIMEOUT_MS;
}
async function sweepTimeouts() {
  try {
    const r = await pool.query(
      "UPDATE agent_questions SET status = 'timeout' WHERE status = 'queued' AND created_at < NOW() - INTERVAL '60 seconds'",
    );
    if (r.rowCount > 0) console.log(`timeout sweeper: marked ${r.rowCount} question(s) timeout`);
  } catch (e) {
    console.error("timeout sweeper error:", e.message);
  }
}
setInterval(sweepTimeouts, 10000);

// ----------------------------------------------------------- daily cleanup
async function dailyCleanup() {
  console.log("daily cleanup: start");
  const client = await pool.connect();
  try {
    await client.query("BEGIN");
    const hist = await client.query("DELETE FROM agent_chat_history WHERE created_at < NOW() - INTERVAL '30 days'");
    const ques = await client.query("DELETE FROM agent_questions WHERE created_at < NOW() - INTERVAL '30 days'");
    const imgs = await client.query(
      "SELECT image_id, path FROM agent_images WHERE created_at < NOW() - INTERVAL '3 days'",
    );
    let filesRemoved = 0;
    for (const row of imgs.rows) {
      try {
        fs.unlinkSync(row.path);
        filesRemoved++;
      } catch (e) {
        if (e.code !== "ENOENT") console.error("cleanup unlink failed:", row.path, e.message);
      }
    }
    const imgDel = await client.query("DELETE FROM agent_images WHERE created_at < NOW() - INTERVAL '3 days'");
    // Burned agents (spec §14.1 / §10.4: delete immediately on burn, do
    // NOT wait 30 days; §14.5's "burned over 30 days ago" is stale text).
    const burned = await client.query(
      `SELECT am.agent_id FROM agent_memory am
          JOIN agents a ON a.agent_id = am.agent_id
         WHERE a.active = false`,
    );
    let burnedCount = 0;
    for (const row of burned.rows) {
      const aid = row.agent_id;
      const bImgs = await client.query("SELECT path FROM agent_images WHERE agent_id = $1", [aid]);
      for (const b of bImgs.rows) {
        try {
          fs.unlinkSync(b.path);
        } catch (e) {
          if (e.code !== "ENOENT") console.error("cleanup unlink failed:", b.path, e.message);
        }
      }
      await client.query("DELETE FROM agent_images WHERE agent_id = $1", [aid]);
      await client.query("DELETE FROM agent_questions WHERE agent_id = $1", [aid]);
      await client.query("DELETE FROM agent_chat_history WHERE agent_id = $1", [aid]);
      await client.query("DELETE FROM agent_memory WHERE agent_id = $1", [aid]);
      burnedCount++;
    }
    await client.query("COMMIT");
    console.log(
      `daily cleanup: done (history ${hist.rowCount}, questions ${ques.rowCount}, images ${imgDel.rowCount} rows + ${filesRemoved} files, burned agents ${burnedCount})`,
    );
  } catch (e) {
    await client.query("ROLLBACK").catch(() => {});
    console.error("daily cleanup error:", e.message);
  } finally {
    client.release();
  }
}
function scheduleDailyCleanup() {
  const now = new Date();
  const next = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() + 1, 0, 0, 0));
  const ms = next.getTime() - now.getTime();
  setTimeout(() => {
    dailyCleanup();
    setInterval(dailyCleanup, 24 * 60 * 60 * 1000);
  }, ms);
  console.log(`daily cleanup scheduled in ${Math.round(ms / 1000)}s (00:00 UTC)`);
}

// ---------------------------------------------------------------- handlers
function checkBearer(req) {
  const h = req.headers["authorization"] || "";
  const m = /^Bearer\s+(.+)$/.exec(h);
  if (!m) return false;
  const token = m[1].trim();
  if (!token) return false;
  // Constant-time comparison to avoid timing leaks.
  const a = Buffer.from(token);
  const b = Buffer.from(CHANNEL_API_KEY);
  return a.length === b.length && crypto.timingSafeEqual(a, b);
}
function isInt(v) {
  return typeof v === "number" && Number.isInteger(v);
}

async function handleHealth(req, res) {
  try {
    await pool.query("SELECT 1");
    sendJson(res, 200, { ok: true });
  } catch (e) {
    console.error("health db check failed:", e.message);
    sendJson(res, 503, { ok: false });
  }
}

const NAME_RE = /^[a-z0-9]+[a-z0-9-]*\.(haha|meme)$/;
async function handlePostQuestions(req, res) {
  const body = await readJson(req, res);
  if (body === null) return;
  // ---- field validation (400) ----
  if (body.agentId === undefined) return sendError(res, 400, "missing_field", "agentId is required.");
  if (!isInt(body.agentId) || body.agentId < 1) return sendError(res, 400, "invalid_field", "agentId must be a positive integer.");
  if (body.name === undefined) return sendError(res, 400, "missing_field", "name is required.");
  if (typeof body.name !== "string" || !NAME_RE.test(body.name)) return sendError(res, 400, "invalid_field", "name must be a domain like example.haha or example.meme.");
  if (body.aiId === undefined) return sendError(res, 400, "missing_field", "aiId is required.");
  if (typeof body.aiId !== "string") return sendError(res, 400, "invalid_field", "aiId must be a string.");
  if (body.lang === undefined) return sendError(res, 400, "missing_field", "lang is required.");
  if (body.lang !== "zh" && body.lang !== "en") return sendError(res, 400, "invalid_field", "lang must be zh or en.");
  if (body.message === undefined) return sendError(res, 400, "missing_field", "message is required.");
  if (typeof body.message !== "string" || !body.message.trim() || body.message.trim().length > 2000) {
    return sendError(res, 400, "message_too_long", "message must be 1-2000 characters.");
  }
  const type = body.type === undefined ? "chat" : body.type;
  if (type !== "chat" && type !== "save") return sendError(res, 400, "invalid_field", "type must be chat or save.");
  const message = body.message.trim();
  const name = body.name.toLowerCase();
  // ---- agent exists and is active (404) ----
  let agent;
  try {
    agent = await getAgent(body.agentId);
  } catch (e) {
    console.error("getAgent error:", e.message);
    return sendError(res, 500, "internal_error", "Internal error.");
  }
  if (!agent || !agent.active) return sendError(res, 404, "agent_not_found", "Agent does not exist or is not active.");
  if (agent.fullName.toLowerCase() !== name) return sendError(res, 400, "name_mismatch", "name does not match the agentId.");
  // ---- submit rate limit: 1 per 5s per agent (429) ----
  if (!checkSubmitLimit(body.agentId)) {
    return sendJson(res, 429, { error: "rate_limited", message: "One question per 5 seconds per agent.", retry_after_seconds: 5 });
  }
  // ---- owner verification, fail-closed (403) ----
  let ok;
  try {
    ok = await verifyOwner(body.aiId, name);
  } catch (e) {
    console.error("verifyOwner error:", e.message);
    return sendError(res, 500, "internal_error", "Internal error.");
  }
  if (!ok) return sendError(res, 403, "not_owner", "aiId does not belong to the owner of this name.");
  // ---- persist ----
  const questionId = newQuestionId();
  const now = new Date();
  const client = await pool.connect();
  try {
    await client.query("BEGIN");
    await client.query(
      `INSERT INTO agent_questions (question_id, agent_id, name, message, lang, ai_id, type, status, created_at)
       VALUES ($1, $2, $3, $4, $5, $6, $7, 'queued', $8)`,
      [questionId, body.agentId, name, message, body.lang, body.aiId, type, now],
    );
    await client.query(
      `INSERT INTO agent_chat_history (agent_id, question_id, role, text, created_at)
       VALUES ($1, $2, 'user', $3, $4)`,
      [body.agentId, questionId, message, now],
    );
    await client.query("COMMIT");
  } catch (e) {
    await client.query("ROLLBACK").catch(() => {});
    console.error("post questions insert error:", e.message);
    return sendError(res, 500, "internal_error", "Internal error.");
  } finally {
    client.release();
  }
  // Ensure the memory row exists (default persona) so pending can serve it.
  try {
    await getOrCreateMemory(body.agentId, name);
  } catch (e) {
    console.error("getOrCreateMemory error:", e.message);
  }
  sendJson(res, 200, { questionId, status: "queued" });
}

async function handlePending(req, res) {
  if (!checkBearer(req)) return sendError(res, 401, "unauthorized", "Missing or invalid Bearer token.");
  const token = (req.headers["authorization"] || "").slice(7).trim();
  if (!checkPendingLimit(token)) {
    return sendJson(res, 429, { error: "rate_limited", message: "Too many pending fetches.", retry_after_seconds: 1 });
  }
  let rows;
  try {
    const r = await pool.query(
      `SELECT question_id, agent_id, name, message, type, lang, created_at
         FROM agent_questions
        WHERE status = 'queued' AND created_at >= NOW() - INTERVAL '60 seconds'
        ORDER BY created_at ASC
        LIMIT 50`,
    );
    rows = r.rows;
  } catch (e) {
    console.error("pending query error:", e.message);
    return sendError(res, 500, "internal_error", "Internal error.");
  }
  const memCache = new Map();
  const questions = [];
  for (const row of rows) {
    const agentId = num(row.agent_id);
    let mem = memCache.get(agentId);
    if (!mem) {
      try {
        mem = await getOrCreateMemory(agentId, row.name);
      } catch (e) {
        console.error("pending memory error:", e.message);
        return sendError(res, 500, "internal_error", "Internal error.");
      }
      memCache.set(agentId, mem);
    }
    const q = {
      questionId: row.question_id,
      agentId,
      name: row.name,
      message: row.message,
      type: row.type || "chat",
      lang: row.lang,
      createdAt: isoNow(new Date(row.created_at)),
      persona: mem.personaMd,
      memory: Array.isArray(mem.entries) ? mem.entries : [],
    };
    if (q.type === "save") {
      try {
        const h = await pool.query(
          `SELECT role, text, created_at FROM agent_chat_history
            WHERE agent_id = $1 AND created_at >= NOW() - INTERVAL '30 days'
            ORDER BY created_at DESC LIMIT 50`,
          [agentId],
        );
        q.history = h.rows.reverse().map((m) => ({
          role: m.role,
          text: m.text,
          at: isoNow(new Date(m.created_at)),
        }));
      } catch (e) {
        console.error("pending history error:", e.message);
        return sendError(res, 500, "internal_error", "Internal error.");
      }
    }
    questions.push(q);
  }
  sendJson(res, 200, { questions });
}

async function handlePostAnswers(req, res) {
  if (!checkBearer(req)) return sendError(res, 401, "unauthorized", "Missing or invalid Bearer token.");
  const body = await readJson(req, res);
  if (body === null) return;
  // ---- field validation (400) ----
  if (body.questionId === undefined) return sendError(res, 400, "missing_field", "questionId is required.");
  if (typeof body.questionId !== "string") return sendError(res, 400, "invalid_field", "questionId must be a string.");
  if (body.agentId === undefined) return sendError(res, 400, "missing_field", "agentId is required.");
  if (!isInt(body.agentId) || body.agentId < 1) return sendError(res, 400, "invalid_field", "agentId must be a positive integer.");
  if (body.answer === undefined) return sendError(res, 400, "missing_field", "answer is required.");
  if (typeof body.answer !== "string" || !body.answer.trim() || body.answer.trim().length > 4000) {
    return sendError(res, 400, "answer_too_long", "answer must be 1-4000 characters.");
  }
  const memCheck = validateMemory(body.memory);
  if (!memCheck.ok) return sendError(res, 400, "invalid_memory", "memory entries are invalid.");
  const imgCheck = validateImages(body.images);
  if (!imgCheck.ok) return sendError(res, 400, imgCheck.code, imgCheck.message);
  const answer = body.answer.trim();
  // ---- question lookup (404) + lazy timeout ----
  let q;
  try {
    const r = await pool.query(
      "SELECT question_id, agent_id, name, status, created_at FROM agent_questions WHERE question_id = $1",
      [body.questionId],
    );
    q = r.rows[0] || null;
  } catch (e) {
    console.error("answer question lookup error:", e.message);
    return sendError(res, 500, "internal_error", "Internal error.");
  }
  if (!q) return sendError(res, 404, "question_not_found", "Question does not exist.");
  if (q.status === "answered") return sendJson(res, 200, { ok: true, duplicate: true });
  if (q.status === "timeout" || isTimedOut(q.created_at)) {
    if (q.status === "queued") {
      await pool.query("UPDATE agent_questions SET status = 'timeout' WHERE question_id = $1", [body.questionId]).catch(() => {});
    }
    return sendError(res, 404, "question_not_found", "Question does not exist or has timed out.");
  }
  // ---- anti-misrouting: agentId must match the question (400) ----
  if (num(q.agent_id) !== body.agentId) {
    return sendError(res, 400, "agent_mismatch", "agentId does not match the question.");
  }
  // ---- images: decode + save file first; DB row goes in the txn ----
  let imageRow = null;
  let imagePath = null;
  if (imgCheck.list.length) {
    const im = imgCheck.list[0];
    const imageId = newImageId();
    const ext = im.mime === "image/png" ? ".png" : ".jpg";
    imagePath = path.join(IMAGE_DIR, imageId + ext);
    const buf = Buffer.from(im.data, "base64");
    try {
      fs.mkdirSync(IMAGE_DIR, { recursive: true });
      fs.writeFileSync(imagePath, buf);
    } catch (e) {
      console.error("image save error:", e.message);
      return sendError(res, 500, "internal_error", "Internal error.");
    }
    imageRow = { imageId, questionId: body.questionId, agentId: body.agentId, mime: im.mime, path: imagePath };
  }
  // ---- persist (transaction) ----
  const now = new Date();
  const client = await pool.connect();
  try {
    await client.query("BEGIN");
    const upd = await client.query(
      `UPDATE agent_questions SET status = 'answered', answer = $1, answered_at = $2
        WHERE question_id = $3 AND status = 'queued'`,
      [answer, now, body.questionId],
    );
    if (upd.rowCount === 0) {
      // Lost a race: another writer answered it first.
      await client.query("ROLLBACK");
      return sendJson(res, 200, { ok: true, duplicate: true });
    }
    await client.query(
      `INSERT INTO agent_chat_history (agent_id, question_id, role, text, created_at)
       VALUES ($1, $2, 'agent', $3, $4)`,
      [body.agentId, body.questionId, answer, now],
    );
    if (imageRow) {
      await client.query(
        `INSERT INTO agent_images (image_id, question_id, agent_id, mime, path, created_at)
         VALUES ($1, $2, $3, $4, $5, $6)`,
        [imageRow.imageId, imageRow.questionId, imageRow.agentId, imageRow.mime, imageRow.path, now],
      );
    }
    await client.query("COMMIT");
  } catch (e) {
    await client.query("ROLLBACK").catch(() => {});
    if (imagePath) {
      try {
        fs.unlinkSync(imagePath);
      } catch {}
    }
    console.error("post answers txn error:", e.message);
    return sendError(res, 500, "internal_error", "Internal error.");
  } finally {
    client.release();
  }
  // Memory updates are applied after the answer is durably stored.
  try {
    await applyMemoryUpdates(body.agentId, memCheck.list);
  } catch (e) {
    console.error("applyMemoryUpdates error:", e.message);
  }
  sendJson(res, 200, { ok: true });
}

async function imageUrlsForQuestion(questionId) {
  const r = await pool.query("SELECT image_id FROM agent_images WHERE question_id = $1 ORDER BY created_at ASC", [questionId]);
  return r.rows.map((row) => ({ url: imageUrl(row.image_id) }));
}
async function handleGetQuestion(req, res, questionId) {
  let q;
  try {
    const r = await pool.query(
      "SELECT question_id, status, answer, created_at FROM agent_questions WHERE question_id = $1",
      [questionId],
    );
    q = r.rows[0] || null;
  } catch (e) {
    console.error("get question error:", e.message);
    return sendError(res, 500, "internal_error", "Internal error.");
  }
  if (!q) return sendError(res, 404, "question_not_found", "Question does not exist.");
  let status = q.status;
  if (status === "queued" && isTimedOut(q.created_at)) {
    await pool.query("UPDATE agent_questions SET status = 'timeout' WHERE question_id = $1", [questionId]).catch(() => {});
    status = "timeout";
  }
  const out = { questionId: q.question_id, status };
  if (status === "answered") {
    out.answer = q.answer;
    try {
      const imgs = await imageUrlsForQuestion(questionId);
      if (imgs.length) out.images = imgs;
    } catch (e) {
      console.error("get question images error:", e.message);
    }
  }
  sendJson(res, 200, out);
}

async function handleHistory(req, res, agentIdRaw, query) {
  const agentId = Number(agentIdRaw);
  if (!Number.isInteger(agentId) || agentId < 1) return sendError(res, 404, "agent_not_found", "Agent does not exist.");
  const aiId = query.get("aiId");
  if (aiId === null) return sendError(res, 400, "missing_field", "aiId is required.");
  let agent;
  try {
    agent = await getAgent(agentId);
  } catch (e) {
    console.error("history getAgent error:", e.message);
    return sendError(res, 500, "internal_error", "Internal error.");
  }
  if (!agent || !agent.active) return sendError(res, 404, "agent_not_found", "Agent does not exist or is not active.");
  let ok;
  try {
    ok = await verifyOwner(aiId, agent.fullName);
  } catch (e) {
    console.error("history verifyOwner error:", e.message);
    return sendError(res, 500, "internal_error", "Internal error.");
  }
  if (!ok) return sendError(res, 403, "not_owner", "aiId does not belong to the owner of this agent.");
  let limit = parseInt(query.get("limit") || "50", 10);
  if (!Number.isInteger(limit) || limit < 1) limit = 50;
  if (limit > 50) limit = 50;
  let rows;
  try {
    const r = await pool.query(
      `SELECT question_id, role, text, created_at FROM agent_chat_history
        WHERE agent_id = $1 AND created_at >= NOW() - INTERVAL '30 days'
        ORDER BY created_at DESC LIMIT $2`,
      [agentId, limit],
    );
    rows = r.rows.reverse();
  } catch (e) {
    console.error("history query error:", e.message);
    return sendError(res, 500, "internal_error", "Internal error.");
  }
  // Attach images to agent messages (looked up by question_id).
  let imgMap = new Map();
  try {
    const qids = [...new Set(rows.filter((m) => m.role === "agent").map((m) => m.question_id))];
    if (qids.length) {
      const ir = await pool.query("SELECT question_id, image_id FROM agent_images WHERE question_id = ANY($1)", [qids]);
      for (const row of ir.rows) {
        if (!imgMap.has(row.question_id)) imgMap.set(row.question_id, []);
        imgMap.get(row.question_id).push({ url: imageUrl(row.image_id) });
      }
    }
  } catch (e) {
    console.error("history images error:", e.message);
  }
  const messages = rows.map((m) => {
    const out = { role: m.role, text: m.text, at: isoNow(new Date(m.created_at)) };
    const imgs = imgMap.get(m.question_id);
    if (m.role === "agent" && imgs && imgs.length) out.images = imgs;
    return out;
  });
  sendJson(res, 200, { messages });
}

async function handleImage(req, res, imageId) {
  if (!checkImageLimit(clientIp(req))) {
    return sendJson(res, 429, { error: "rate_limited", message: "Too many image requests.", retry_after_seconds: 60 });
  }
  let row;
  try {
    const r = await pool.query("SELECT image_id, mime, path, created_at FROM agent_images WHERE image_id = $1", [imageId]);
    row = r.rows[0] || null;
  } catch (e) {
    console.error("image lookup error:", e.message);
    return sendError(res, 500, "internal_error", "Internal error.");
  }
  if (!row) return sendError(res, 404, "image_not_found", "Image not found.");
  // Enforce the 3-day retention even if the daily cleanup has not run yet.
  if (Date.now() - new Date(row.created_at).getTime() > 3 * 24 * 60 * 60 * 1000) {
    return sendError(res, 404, "image_not_found", "Image not found.");
  }
  let buf;
  try {
    buf = fs.readFileSync(row.path);
  } catch (e) {
    console.error("image read failed:", row.path, e.message);
    return sendError(res, 404, "image_not_found", "Image not found.");
  }
  res.writeHead(200, {
    "Content-Type": row.mime,
    "Cache-Control": "public, max-age=259200",
    "Content-Length": buf.length,
  });
  // HEAD returns the same headers as GET but no body.
  res.end(req.method === "HEAD" ? undefined : buf);
}

// ---------------------------------------------------------------- routing
async function route(req, res) {
  const started = Date.now();
  let pathname;
  let query;
  try {
    const u = new URL(req.url, "http://127.0.0.1");
    pathname = u.pathname;
    query = u.searchParams;
  } catch {
    sendError(res, 400, "invalid_field", "Bad URL.");
    return;
  }
  // Accept both bare paths and the /agent-chat prefix (nginx may or may
  // not strip it, depending on the proxy_pass form).
  if (pathname === "/agent-chat" || pathname.startsWith("/agent-chat/")) {
    pathname = pathname.slice("/agent-chat".length) || "/";
  }
  try {
    if ((req.method === "GET" || req.method === "HEAD") && pathname === "/health") {
      if (req.method === "HEAD") {
        try {
          await pool.query("SELECT 1");
          res.writeHead(200, { "Content-Type": "application/json" });
          res.end();
        } catch {
          res.writeHead(503, { "Content-Type": "application/json" });
          res.end(JSON.stringify({ ok: false }));
        }
      } else {
        await handleHealth(req, res);
      }
    } else if (req.method === "POST" && pathname === "/questions") {
      await handlePostQuestions(req, res);
    } else if (req.method === "GET" && pathname === "/questions/pending") {
      await handlePending(req, res);
    } else if (req.method === "POST" && pathname === "/answers") {
      await handlePostAnswers(req, res);
    } else if (req.method === "GET" && pathname.startsWith("/questions/")) {
      const id = decodeURIComponent(pathname.slice("/questions/".length));
      if (!id || id.includes("/")) sendError(res, 404, "question_not_found", "Question does not exist.");
      else await handleGetQuestion(req, res, id);
    } else if (req.method === "GET" && pathname.startsWith("/history/")) {
      const id = decodeURIComponent(pathname.slice("/history/".length));
      if (!id || id.includes("/")) sendError(res, 404, "agent_not_found", "Agent does not exist.");
      else await handleHistory(req, res, id, query);
    } else if ((req.method === "GET" || req.method === "HEAD") && pathname.startsWith("/images/")) {
      const id = decodeURIComponent(pathname.slice("/images/".length));
      if (!id || id.includes("/")) sendError(res, 404, "image_not_found", "Image not found.");
      else await handleImage(req, res, id);
    } else {
      sendError(res, 404, "question_not_found", "Not found.");
    }
  } catch (e) {
    console.error("handler error:", e);
    if (!res.headersSent) sendError(res, 500, "internal_error", "Internal error.");
  } finally {
    log(req, res.statusCode || 0, Date.now() - started);
  }
}

const server = http.createServer((req, res) => {
  route(req, res).catch((e) => {
    console.error("route error:", e);
    if (!res.headersSent) sendError(res, 500, "internal_error", "Internal error.");
  });
});

server.listen(PORT, HOST, async () => {
  console.log(`haha-agent-chat listening on ${HOST}:${PORT}`);
  try {
    await pool.query("SELECT 1");
    console.log("postgres connected");
  } catch (e) {
    console.error("postgres connect failed:", e.message);
  }
  try {
    fs.mkdirSync(IMAGE_DIR, { recursive: true });
  } catch (e) {
    console.error("image dir create failed:", e.message);
  }
  try {
    await loadHandleCache();
    console.log(`handle cache loaded (${handleCache.size} aiId -> address)`);
  } catch (e) {
    console.error("handle cache load failed:", e.message);
  }
  setInterval(() => {
    loadHandleCache().catch((e) => console.error("handle cache refresh failed:", e.message));
  }, HANDLE_CACHE_TTL_MS);
  scheduleDailyCleanup();
  setInterval(sweepTimeouts, 10000);
  sweepTimeouts();
});
