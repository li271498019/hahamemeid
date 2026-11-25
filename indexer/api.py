"""haha.meme V1 indexer — HTTP API.

Binds 127.0.0.1:8787 only. nginx strips /api/ before proxying, so routes
here have NO /api prefix: /health, /v1/listings, /v1/trades, /v1/agents,
/v1/leaderboard/reputation, /v1/names/{fullName},
/v1/names/{fullName}/generations, /v1/owners/{address}/names,
/v1/leaderboard/points, /v1/stats, /v1/owners/{address}/primary,
/v1/names/{fullName}/image.svg, /v1/names/{fullName}/metadata,
/v1/names, /v1/events, /v1/agents/{agentId}/validations,
/v1/validations/{requestHash}.

Conventions (per V1-INDEXER-SPEC.md): uint256 as decimal strings,
addresses lowercase 0x, times UTC ISO-8601 with Z, opaque cursors
(sort keys + primary key), limit default 24 / max 50, empty list = 200,
lists Cache-Control: public, max-age=5, stale-while-revalidate=30,
health Cache-Control: no-store. Derived tables only ever hold blocks
<= safe_block, so the API never reads unconfirmed data.

Usage: python3 api.py [--env /etc/haha/indexer.env] [--port 8787]
"""

import argparse
import base64
import datetime
import json
import os
import re
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

import psycopg2
import psycopg2.extras

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (CHAIN_ID, CONTRACTS, EVENTS, decode_log,
                    get_config, RpcClient, keccak256, season1_module,
                    topic0)
from svg import build_svg_only

LIST_CACHE = "public, max-age=5, stale-while-revalidate=30"
NAME_RE = re.compile(r"^[a-z0-9]{1,32}\.(haha|meme)$")

_local = threading.local()
_rpc = None
_cfg = None


def db():
    conn = getattr(_local, "conn", None)
    if conn is None or conn.closed:
        conn = psycopg2.connect(_cfg["database_url"])
        conn.autocommit = True
        # M3: bound every query the API can issue; a runaway query fails
        # after 5s instead of stacking threads/connections.
        with conn.cursor() as cur:
            cur.execute("SET statement_timeout = '5s'")
        _local.conn = conn
    return conn


def iso(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def hexb(b):
    return "0x" + bytes(b).hex() if b is not None else None


def dec(v):
    return str(v) if v is not None else None


def tld_str(tld):
    return "haha" if tld == 0 else "meme"


class ApiError(Exception):
    def __init__(self, status, body):
        super().__init__(body.get("error", ""))
        self.status = status
        self.body = body


def encode_cursor(values):
    raw = json.dumps(values, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


_NUMSTR_RE = re.compile(r"^-?\d+(\.\d+)?$")
_HEX_RE = re.compile(r"^0x([0-9a-fA-F]{2})+$")


def _check_cursor_value(v, kind):
    if kind == "int":
        return isinstance(v, int) and not isinstance(v, bool)
    if kind == "numstr":
        return isinstance(v, str) and _NUMSTR_RE.fullmatch(v) is not None
    if kind == "hex":
        return isinstance(v, str) and _HEX_RE.fullmatch(v) is not None
    return False


def decode_cursor(s, expect):
    """Decode a pagination cursor. expect is a tuple of kinds, one per
    element: "int" (JSON integer), "numstr" (decimal string) or "hex"
    ("0x" + even hex digits). A malformed cursor is a 400, never a 500."""
    try:
        padded = s + "=" * (-len(s) % 4)
        vals = json.loads(base64.urlsafe_b64decode(padded).decode())
        if not isinstance(vals, list) or len(vals) != len(expect):
            raise ValueError
        if not all(_check_cursor_value(v, k) for v, k in zip(vals, expect)):
            raise ValueError
        return vals
    except ApiError:
        raise
    except Exception:
        raise ApiError(400, {"error": "invalid_cursor"})


def parse_limit(q):
    raw = q.get("limit", [None])[0]
    if raw is None:
        return 24
    try:
        n = int(raw)
    except ValueError:
        raise ApiError(400, {"error": "invalid_limit"})
    if n < 1 or n > 50:
        raise ApiError(400, {"error": "invalid_limit"})
    return n


def parse_limit_bounded(q, default, maximum):
    """M3: ?limit with a caller-chosen default/cap (season endpoints:
    default 50, max 100)."""
    raw = q.get("limit", [None])[0]
    if raw is None:
        return default
    try:
        n = int(raw)
    except ValueError:
        raise ApiError(400, {"error": "invalid_limit"})
    if n < 1 or n > maximum:
        raise ApiError(400, {"error": "invalid_limit"})
    return n


def parse_sort(q, allowed, default):
    s = q.get("sort", [default])[0]
    if s not in allowed:
        raise ApiError(400, {"error": "invalid_sort"})
    return s


def page(rows, limit, make_cursor):
    """rows: fetched limit+1 rows. Returns (items, nextCursor)."""
    has_more = len(rows) > limit
    rows = rows[:limit]
    nxt = encode_cursor(make_cursor(rows[-1])) if has_more and rows else None
    return rows, nxt


# ---------------------------------------------------------------- handlers

def h_health():
    try:
        conn = db()
        with conn.cursor() as cur:
            cur.execute("SELECT safe_block FROM checkpoint WHERE id = 1")
            row = cur.fetchone()
        safe = row[0] if row else None
    except Exception as e:
        # L6: never echo the raw exception (it leaks the internal DB
        # address/port); the detail goes to the server log only.
        sys.stderr.write("[health] db error: %r\n" % e)
        return {"ok": False, "chainId": CHAIN_ID, "safeBlock": None,
                "headBlock": None, "lagBlocks": None,
                "lastError": "db_unavailable"}
    head = None
    last_error = None
    try:
        # short-lived cache: health is polled every minute, head moves ~3s
        now = datetime.datetime.now(datetime.timezone.utc).timestamp()
        if getattr(h_health, "_head_ts", 0) and now - h_health._head_ts < 5:
            head = h_health._head
        else:
            head = _rpc.block_number()
            h_health._head = head
            h_health._head_ts = now
    except Exception as e:
        # L6: fixed string only; the raw error goes to the server log.
        sys.stderr.write("[health] rpc error: %r\n" % e)
        last_error = "rpc_unavailable"
        head = getattr(h_health, "_head", None)
    lag = (head - safe) if (head is not None and safe is not None) else None
    ok = safe is not None and lag is not None and lag <= 40
    return {"ok": ok, "chainId": CHAIN_ID, "safeBlock": safe,
            "headBlock": head, "lagBlocks": lag, "lastError": last_error}


def h_listings(q):
    limit = parse_limit(q)
    sort = parse_sort(q, ("listed_desc", "price_asc", "price_desc"), "listed_desc")
    tld = q.get("tld", [None])[0]
    label = q.get("q", [None])[0]
    cursor = q.get("cursor", [None])[0]
    where = []
    args = []
    if tld is not None:
        if tld not in ("haha", "meme"):
            raise ApiError(400, {"error": "invalid_tld"})
        where.append("n.tld = %s")
        args.append(0 if tld == "haha" else 1)
    if label is not None:
        label = label.strip().lower()
        if not re.fullmatch(r"[a-z0-9]{1,32}", label):
            raise ApiError(400, {"error": "invalid_name"})
        where.append("n.label = %s")
        args.append(label)
    if sort == "listed_desc":
        order = "l.listed_block DESC, l.token_id DESC"
        if cursor:
            cb, ct = decode_cursor(cursor, ("int", "numstr"))
            where.append("(l.listed_block < %s OR (l.listed_block = %s AND l.token_id < %s))")
            args += [cb, cb, ct]
        mk = lambda r: [r["listed_block"], dec(r["token_id"])]
    elif sort == "price_asc":
        order = "l.price_wei ASC, l.token_id ASC"
        if cursor:
            cp, ct = decode_cursor(cursor, ("numstr", "numstr"))
            where.append("(l.price_wei > %s OR (l.price_wei = %s AND l.token_id > %s))")
            args += [cp, cp, ct]
        mk = lambda r: [dec(r["price_wei"]), dec(r["token_id"])]
    else:  # price_desc
        order = "l.price_wei DESC, l.token_id ASC"
        if cursor:
            cp, ct = decode_cursor(cursor, ("numstr", "numstr"))
            where.append("(l.price_wei < %s OR (l.price_wei = %s AND l.token_id > %s))")
            args += [cp, cp, ct]
        mk = lambda r: [dec(r["price_wei"]), dec(r["token_id"])]
    sql = ("SELECT l.token_id, n.label, n.tld, n.full_name, n.owner, l.seller,"
           " l.price_wei, l.listed_time, l.listed_block, l.tx_hash, l.log_index"
           " FROM listings l JOIN names n ON n.token_id = l.token_id"
           + (" WHERE " + " AND ".join(where) if where else "")
           + " ORDER BY " + order + " LIMIT %s")
    args.append(limit + 1)
    with db().cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, args)
        rows = cur.fetchall()
    items, nxt = page(rows, limit, mk)
    return {"items": [{
        "tokenId": dec(r["token_id"]), "label": r["label"],
        "tld": tld_str(r["tld"]), "fullName": r["full_name"],
        "owner": hexb(r["owner"]), "seller": hexb(r["seller"]), "priceWei": dec(r["price_wei"]),
        "listedAt": iso(r["listed_time"]), "blockNumber": r["listed_block"],
        "txHash": hexb(r["tx_hash"]), "logIndex": r["log_index"],
    } for r in items], "nextCursor": nxt}


def h_trades(q):
    limit = parse_limit(q)
    sort = parse_sort(q, ("time_desc", "price_desc"), "time_desc")
    full = q.get("fullName", [None])[0]
    cursor = q.get("cursor", [None])[0]
    where, args = [], []
    if full is not None:
        if not NAME_RE.fullmatch(full.strip().lower()):
            raise ApiError(400, {"error": "invalid_name"})
        where.append("n.full_name = %s")
        args.append(full.strip().lower())
    if sort == "time_desc":
        order = "t.block_number DESC, t.tx_hash DESC, t.log_index DESC"
        if cursor:
            cb, cth, cl = decode_cursor(cursor, ("int", "hex", "int"))
            where.append("(t.block_number < %s OR (t.block_number = %s AND"
                         " (t.tx_hash < %s OR (t.tx_hash = %s AND t.log_index < %s))))")
            args += [cb, cb, h2b(cth), h2b(cth), cl]
        mk = lambda r: [r["block_number"], hexb(r["tx_hash"]), r["log_index"]]
    else:
        order = ("t.price_wei DESC, t.block_number DESC,"
                 " t.tx_hash DESC, t.log_index DESC")
        if cursor:
            cp, cb, cth, cl = decode_cursor(cursor, ("numstr", "int", "hex", "int"))
            where.append("(t.price_wei < %s OR (t.price_wei = %s AND"
                         " (t.block_number < %s OR (t.block_number = %s AND"
                         " (t.tx_hash < %s OR (t.tx_hash = %s AND t.log_index < %s))))))")
            args += [cp, cp, cb, cb, h2b(cth), h2b(cth), cl]
        mk = lambda r: [dec(r["price_wei"]), r["block_number"],
                        hexb(r["tx_hash"]), r["log_index"]]
    sql = ("SELECT t.token_id, n.label, n.tld, n.full_name, t.seller, t.buyer,"
           " t.price_wei, t.fee_wei, t.proceeds_wei, t.block_time,"
           " t.block_number, t.tx_hash, t.log_index"
           " FROM trades t JOIN names n ON n.token_id = t.token_id"
           + (" WHERE " + " AND ".join(where) if where else "")
           + " ORDER BY " + order + " LIMIT %s")
    args.append(limit + 1)
    with db().cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, args)
        rows = cur.fetchall()
    items, nxt = page(rows, limit, mk)
    return {"items": [{
        "tokenId": dec(r["token_id"]), "label": r["label"],
        "tld": tld_str(r["tld"]), "fullName": r["full_name"],
        "seller": hexb(r["seller"]), "buyer": hexb(r["buyer"]),
        "priceWei": dec(r["price_wei"]), "feeWei": dec(r["fee_wei"]),
        "proceedsWei": dec(r["proceeds_wei"]), "tradedAt": iso(r["block_time"]),
        "blockNumber": r["block_number"], "txHash": hexb(r["tx_hash"]),
        "logIndex": r["log_index"],
    } for r in items], "nextCursor": nxt}


def h_names(q):
    """All minted names, newest first. tld is the int 0=haha / 1=meme
    (unlike _name_row, which renders it as a string)."""
    limit = parse_limit(q)
    cursor = q.get("cursor", [None])[0]
    where, args = [], []
    if cursor:
        cb, ct = decode_cursor(cursor, ("int", "numstr"))
        where.append("(n.mint_block < %s OR (n.mint_block = %s"
                     " AND n.token_id < %s))")
        args += [cb, cb, ct]
    sql = ("SELECT n.token_id, n.label, n.tld, n.full_name, n.owner,"
           " n.mint_time, n.mint_block FROM names n"
           + (" WHERE " + " AND ".join(where) if where else "")
           + " ORDER BY n.mint_block DESC, n.token_id DESC LIMIT %s")
    args.append(limit + 1)
    with db().cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, args)
        rows = cur.fetchall()
    items, nxt = page(rows, limit,
                      lambda r: [r["mint_block"], dec(r["token_id"])])
    return {"names": [{
        "fullName": r["full_name"], "label": r["label"],
        "tld": int(r["tld"]), "tokenId": dec(r["token_id"]),
        "owner": hexb(r["owner"]), "mintedAt": iso(r["mint_time"]),
        "blockNumber": r["mint_block"],
    } for r in items], "nextCursor": nxt}


def h_events(q):
    """All indexed chain events, newest first, decoded via common.decode_log.

    Filters: contract= (contract key, e.g. registrar, or a 0x address),
    event= (event name, e.g. NameMinted), address= (a related address:
    the log's own contract, or any topic carrying it). Undecodable logs
    (e.g. season1 module events, which have no defs in common.EVENTS)
    are still returned with event=null and args={}.
    """
    limit = parse_limit(q)
    cursor = q.get("cursor", [None])[0]
    contract = q.get("contract", [None])[0]
    event = q.get("event", [None])[0]
    address = q.get("address", [None])[0]
    where, args = [], []
    if contract is not None:
        c = contract.strip().lower()
        if ADDR_RE.fullmatch(c):
            addr_bytes = bytes.fromhex(c[2:])
        elif c in CONTRACTS:
            addr_bytes = bytes.fromhex(CONTRACTS[c][2:])
        elif c == "season1":
            mod = season1_module()
            if mod is None:
                raise ApiError(400, {"error": "invalid_contract"})
            addr_bytes = bytes.fromhex(mod[2:])
        else:
            raise ApiError(400, {"error": "invalid_contract"})
        where.append("r.address = %s")
        args.append(addr_bytes)
    if event is not None:
        ev = event.strip()
        t0s = sorted({t0 for (addr, t0), (name, params) in EVENTS.items()
                      if name == ev})
        if not t0s:
            raise ApiError(400, {"error": "invalid_event"})
        where.append("r.topic0 = ANY(%s)")
        args.append([bytes.fromhex(t[2:]) for t in t0s])
    if address is not None:
        a = address.strip().lower()
        if not ADDR_RE.fullmatch(a):
            raise ApiError(400, {"error": "invalid_address"})
        # M3: match the 32-byte left-padded address topic via the
        # raw_logs_topics_gin GIN index. The old
        # `topics::text ILIKE '%hex%'` was a leading-wildcard full scan
        # (and never used an index); @> on JSONB does.
        topic = "0x" + "00" * 12 + a[2:]
        where.append("(r.address = %s OR r.topics @> %s::jsonb)")
        args.append(bytes.fromhex(a[2:]))
        args.append(json.dumps([topic]))
    if cursor:
        cb, ct, cl = decode_cursor(cursor, ("int", "int", "int"))
        where.append("(r.block_number < %s OR (r.block_number = %s AND"
                     " (r.tx_index < %s OR (r.tx_index = %s"
                     " AND r.log_index < %s))))")
        args += [cb, cb, ct, ct, cl]
    sql = ("SELECT r.block_number, r.block_hash, r.block_time, r.tx_hash,"
           " r.tx_index, r.log_index, r.address, r.topics, r.data"
           " FROM raw_logs r"
           + (" WHERE " + " AND ".join(where) if where else "")
           + " ORDER BY r.block_number DESC, r.tx_index DESC,"
           " r.log_index DESC LIMIT %s")
    args.append(limit + 1)
    with db().cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, args)
        rows = cur.fetchall()
    items, nxt = page(rows, limit,
                      lambda r: [r["block_number"], r["tx_index"],
                                 r["log_index"]])
    out = []
    for r in items:
        topics = r["topics"] or []
        try:
            name, params = decode_log(hexb(r["address"]), topics,
                                      bytes(r["data"]))
        except Exception:
            name, params = None, {}
        # I3: uint256 values (tokenId etc.) are up to 77 digits, past the
        # JS safe-integer limit. Emit every integer arg as a decimal
        # string, matching the "uint256 as decimal strings" convention
        # used by the other endpoints. decode_log itself is untouched
        # (the syncer depends on its int return values); only this
        # output layer converts. Booleans are not ints here (bool is a
        # subclass of int, so exclude it explicitly).
        params = {k: (str(v) if isinstance(v, int) and not isinstance(v, bool) else v)
                  for k, v in params.items()}
        out.append({
            "blockNumber": r["block_number"],
            "blockHash": hexb(r["block_hash"]),
            "blockTime": iso(r["block_time"]),
            "txHash": hexb(r["tx_hash"]),
            "txIndex": r["tx_index"],
            "logIndex": r["log_index"],
            "address": hexb(r["address"]),
            "event": name,
            "args": params,
        })
    return {"events": out, "nextCursor": nxt}


def h2b(s):
    return bytes.fromhex(s[2:])


AVG_SQL = ("CASE WHEN a.stars_count = 0 THEN 0::numeric"
           " ELSE a.stars_sum::numeric / a.stars_count END")


def agent_item(r):
    return {
        "agentId": dec(r["agent_id"]), "tokenId": dec(r["name_token_id"]),
        "label": r["label"], "tld": tld_str(r["tld"]),
        "fullName": r["full_name"], "owner": hexb(r["owner"]),
        "operatorAiId": hexb(r["operator_ai_id"]),
        "generation": r["generation"], "agentURI": r["agent_uri"],
        "active": r["active"], "starsSum": int(r["stars_sum"]),
        "starsCount": int(r["stars_count"]),
        "activatedAt": iso(r["activated_time"]),
        "blockNumber": r["activated_block"],
    }


def h_agents(q):
    limit = parse_limit(q)
    sort = parse_sort(q, ("activated_desc", "stars_desc", "reviews_desc"),
                      "activated_desc")
    cursor = q.get("cursor", [None])[0]
    where, args = ["a.active = true"], []
    if sort == "activated_desc":
        order = "a.activated_block DESC, a.agent_id DESC"
        if cursor:
            cb, ca = decode_cursor(cursor, ("int", "numstr"))
            where.append("(a.activated_block < %s OR (a.activated_block = %s"
                         " AND a.agent_id < %s))")
            args += [cb, cb, ca]
        mk = lambda r: [r["activated_block"], dec(r["agent_id"])]
    elif sort == "stars_desc":
        order = "%s DESC, a.stars_count DESC, a.agent_id ASC" % AVG_SQL
        if cursor:
            cav, cc, ca = decode_cursor(cursor, ("numstr", "int", "numstr"))
            where.append("(%s < %%s OR (%s = %%s AND (a.stars_count < %%s OR"
                         " (a.stars_count = %%s AND a.agent_id > %%s))))"
                         % (AVG_SQL, AVG_SQL))
            args += [cav, cav, cc, cc, ca]
        mk = lambda r: [dec(r["avg"]), int(r["stars_count"]), dec(r["agent_id"])]
    else:  # reviews_desc
        order = "a.stars_count DESC, a.agent_id ASC"
        if cursor:
            cc, ca = decode_cursor(cursor, ("int", "numstr"))
            where.append("(a.stars_count < %s OR (a.stars_count = %s"
                         " AND a.agent_id > %s))")
            args += [cc, cc, ca]
        mk = lambda r: [int(r["stars_count"]), dec(r["agent_id"])]
    sql = ("SELECT a.*, n.label, n.tld, n.full_name, " + AVG_SQL + " AS avg"
           " FROM agents a JOIN names n ON n.token_id = a.name_token_id"
           " WHERE " + " AND ".join(where) +
           " ORDER BY " + order + " LIMIT %s")
    args.append(limit + 1)
    with db().cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, args)
        rows = cur.fetchall()
    items, nxt = page(rows, limit, mk)
    return {"items": [agent_item(r) for r in items], "nextCursor": nxt}


def _stars_before_count(where_sql, args):
    """Rows strictly before the cursor in stars_desc order (for rank)."""
    sql = ("SELECT COUNT(*) FROM agents a WHERE " + where_sql)
    with db().cursor() as cur:
        cur.execute(sql, args)
        return cur.fetchone()[0]


def h_reputation(q):
    limit = parse_limit(q)
    sort = parse_sort(q, ("stars_desc",), "stars_desc")
    cursor = q.get("cursor", [None])[0]
    raw_min = q.get("minReviews", [None])[0]
    try:
        min_reviews = 1 if raw_min is None else int(raw_min)
    except ValueError:
        raise ApiError(400, {"error": "invalid_minReviews"})
    if min_reviews < 1 or min_reviews > 20:
        raise ApiError(400, {"error": "invalid_minReviews"})
    where = ["a.active = true", "a.stars_count >= %s"]
    args = [min_reviews]
    order = "%s DESC, a.stars_count DESC, a.agent_id ASC" % AVG_SQL
    base = 0
    if cursor:
        cav, cc, ca = decode_cursor(cursor, ("numstr", "int", "numstr"))
        where.append("(%s < %%s OR (%s = %%s AND (a.stars_count < %%s OR"
                     " (a.stars_count = %%s AND a.agent_id > %%s))))"
                     % (AVG_SQL, AVG_SQL))
        args += [cav, cav, cc, cc, ca]
        # rank needs rows strictly BEFORE the cursor, not after it.
        before_where = ["a.active = true", "a.stars_count >= %s",
                        "(%s > %%s OR (%s = %%s AND (a.stars_count > %%s OR"
                        " (a.stars_count = %%s AND a.agent_id <= %%s))))"
                        % (AVG_SQL, AVG_SQL)]
        before_args = [min_reviews, cav, cav, cc, cc, ca]
        base = _stars_before_count(" AND ".join(before_where), before_args)
    sql = ("SELECT a.*, n.label, n.tld, n.full_name, " + AVG_SQL + " AS avg"
           " FROM agents a JOIN names n ON n.token_id = a.name_token_id"
           " WHERE " + " AND ".join(where) +
           " ORDER BY " + order + " LIMIT %s")
    args.append(limit + 1)
    with db().cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, args)
        rows = cur.fetchall()
    items, nxt = page(rows, limit,
                      lambda r: [dec(r["avg"]), int(r["stars_count"]),
                                 dec(r["agent_id"])])
    out = []
    for i, r in enumerate(items):
        it = agent_item(r)
        it["rank"] = base + i + 1
        out.append(it)
    return {"items": out, "nextCursor": nxt}


NAME_CACHE = "public, max-age=2, stale-while-revalidate=5"
ADDR_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")

# Resolver contract (primaryName) and NFT image/metadata.
RESOLVER_ADDR = "0x85c2dbdfd81a14b958b360159e8710e6c15370d6"
PRIMARY_NAME_SEL = bytes.fromhex("eba951aa")  # primaryName(address)
# The SVG for a name never changes, so it can be cached longer than the lists.
SVG_CACHE = "public, max-age=3600, stale-while-revalidate=86400"
# Canonical base URL used for the metadata `image` field.
SITE_BASE = "https://haha.meme"


def _listing_of(row):
    if row.get("seller") is None:
        return None
    return {
        "seller": hexb(row["seller"]),
        "priceWei": dec(row["price_wei"]),
        "listedAt": iso(row["listed_time"]),
    }


def _name_row(r):
    return {
        "fullName": r["full_name"],
        "minted": True,
        "tokenId": dec(r["token_id"]),
        "label": r["label"],
        "tld": tld_str(r["tld"]),
        "owner": hexb(r["owner"]),
        "mintedAt": iso(r["mint_time"]),
        "listing": _listing_of(r),
    }


def h_name(full_name):
    """One indexed lookup. Unminted names are 200 with minted=false, not 404,
    so the site can tell 'not in the index' from 'the API is down'."""
    full_name = unquote(full_name).strip().lower()
    if not NAME_RE.fullmatch(full_name):
        raise ApiError(400, {"error": "invalid_name"})
    label, tld = full_name.split(".", 1)
    sql = ("SELECT n.token_id, n.label, n.tld, n.full_name, n.owner, n.mint_time,"
           " l.seller, l.price_wei, l.listed_time"
           " FROM names n LEFT JOIN listings l ON l.token_id = n.token_id"
           " WHERE n.full_name = %s")
    with db().cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, (full_name,))
        row = cur.fetchone()
    if row is None:
        return {
            "fullName": full_name, "minted": False, "tokenId": None,
            "label": label, "tld": tld, "owner": None,
            "mintedAt": None, "listing": None,
        }
    return _name_row(row)


def h_owner_names(address):
    address = unquote(address).strip()
    if not ADDR_RE.fullmatch(address):
        raise ApiError(400, {"error": "invalid_address"})
    raw = bytes.fromhex(address[2:])
    sql = ("SELECT n.token_id, n.label, n.tld, n.full_name, n.owner, n.mint_time,"
           " l.seller, l.price_wei, l.listed_time"
           " FROM names n LEFT JOIN listings l ON l.token_id = n.token_id"
           " WHERE n.owner = %s"
           " ORDER BY n.mint_block DESC, n.token_id DESC"
           " LIMIT 200")
    with db().cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, (raw,))
        rows = cur.fetchall()
    return {"owner": address.lower(), "items": [_name_row(r) for r in rows]}


def _decode_string_return(hexdata):
    """Decode a Solidity `string` return value (same shape as handleOf)."""
    if not hexdata or hexdata == "0x":
        return None
    data = bytes.fromhex(hexdata[2:])
    if len(data) < 64:
        return None
    try:
        pos = int.from_bytes(data[0:32], "big")
        ln = int.from_bytes(data[pos:pos + 32], "big")
        return data[pos + 32:pos + 32 + ln].decode("utf-8", "replace")
    except Exception:
        return None


def _minted_row(full_name):
    """Return the names row for a minted name, else None."""
    sql = ("SELECT token_id, label, tld, full_name, owner, mint_time"
           " FROM names WHERE full_name = %s")
    with db().cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, (full_name,))
        return cur.fetchone()


def h_primary(address):
    """Primary-name reverse lookup: wallet address -> primary name (or null).

    Reads HahaResolver.primaryName on-chain via eth_call, so it is always
    current. An RPC failure is a 502, not a null (null means "no primary
    name set").
    """
    address = unquote(address).strip()
    if not ADDR_RE.fullmatch(address):
        raise ApiError(400, {"error": "invalid_address"})
    data = "0x" + (PRIMARY_NAME_SEL + b"\x00" * 12 + bytes.fromhex(address[2:])).hex()
    try:
        result = _rpc.eth_call(RESOLVER_ADDR, data)
    except Exception:
        raise ApiError(502, {"error": "upstream_unavailable"})
    name = _decode_string_return(result)
    if not name:
        name = None
    return {"owner": address.lower(), "primaryName": name}


def h_name_image(full_name):
    """NFT image: the on-chain SVG for a minted name (image/svg+xml).

    Generated locally by svg.py, a byte-identical port of
    HahaMetadata.buildSvgOnly, so no RPC call is needed.
    """
    full_name = unquote(full_name).strip().lower()
    if not NAME_RE.fullmatch(full_name):
        raise ApiError(400, {"error": "invalid_name"})
    if _minted_row(full_name) is None:
        raise ApiError(404, {"error": "not_found"})
    label, tld = full_name.split(".", 1)
    return build_svg_only(label, tld)


# ---------------------------------------------------------------- EIP-8004 registration file (G4)

REGISTRATION_TYPE = "https://eips.ethereum.org/EIPS/eip-8004#registration-v1"
AGENT_REGISTRY = "eip155:56:0x54A70BF81B288d41013D7b57c2Db0922f1E1a4d4"


def _registration_file(full_name, agent_id, active):
    """Standard EIP-8004 registration file JSON for one agent generation.

    `agent_id` is a JSON number, not a string; `registrations` holds
    exactly one entry with only `agentId` and `agentRegistry`.
    """
    return {
        "type": REGISTRATION_TYPE,
        "name": full_name,
        "description": ("haha id %s 是链上 AI agent 身份，信誉写在链上。"
                        "haha id %s is an on-chain AI agent identity with "
                        "reputation written on-chain." % (full_name, full_name)),
        "image": "%s/api/v1/names/%s/image.svg" % (SITE_BASE, full_name),
        "services": [],
        "x402Support": False,
        "active": active,
        "registrations": [{"agentId": agent_id,
                           "agentRegistry": AGENT_REGISTRY}],
        "supportedTrust": ["reputation"],
    }


def h_agent_registration_by_name(full_name):
    """Registration file for a name's current (active) agent generation.

    No active generation (never activated, or transferred and not
    re-activated) is 404 no_active_agent; an unminted name is 404
    name_not_found. Names are lowercased before lookup.
    """
    full_name = unquote(full_name).strip().lower()
    if not NAME_RE.fullmatch(full_name):
        raise ApiError(404, {"error": "name_not_found"})
    with db().cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT token_id FROM names WHERE full_name = %s",
                    (full_name,))
        row = cur.fetchone()
        if row is None:
            raise ApiError(404, {"error": "name_not_found"})
        cur.execute(
            "SELECT agent_id, active FROM agents"
            " WHERE name_token_id = %s AND active = TRUE",
            (row["token_id"],))
        agent = cur.fetchone()
    if agent is None:
        raise ApiError(404, {"error": "no_active_agent"})
    return _registration_file(full_name, int(agent["agent_id"]),
                              bool(agent["active"]))


def h_agent_registration_by_id(agent_id_raw):
    """Registration file for one agent generation by agentId.

    A non-numeric agentId is 404 agent_not_found, never 500. An
    inactive generation still returns its file with active=false;
    only a missing agentId is 404.
    """
    try:
        agent_id = int(unquote(agent_id_raw).strip())
    except ValueError:
        raise ApiError(404, {"error": "agent_not_found"})
    with db().cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "SELECT a.agent_id, a.active, n.full_name FROM agents a"
            " JOIN names n ON n.token_id = a.name_token_id"
            " WHERE a.agent_id = %s",
            (agent_id,))
        row = cur.fetchone()
    if row is None:
        raise ApiError(404, {"error": "agent_not_found"})
    return _registration_file(row["full_name"], int(row["agent_id"]),
                              bool(row["active"]))


# ---------------------------------------------------------------- G13 Validation Registry

VALIDATION_ADDR = CONTRACTS["validation"]
VALIDATION_ADDR_BYTES = bytes.fromhex(VALIDATION_ADDR[2:])
VALIDATION_TOPIC0S = [
    topic0("ValidationRequest(address,uint256,string,bytes32)"),
    topic0("ValidationResponse(address,uint256,bytes32,uint8,string,bytes32,string)"),
    topic0("ValidationDisputed(bytes32,address)"),
]
# topic0 column is bytea: pass bytes, not hex strings (h_events pattern).
VALIDATION_TOPIC0_BYTES = [bytes.fromhex(t[2:]) for t in VALIDATION_TOPIC0S]


def _decode_validation_row(r):
    """Decode one validation raw_log row. Returns an event dict or None
    when the row does not decode (never raises)."""
    try:
        name, params = decode_log(VALIDATION_ADDR, r["topics"],
                                  bytes(r["data"]))
    except Exception:
        return None
    if name is None:
        return None
    return {
        "event": name,
        "blockNumber": r["block_number"],
        "blockTime": r["block_time"],
        "txHash": r["tx_hash"],
        "txIndex": r["tx_index"],
        "logIndex": r["log_index"],
        "params": params,
    }


def _validation_groups():
    """All validation requests grouped by requestHash, chain order.

    Reads raw_logs and decodes at query time, like h_events (E14): old
    events decode after a restart with no backfill table. Volume is
    tiny (each validation is a manual on-chain tx), so one scan per
    call is cheap; no new table.
    """
    with db().cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "SELECT r.block_number, r.block_time, r.tx_hash, r.tx_index,"
            " r.log_index, r.topics, r.data FROM raw_logs r"
            " WHERE r.address = %s AND r.topic0 = ANY(%s)"
            " ORDER BY r.block_number, r.tx_index, r.log_index",
            (VALIDATION_ADDR_BYTES, VALIDATION_TOPIC0_BYTES))
        rows = cur.fetchall()
    groups = {}
    for r in rows:
        ev = _decode_validation_row(r)
        if ev is None:
            continue
        rh = ev["params"].get("requestHash")
        if rh is None:
            continue
        groups.setdefault(rh, []).append(ev)
    return groups


def _validation_dispute_state(events):
    """Dispute derivation (plan §7.2) from one request's events in chain
    order. Returns (disputeStatus, disputeCount, originalResponse,
    latestResponse). Scores are 0-100 ints, or None when no response
    exists yet. disputeCount is 0 or 1 (the contract allows at most one
    dispute per request)."""
    responses = [e for e in events if e["event"] == "ValidationResponse"]
    disputes = [e for e in events if e["event"] == "ValidationDisputed"]
    latest = responses[-1]["params"]["response"] if responses else None
    if not disputes:
        return "not_disputed", 0, latest, latest
    first_dispute_idx = events.index(disputes[0])
    before = [e for e in events[:first_dispute_idx]
              if e["event"] == "ValidationResponse"]
    original = before[-1]["params"]["response"] if before else None
    after = [e for e in events[first_dispute_idx + 1:]
             if e["event"] == "ValidationResponse"]
    if not after:
        return "disputed", 1, original, latest
    if latest == original:
        return "upheld", 1, original, latest
    return "overturned", 1, original, latest


def _validation_record(request_hash, events):
    """One request's record: request + latest result + dispute state."""
    req = next((e for e in events
                if e["event"] == "ValidationRequest"), None)
    responses = [e for e in events if e["event"] == "ValidationResponse"]
    last = responses[-1] if responses else None
    status, count, original, latest = _validation_dispute_state(events)
    return {
        "requestHash": request_hash,
        "agentId": dec(req["params"]["agentId"]) if req is not None
                   else (dec(responses[0]["params"]["agentId"])
                         if responses else None),
        "validatorAddress": (req["params"]["validatorAddress"]
                             if req is not None else None),
        "requestURI": req["params"]["requestURI"] if req is not None else None,
        "requestedAt": iso(req["blockTime"]) if req is not None else None,
        "requestedBlock": req["blockNumber"] if req is not None else None,
        "requestTxHash": hexb(req["txHash"]) if req is not None else None,
        "response": last["params"]["response"] if last is not None else None,
        "responseURI": (last["params"]["responseURI"]
                        if last is not None else None),
        "responseHash": (last["params"]["responseHash"]
                         if last is not None else None),
        "tag": last["params"]["tag"] if last is not None else None,
        "lastUpdatedAt": iso(last["blockTime"]) if last is not None else None,
        "lastUpdateBlock": (last["blockNumber"]
                            if last is not None else None),
        "lastUpdateTxHash": (hexb(last["txHash"])
                             if last is not None else None),
        "disputeStatus": status,
        "disputeCount": count,
        "originalResponse": original,
        "latestResponse": latest,
    }


def h_agent_validations(agent_id_raw):
    """All validation records for one agent, oldest request first.

    A missing agentId is 200 with an empty list, never 404 (a
    non-numeric agentId is treated as missing, same result).
    """
    raw = unquote(agent_id_raw).strip()
    try:
        agent_id = int(raw)
    except ValueError:
        return {"agentId": raw, "validations": []}
    groups = _validation_groups()
    out = []
    for rh, events in groups.items():
        rec = _validation_record(rh, events)
        if rec["agentId"] is not None and int(rec["agentId"]) == agent_id:
            out.append(rec)
    out.sort(key=lambda r: (r["requestedBlock"] is None,
                            r["requestedBlock"] or 0))
    return {"agentId": str(agent_id), "validations": out}


def h_validation_detail(request_hash_raw):
    """One validation request: request + latest result + dispute state,
    plus the full response and dispute history in chain order.

    An unknown or malformed requestHash is 404 validation_not_found
    (machine-readable, like the G4 registration file 404s).
    """
    rh = unquote(request_hash_raw).strip().lower()
    if not re.fullmatch(r"0x[0-9a-f]{64}", rh):
        raise ApiError(404, {"error": "validation_not_found"})
    groups = _validation_groups()
    events = groups.get(rh)
    if not events:
        raise ApiError(404, {"error": "validation_not_found"})
    rec = _validation_record(rh, events)
    rec["responses"] = [{
        "response": e["params"]["response"],
        "responseURI": e["params"]["responseURI"],
        "responseHash": e["params"]["responseHash"],
        "tag": e["params"]["tag"],
        "validatorAddress": e["params"]["validatorAddress"],
        "respondedAt": iso(e["blockTime"]),
        "blockNumber": e["blockNumber"],
        "txHash": hexb(e["txHash"]),
    } for e in events if e["event"] == "ValidationResponse"]
    rec["disputes"] = [{
        "disputer": e["params"]["disputer"],
        "disputedAt": iso(e["blockTime"]),
        "blockNumber": e["blockNumber"],
        "txHash": hexb(e["txHash"]),
    } for e in events if e["event"] == "ValidationDisputed"]
    return rec


def h_name_metadata(full_name):
    """NFT metadata (tokenURI-style JSON) for a minted name.

    Same shape as HahaMetadata.buildJson (name, description, image,
    attributes with TLD and Length), except `image` is an HTTP URL to the
    /image.svg endpoint instead of a data URI.
    """
    full_name = unquote(full_name).strip().lower()
    if not NAME_RE.fullmatch(full_name):
        raise ApiError(400, {"error": "invalid_name"})
    row = _minted_row(full_name)
    if row is None:
        raise ApiError(404, {"error": "not_found"})
    label, tld = full_name.split(".", 1)
    tld_s = tld_str(row["tld"])
    return {
        "name": full_name,
        "description": "haha.meme agent identity for %s" % full_name,
        "image": "%s/api/v1/names/%s/image.svg" % (SITE_BASE, full_name),
        "attributes": [
            {"trait_type": "TLD", "value": tld_s},
            {"trait_type": "Length", "display_type": "number",
             "value": len(label.encode("utf-8"))},
        ],
    }


def _parse_reviews_limit(q):
    """M3: reviews pagination for /v1/names/{name}/generations.
    Query param reviewsLimit, default 20, max 50."""
    raw = (q.get("reviewsLimit") or [None])[0]
    if raw is None:
        return 20
    try:
        n = int(raw)
    except ValueError:
        raise ApiError(400, {"error": "invalid_reviewsLimit"})
    if n < 1 or n > 50:
        raise ApiError(400, {"error": "invalid_reviewsLimit"})
    return n


def h_generations(full_name, q):
    full_name = unquote(full_name).strip()
    if not NAME_RE.fullmatch(full_name):
        raise ApiError(400, {"error": "invalid_name"})
    full_name = full_name.lower()
    reviews_limit = _parse_reviews_limit(q)
    with db().cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT token_id FROM names WHERE full_name = %s", (full_name,))
        row = cur.fetchone()
        if row is None:
            raise ApiError(404, {"error": "not_found"})
        token_id = row["token_id"]
        cur.execute(
            "SELECT * FROM agents WHERE name_token_id = %s ORDER BY generation DESC",
            (token_id,))
        agents = cur.fetchall()
        # M3: was N+1 (one reviews query per generation, each with a
        # correlated subquery for rater_name). Now one query for all
        # generations: ROW_NUMBER() caps reviews per agent, and the
        # rater's first name comes from a DISTINCT ON join instead of a
        # per-row subquery.
        revs_by_agent = {}
        if agents:
            cur.execute(
                "SELECT s.* FROM ("
                " SELECT r.agent_id, r.rater, r.rater_ai_id, r.stars,"
                " r.review, r.edited, r.block_time, r.tx_hash,"
                " p.handle AS rater_ai_handle, n2.full_name AS rater_name,"
                " ROW_NUMBER() OVER (PARTITION BY r.agent_id"
                " ORDER BY r.block_time DESC, r.block_number DESC,"
                " r.tx_hash DESC, r.log_index DESC) AS rn"
                " FROM reviews r"
                " LEFT JOIN points p ON p.ai_id = r.rater_ai_id"
                " LEFT JOIN (SELECT DISTINCT ON (mint_ai_id) mint_ai_id,"
                " full_name FROM names"
                " ORDER BY mint_ai_id, mint_block ASC, token_id ASC) n2"
                " ON n2.mint_ai_id = r.rater_ai_id"
                " WHERE r.agent_id = ANY(%s)) s"
                " WHERE s.rn <= %s ORDER BY s.agent_id, s.rn",
                ([a["agent_id"] for a in agents], reviews_limit + 1))
            for r in cur.fetchall():
                revs_by_agent.setdefault(r["agent_id"], []).append(r)
        gens = []
        for a in agents:
            revs = revs_by_agent.get(a["agent_id"], [])
            truncated = len(revs) > reviews_limit
            revs = revs[:reviews_limit]
            gens.append({
                "generation": a["generation"],
                "agentId": dec(a["agent_id"]),
                "active": a["active"],
                "owner": hexb(a["owner"]),
                "agentURI": a["agent_uri"],
                "starsSum": int(a["stars_sum"]),
                "starsCount": int(a["stars_count"]),
                "activatedAt": iso(a["activated_time"]),
                "resetAt": iso(a["reset_time"]),
                "reviewsTruncated": truncated,
                "reviews": [{
                    "rater": hexb(r["rater"]),
                    "raterAiId": hexb(r["rater_ai_id"]),
                    "raterAi": (r["rater_ai_handle"] + ".ai"
                                if r["rater_ai_handle"] else None),
                    "raterName": r["rater_name"],
                    "stars": r["stars"], "review": r["review"],
                    "edited": r["edited"], "ratedAt": iso(r["block_time"]),
                    "txHash": hexb(r["tx_hash"]),
                } for r in revs],
            })
    return {"fullName": full_name, "tokenId": dec(token_id),
            "generations": gens}


def h_latest_reviews(q):
    limit = parse_limit(q)
    sql = ("SELECT r.agent_id, r.rater, r.rater_ai_id, r.stars, r.review,"
           " r.edited, r.block_time, r.tx_hash, a.generation, n.full_name,"
           " p.handle AS rater_ai_handle,"
           " (SELECT n2.full_name FROM names n2"
           " WHERE n2.mint_ai_id = r.rater_ai_id"
           " ORDER BY n2.mint_block ASC, n2.token_id ASC LIMIT 1)"
           " AS rater_name FROM reviews r"
           " JOIN agents a ON a.agent_id = r.agent_id"
           " JOIN names n ON n.token_id = a.name_token_id"
           " LEFT JOIN points p ON p.ai_id = r.rater_ai_id"
           " ORDER BY r.block_time DESC, r.block_number DESC,"
           " r.tx_hash DESC, r.log_index DESC LIMIT %s")
    with db().cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, (limit,))
        rows = cur.fetchall()
    items = [{
        "fullName": r["full_name"],
        "agentId": dec(r["agent_id"]),
        "generation": int(r["generation"]),
        "rater": hexb(r["rater"]),
        "raterAiId": hexb(r["rater_ai_id"]),
        "raterAi": (r["rater_ai_handle"] + ".ai"
                    if r["rater_ai_handle"] else None),
        "raterName": r["rater_name"],
        "stars": r["stars"],
        "review": r["review"],
        "edited": r["edited"],
        "ratedAt": iso(r["block_time"]),
        "txHash": hexb(r["tx_hash"]),
    } for r in rows]
    return {"items": items, "nextCursor": None}


def h_points(q):
    limit = parse_limit(q)
    sort = parse_sort(q, ("balance_desc",), "balance_desc")
    cursor = q.get("cursor", [None])[0]
    where = ["p.balance > 0", "p.ai_id <> %s"]
    args = [bytes(32)]
    order = "p.balance DESC, p.ai_id ASC"
    base = 0
    if cursor:
        cb, ca = decode_cursor(cursor, ("numstr", "hex"))
        where.append("(p.balance < %s OR (p.balance = %s AND p.ai_id > %s))")
        args += [cb, cb, h2b(ca)]
        # rank needs rows strictly BEFORE the cursor, not after it.
        before_args = [bytes(32), cb, cb, h2b(ca)]
        with db().cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM points p WHERE p.balance > 0"
                        " AND p.ai_id <> %s"
                        " AND (p.balance > %s OR (p.balance = %s AND p.ai_id <= %s))",
                        before_args)
            base = cur.fetchone()[0]
    sql = ("SELECT p.ai_id, p.handle, p.balance, p.updated_time,"
           " (SELECT n.full_name FROM names n WHERE n.mint_ai_id = p.ai_id"
           " ORDER BY n.mint_block ASC, n.token_id ASC LIMIT 1)"
           " AS first_name FROM points p"
           " WHERE " + " AND ".join(where) +
           " ORDER BY " + order + " LIMIT %s")
    args.append(limit + 1)
    with db().cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, args)
        rows = cur.fetchall()
    items, nxt = page(rows, limit,
                      lambda r: [dec(r["balance"]), hexb(r["ai_id"])])
    out = []
    for i, r in enumerate(items):
        out.append({"rank": base + i + 1, "aiId": hexb(r["ai_id"]),
                    "handle": r["handle"], "name": r["first_name"],
                    "balance": dec(r["balance"]),
                    "updatedAt": iso(r["updated_time"])})
    return {"items": out, "nextCursor": nxt}


# 3-char name pools. Totals are fixed by the label charset; reserved and
# blacklisted counts are fixed because both lists were frozen at deployment
# (HahaNamePolicy constructor). Verified 2026-11-21 against
# docs/contracts/blacklist-v2.hashes.txt and reserved-names.hashes.txt
# (all 269 labels reproduce their on-chain hashes) and spot-checked live
# (isReserved(htx/okx)=true, isBlacklisted(ccp/gov)=true,
# isReserved/isBlacklisted(abc)=false).
# Reserved 3-letter: htx, okx (2). Blacklisted 3-letter: ccp, cpc, fag,
# gov, kkk, pla, xjp (7). No 3-digit name is reserved or blacklisted.
THREE_DIGIT_TOTAL = 1000
THREE_DIGIT_RESERVED = 0
THREE_DIGIT_BLACKLISTED = 0
THREE_LETTER_TOTAL = 26 ** 3  # 17576
THREE_LETTER_RESERVED = 2
THREE_LETTER_BLACKLISTED = 7
LATEST_MINTS_LIMIT = 20


def _ai_param(text):
    if not re.fullmatch(r"0x[0-9a-fA-F]{64}", text or ""):
        raise ApiError(404, {"error": "not_found"})
    return bytes.fromhex(text[2:])


def _day_param(text):
    if not re.fullmatch(r"[0-9]{1,6}", text or ""):
        raise ApiError(404, {"error": "not_found"})
    return int(text)


def h_season_day(day_text):
    from season1_read import day_row
    day = _day_param(day_text)
    with db().cursor() as cur:
        body = day_row(cur, day)
    if body is None:
        raise ApiError(404, {"error": "not_found"})
    return body


def h_season_eligibility(ai_text, q):
    from season1_read import eligibility_row
    day = _day_param((q.get("day") or [None])[0])
    ai = _ai_param(ai_text)
    with db().cursor() as cur:
        body = eligibility_row(cur, ai, day)
    body["aiId"] = "0x" + ai.hex()
    body["dayIndex"] = day
    return body


def h_season_proof(ai_text, q):
    """Merkle proof for one .ai on one day (for applyFor).

    The agent passes proof to HahaSeason1.applyFor along with the
    ApplyAuth. Returns 404 when this .ai has no entry that day.
    """
    from season1_read import proof_row
    day = _day_param((q.get("day") or [None])[0])
    ai = _ai_param(ai_text)
    with db().cursor() as cur:
        body = proof_row(cur, ai, day)
    if body is None:
        raise ApiError(404, {"error": "not_found"})
    return body


def h_season_orders(q):
    from season1_read import orders_for_day
    day = _day_param((q.get("day") or [None])[0])
    limit = parse_limit_bounded(q, 50, 100)
    with db().cursor() as cur:
        orders = orders_for_day(cur, day, limit)
    return {"dayIndex": day, "orders": orders}


def h_season_order(order_text):
    from season1_read import order_by_id
    if not re.fullmatch(r"[0-9]+", order_text or ""):
        raise ApiError(404, {"error": "not_found"})
    with db().cursor() as cur:
        body = order_by_id(cur, int(order_text))
    if body is None:
        raise ApiError(404, {"error": "not_found"})
    return body


def h_season_leaderboard(day_text, q):
    """Per-person season leaderboard for one day.

    Ranked by snapshot balance (the day's official order), same shape
    as /v1/leaderboard/points plus the season application/issuance
    fields. Only real entrants appear (dirty snapshot leaves excluded).
    """
    from season1_read import leaderboard_rows
    day = _day_param(day_text)
    limit = parse_limit_bounded(q, 50, 100)
    with db().cursor() as cur:
        entries = leaderboard_rows(cur, day, limit)
    return {"dayIndex": day, "entries": entries}


def h_season_verify(ai_text, q):
    from season1_read import verify_row
    day = _day_param((q.get("day") or [None])[0])
    ai = _ai_param(ai_text)
    with db().cursor() as cur:
        body = verify_row(cur, ai, day)
    body["aiId"] = "0x" + ai.hex()
    body["dayIndex"] = day
    return body


TASKPACK_DIR = "/opt/haha-season1/day-taskpacks"


def h_season_taskpack(day_text):
    """Daily task pack: the canonical JSON file, served byte-identical.

    Agents fetch this, hash the exact bytes, and compare with the
    on-chain taskPack(dayIndex). Re-serializing would change the hash,
    so the file bytes are returned untouched.
    """
    day = _day_param(day_text)
    path = os.path.join(TASKPACK_DIR, "taskpack-day%d.json" % day)
    try:
        with open(path, "rb") as f:
            return f.read()
    except FileNotFoundError:
        raise ApiError(404, {"error": "not_found"})


# M3: findings-list block-header cache. Block headers are immutable,
# so a fetched header stays valid; cache it in memory for 1h so a
# repeat list call (or several findings sharing one block) costs no
# extra RPC round-trip. Values are the raw eth_getBlockByNumber result
# (or None on failure), exactly as the old per-request dedup did.
_BLOCK_CACHE = {}
_BLOCK_CACHE_TTL = 3600.0


def _cached_block(block):
    ent = _BLOCK_CACHE.get(block)
    now = time.time()
    if ent is not None and now - ent[0] < _BLOCK_CACHE_TTL:
        return ent[1]
    try:
        blk = _rpc.call("eth_getBlockByNumber", [hex(block), False])
    except Exception:
        blk = None
    _BLOCK_CACHE[block] = (now, blk)
    return blk


def h_season_findings_list():
    """All season-1 findings, earliest commit first.

    Same rows as the per-hash endpoint, plus the submitter's .ai
    handle/name, the commit block timestamp, and the commit tx hash.
    The timestamp and tx hash come from the block header via RPC
    (one call per distinct block, cached in memory; findings are few,
    so this stays cheap). An RPC failure leaves both null rather than
    failing the whole list.
    """
    from season1_read import findings_rows
    with db().cursor() as cur:
        findings = findings_rows(cur)
    # One RPC call per distinct block: the block header gives the
    # timestamp, and its transactions array (hashes, in tx-index order)
    # gives the commit tx hash. A failure leaves both null rather than
    # failing the whole list.
    blocks = {}
    for f in findings:
        block = f["commitBlock"]
        if block not in blocks:
            blocks[block] = _cached_block(block)
        blk = blocks[block]
        if blk is None:
            f["commitTime"] = None
            f["commitTx"] = None
            continue
        try:
            f["commitTime"] = int(blk["timestamp"], 16)
        except Exception:
            f["commitTime"] = None
        try:
            txs = blk.get("transactions") or []
            txi = f["txIndex"]
            f["commitTx"] = txs[txi] if (txi is not None and 0 <= txi < len(txs)) else None
        except Exception:
            f["commitTx"] = None
    return {"findings": findings}


# H9: reportId format — letters/digits/dash/underscore only, must start
# with a letter or digit. The old check (non-empty, <=64 chars) let two
# different findings share one reportId and let garbage through.
REPORT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


def h_season_finding_publish(digest_text, body):
    """Publish a finding report (submitter self-service).

    The submitter POSTs {reportId, title, content}. The server verifies
    keccak256(content UTF-8) == the on-chain reportEvidenceHash before
    storing, so only the submitter (who holds the report bytes) can
    publish it. The salt is never sent and never stored. Idempotent:
    re-publishing the same content is a no-op.

    H9: the first publish LOCKS reportId/title. The content is fixed by
    the hash, so reportId/title were the only updatable fields — anyone
    holding the (public, post-publication) content could re-POST it
    with their own reportId/title and overwrite the submitter's. On
    conflict only content/published_at are now updated, and the
    already-stored reportId/title are returned. reportId is also
    format-checked and unique across hashes (a second hash reusing an
    existing reportId gets 409).
    """
    # I2: validate the digest here too, not only in the route regex, so
    # a future caller gets a 400 instead of a 500 from bytes.fromhex.
    if not re.fullmatch(r"0x[0-9a-fA-F]{64}", digest_text or ""):
        raise ApiError(400, {"error": "bad_digest"})
    if not isinstance(body, dict):
        raise ApiError(400, {"error": "bad_body"})
    report_id = body.get("reportId")
    title = body.get("title")
    content = body.get("content")
    if not isinstance(report_id, str) or not REPORT_ID_RE.fullmatch(report_id):
        raise ApiError(400, {"error": "bad_report_id"})
    if not isinstance(title, str) or not title or len(title) > 200:
        raise ApiError(400, {"error": "bad_title"})
    if not isinstance(content, str) or not content or len(content) > 200000:
        raise ApiError(400, {"error": "bad_content"})
    raw = bytes.fromhex(digest_text[2:])
    with db().cursor() as cur:
        cur.execute("SELECT 1 FROM season1_findings"
                    " WHERE report_evidence_hash = %s", (raw,))
        if cur.fetchone() is None:
            raise ApiError(404, {"error": "not_found"})
        if keccak256(content.encode("utf-8")) != raw:
            raise ApiError(400, {"error": "hash_mismatch"})
        # H9: one reportId belongs to one hash. (The row for this hash
        # itself is excluded, so re-publishing under its own id is fine.)
        cur.execute("SELECT report_evidence_hash FROM season1_finding_reports"
                    " WHERE report_id = %s AND report_evidence_hash <> %s",
                    (report_id, raw))
        if cur.fetchone() is not None:
            raise ApiError(409, {"error": "report_id_conflict"})
        cur.execute("SELECT report_id, title FROM season1_finding_reports"
                    " WHERE report_evidence_hash = %s", (raw,))
        existing = cur.fetchone()
        now = int(datetime.datetime.now(datetime.timezone.utc).timestamp())
        if existing is not None and existing[0] and existing[1]:
            # Already published: lock reportId/title, refresh only the
            # (hash-fixed) content and the timestamp, return stored values.
            cur.execute(
                "INSERT INTO season1_finding_reports"
                " (report_evidence_hash, report_id, title, content, published_at)"
                " VALUES (%s, %s, %s, %s, %s)"
                " ON CONFLICT (report_evidence_hash) DO UPDATE"
                " SET content = EXCLUDED.content,"
                " published_at = EXCLUDED.published_at",
                (raw, existing[0], existing[1], content, now))
            return {"reportEvidenceHash": "0x" + raw.hex(),
                    "reportId": existing[0], "title": existing[1],
                    "publishedAt": now}
        cur.execute(
            "INSERT INTO season1_finding_reports"
            " (report_evidence_hash, report_id, title, content, published_at)"
            " VALUES (%s, %s, %s, %s, %s)"
            " ON CONFLICT (report_evidence_hash) DO UPDATE"
            " SET report_id = EXCLUDED.report_id, title = EXCLUDED.title,"
            " content = EXCLUDED.content, published_at = EXCLUDED.published_at",
            (raw, report_id, title, content, now))
    return {"reportEvidenceHash": "0x" + raw.hex(), "reportId": report_id,
            "title": title, "publishedAt": now}


def h_season_finding(digest_text):
    from season1_read import finding_row, hx
    if not re.fullmatch(r"0x[0-9a-fA-F]{64}", digest_text or ""):
        raise ApiError(404, {"error": "not_found"})
    withheld = {item.strip().lower() for item in os.environ.get("SEASON1_WITHHELD", "").split(",") if item.strip()}
    raw = bytes.fromhex(digest_text[2:])
    with db().cursor() as cur:
        body = finding_row(cur, raw, withheld)
    if body is None:
        raise ApiError(404, {"error": "not_found"})
    body["reportEvidenceHash"] = hx(raw)
    if body.get("withheld"):
        return {"reportEvidenceHash": body["reportEvidenceHash"], "withheld": True}
    return body


# M3: h_stats server-side cache. 20s TTL.
_STATS_TTL = 20.0
_STATS_CACHE = {"ts": 0.0, "body": None}


def h_stats():
    """Dashboard aggregates for the stats page. One object, no paging:
    participating .ai, active agents, registered names per TLD, 3-char
    names left per TLD, latest mints, total agent interactions with the
    11 contracts (distinct tx hashes in raw_logs), and the safe block
    the numbers cover."""
    # M3: 11 queries per request with no caching. Stats numbers do not
    # need to be realtime; serve a server-side in-memory copy for 20s.
    global _STATS_CACHE
    now = time.time()
    if (_STATS_CACHE["body"] is not None
            and now - _STATS_CACHE["ts"] < _STATS_TTL):
        return _STATS_CACHE["body"]
    with db().cursor() as cur:
        cur.execute("SELECT COUNT(DISTINCT mint_ai_id) FROM names")
        participants = cur.fetchone()[0]
        cur.execute("SELECT tld, COUNT(*) FROM names GROUP BY tld")
        registered = {0: 0, 1: 0}
        for tld, n in cur.fetchall():
            registered[tld] = int(n)
        cur.execute("SELECT tld, COUNT(*) FROM names"
                    " WHERE label ~ '^[0-9]{3}$' GROUP BY tld")
        digit = {0: 0, 1: 0}
        for tld, n in cur.fetchall():
            digit[tld] = int(n)
        cur.execute("SELECT tld, COUNT(*) FROM names"
                    " WHERE label ~ '^[a-z]{3}$' GROUP BY tld")
        letter = {0: 0, 1: 0}
        for tld, n in cur.fetchall():
            letter[tld] = int(n)
        cur.execute("SELECT COUNT(DISTINCT tx_hash) FROM raw_logs")
        agent_interactions = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM agents WHERE active")
        active_agents = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM agents")
        total_activations = cur.fetchone()[0]
        cur.execute("SELECT safe_block FROM checkpoint WHERE id = 1")
        row = cur.fetchone()
        safe_block = row[0] if row else None
        # market aggregates for the market page stats row
        cur.execute("SELECT COUNT(*), MIN(price_wei) FROM listings")
        listings_count, floor_wei = cur.fetchone()
        cur.execute("SELECT price_wei FROM trades"
                    " ORDER BY block_number DESC, tx_hash DESC, log_index DESC LIMIT 1")
        row = cur.fetchone()
        latest_wei = row[0] if row else None
        cur.execute("SELECT COALESCE(SUM(price_wei), 0) FROM trades"
                    " WHERE block_time >= NOW() - INTERVAL '24 hours'")
        vol24_wei = cur.fetchone()[0]
    with db().cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "SELECT full_name, label, tld, mint_time, mint_block FROM names"
            " ORDER BY mint_block DESC, full_name ASC LIMIT %s",
            (LATEST_MINTS_LIMIT,))
        latest = [{
            "fullName": r["full_name"], "label": r["label"],
            "tld": tld_str(r["tld"]), "mintedAt": iso(r["mint_time"]),
            "blockNumber": r["mint_block"],
        } for r in cur.fetchall()]

    def pool(total, reserved, blacklisted, minted):
        return {"minted": minted,
                "remaining": total - reserved - blacklisted - minted}

    body = {
        "agentInteractions": int(agent_interactions),
        "participants": int(participants),
        "activeAgents": int(active_agents),
        "totalActivations": int(total_activations),
        "registered": {
            "haha": registered[0], "meme": registered[1],
            "total": registered[0] + registered[1],
        },
        "threeDigit": {
            "total": THREE_DIGIT_TOTAL,
            "reserved": THREE_DIGIT_RESERVED,
            "blacklisted": THREE_DIGIT_BLACKLISTED,
            "haha": pool(THREE_DIGIT_TOTAL, THREE_DIGIT_RESERVED,
                         THREE_DIGIT_BLACKLISTED, digit[0]),
            "meme": pool(THREE_DIGIT_TOTAL, THREE_DIGIT_RESERVED,
                         THREE_DIGIT_BLACKLISTED, digit[1]),
        },
        "threeLetter": {
            "total": THREE_LETTER_TOTAL,
            "reserved": THREE_LETTER_RESERVED,
            "blacklisted": THREE_LETTER_BLACKLISTED,
            "haha": pool(THREE_LETTER_TOTAL, THREE_LETTER_RESERVED,
                         THREE_LETTER_BLACKLISTED, letter[0]),
            "meme": pool(THREE_LETTER_TOTAL, THREE_LETTER_RESERVED,
                         THREE_LETTER_BLACKLISTED, letter[1]),
        },
        "latest": latest,
        "market": {
            "listings": int(listings_count),
            "floorPriceWei": dec(floor_wei) if floor_wei is not None else None,
            "latestTradePriceWei": dec(latest_wei) if latest_wei is not None else None,
            "volume24hWei": dec(vol24_wei),
        },
        "safeBlock": safe_block,
    }
    _STATS_CACHE = {"ts": now, "body": body}
    return body


# ---------------------------------------------------------------- G13 validation document upload
# POST /v1/validations/upload: an agent owner publishes their own validation
# request document (automated; replaces the manual C deploy to
# /validations/). The server verifies the uploader owns the agent before
# writing anything, fail-closed: the signature over requestHash must
# recover to the on-chain ownerOf(agentId) at upload time. Identity and
# validator addresses are read from the HahaValidation contract on-chain
# (validator() / getIdentityRegistry()), so the endpoint stays correct if
# the validator ever changes, and it works on a test chain when
# VALIDATION_UPLOAD_VALIDATION points at a test deployment. The EIP-712
# domain is the same fixed domain the validator service uses (name
# HahaValidation, version 1, chainId 56, verifyingContract = mainnet
# HahaValidation); a signature the upload accepts is one the validator
# service accepts too.

VALIDATION_UPLOAD_DIR = os.environ.get(
    "VALIDATION_UPLOAD_DIR", "/var/www/validations")
# Public URL base for the published documents. Production default is the
# fixed haha.meme path; tests point it at a local fixture HTTP server so
# the validator service can fetch the uploaded file end to end.
# NOTE: do NOT rstrip("/") here: the test value "ipfs://" would lose
# its slashes and become "ipfs:", producing a one-slash URI the
# validator rejects. Trailing slashes are handled at use time.
VALIDATION_UPLOAD_URL_BASE = os.environ.get(
    "VALIDATION_UPLOAD_URL_BASE", "https://haha.meme/validations")
VALIDATION_UPLOAD_VALIDATION = os.environ.get(
    "VALIDATION_UPLOAD_VALIDATION", CONTRACTS["validation"])
VALIDATION_UPLOAD_EIP712_CHAIN_ID = int(os.environ.get(
    "VALIDATION_UPLOAD_EIP712_CHAIN_ID", "56"))
VALIDATION_UPLOAD_EIP712_CONTRACT = os.environ.get(
    "VALIDATION_UPLOAD_EIP712_CONTRACT", CONTRACTS["validation"])
VALIDATION_UPLOAD_MAX_DOC_BYTES = 64 * 1024
VALIDATION_UPLOAD_MAX_PER_AGENT_PER_DAY = 10
VALIDATION_UPLOAD_TAGS = ("identity-verified", "endpoint-reachable")
# Short tag used in the public URL: the deployed ha.haha document is
# ha.haha-identity-v1.json (short "identity"), not "identity-verified".
VALIDATION_UPLOAD_URL_TAGS = {
    "identity-verified": "identity",
    "endpoint-reachable": "endpoint",
}
_SEL_VALIDATOR = "3a5381b5"               # validator()
_SEL_GET_IDENTITY_REGISTRY = "bc4d861b"   # getIdentityRegistry()
_SEL_OWNER_OF = "6352211e"               # ownerOf(uint256)

# Per-agent daily upload cap (successful uploads only). In-memory, same
# pattern as the findings/sign-verify limits; a restart resets it.
_UPLOAD_RATE_LIMIT = {}
_UPLOAD_RATE_LIMIT_LOCK = threading.Lock()


def _upload_decode_address(hexdata):
    raw = bytes.fromhex(hexdata[2:] if hexdata.startswith("0x") else hexdata)
    if len(raw) < 32:
        raise ValueError("short address return data")
    return "0x" + raw[-20:].hex()


def _upload_chain_validator():
    res = _rpc.eth_call(VALIDATION_UPLOAD_VALIDATION,
                        "0x" + _SEL_VALIDATOR)
    if not res:
        raise RuntimeError("validator() returned empty")
    return _upload_decode_address(res)


def _upload_chain_identity():
    res = _rpc.eth_call(VALIDATION_UPLOAD_VALIDATION,
                        "0x" + _SEL_GET_IDENTITY_REGISTRY)
    if not res:
        raise RuntimeError("getIdentityRegistry() returned empty")
    return _upload_decode_address(res)


def _upload_chain_owner(identity, agent_id):
    data = "0x" + _SEL_OWNER_OF + agent_id.to_bytes(32, "big").hex()
    res = _rpc.eth_call(identity, data)
    if not res:
        raise RuntimeError("ownerOf() returned empty")
    return _upload_decode_address(res)


def _upload_request_hash(validator_address, agent_id, request_uri):
    """Plan §3.4: keccak256(abi.encodePacked(validatorAddress, agentId,
    requestURI))."""
    packed = (bytes.fromhex(validator_address[2:])
              + agent_id.to_bytes(32, "big")
              + request_uri.encode("utf-8"))
    return "0x" + keccak256(packed).hex()


def _upload_recover(req_hash, agent_id, sig_bytes, sig_type, owner):
    """Recover the signer address and compare with the on-chain owner.
    Tries EIP-191 then EIP-712 (reversed when sig_type == 'eip712'),
    mirroring the validator service: an attempt that recovers to a
    non-owner address does NOT stop the loop (an EIP-712 signature
    recovers to a garbage address under EIP-191, and vice versa).
    Returns the matching address, or None when neither attempt matches."""
    try:
        from eth_account import Account
        from eth_account.messages import encode_defunct, encode_typed_data
    except ImportError:
        raise ApiError(500, {"error": "upload_unavailable"})
    if sig_type == "eip712":
        attempts = ("eip712", "eip191")
    else:
        attempts = ("eip191", "eip712")
    for method in attempts:
        try:
            if method == "eip191":
                recovered = Account.recover_message(
                    encode_defunct(primitive=bytes.fromhex(req_hash[2:])),
                    signature=sig_bytes)
            else:
                msg = {
                    "types": {
                        "EIP712Domain": [
                            {"name": "name", "type": "string"},
                            {"name": "version", "type": "string"},
                            {"name": "chainId", "type": "uint256"},
                            {"name": "verifyingContract", "type": "address"},
                        ],
                        "IdentityChallenge": [
                            {"name": "agentId", "type": "uint256"},
                            {"name": "requestHash", "type": "bytes32"},
                        ],
                    },
                    "domain": {
                        "name": "HahaValidation",
                        "version": "1",
                        "chainId": VALIDATION_UPLOAD_EIP712_CHAIN_ID,
                        "verifyingContract": VALIDATION_UPLOAD_EIP712_CONTRACT,
                    },
                    "primaryType": "IdentityChallenge",
                    "message": {
                        "agentId": agent_id,
                        "requestHash": bytes.fromhex(req_hash[2:]),
                    },
                }
                recovered = Account.recover_message(
                    encode_typed_data(full_message=msg), signature=sig_bytes)
        except Exception:
            continue
        if recovered.lower() == owner.lower():
            return recovered
    return None


def _upload_reserve_slot(agent_id):
    """Per-agent daily cap. Check + reserve atomically, called only after
    all validation passed (so a failed upload never consumes a slot)."""
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    with _UPLOAD_RATE_LIMIT_LOCK:
        for k in list(_UPLOAD_RATE_LIMIT):
            if _UPLOAD_RATE_LIMIT[k][0] != today:
                del _UPLOAD_RATE_LIMIT[k]
        day, count = _UPLOAD_RATE_LIMIT.get(agent_id, (today, 0))
        if day != today:
            day, count = today, 0
        if count >= VALIDATION_UPLOAD_MAX_PER_AGENT_PER_DAY:
            raise ApiError(429, {"error": "rate_limited"})
        _UPLOAD_RATE_LIMIT[agent_id] = (day, count + 1)


def h_validations_upload(body):
    """POST /v1/validations/upload. Body: {agentId | fullName, tag,
    version, document, signature}. Returns {url, requestHash, agentId}.
    Fail-closed: any check failing rejects the upload and writes nothing.
    identity-verified is authenticated by the signature inside the
    document; endpoint-reachable by the signature in the request body
    (never stored in the document)."""
    if not isinstance(body, dict):
        raise ApiError(400, {"error": "bad_body"})
    tag = body.get("tag")
    if tag not in VALIDATION_UPLOAD_TAGS:
        raise ApiError(400, {"error": "bad_tag"})
    version = body.get("version", 1)
    if (not isinstance(version, int) or isinstance(version, bool)
            or version < 1 or version > 9999):
        raise ApiError(400, {"error": "bad_version"})
    document = body.get("document")
    if not isinstance(document, dict):
        raise ApiError(400, {"error": "document_invalid"})
    # Resolve agentId + fullName (either input, at least one).
    agent_id = body.get("agentId")
    full_name = body.get("fullName")
    if agent_id is not None:
        if (not isinstance(agent_id, int) or isinstance(agent_id, bool)
                or agent_id < 0):
            raise ApiError(400, {"error": "bad_agent"})
        with db().cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT n.full_name FROM agents a"
                " JOIN names n ON n.token_id = a.name_token_id"
                " WHERE a.agent_id = %s", (agent_id,))
            row = cur.fetchone()
        if row is None:
            raise ApiError(404, {"error": "agent_not_found"})
        full_name = row["full_name"]
        if (isinstance(body.get("fullName"), str)
                and body.get("fullName").strip().lower() != full_name):
            raise ApiError(400, {"error": "bad_agent"})
    else:
        if not isinstance(full_name, str):
            raise ApiError(400, {"error": "bad_agent"})
        full_name = full_name.strip().lower()
        if not NAME_RE.fullmatch(full_name):
            raise ApiError(404, {"error": "name_not_found"})
        with db().cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT token_id FROM names WHERE full_name = %s",
                        (full_name,))
            row = cur.fetchone()
            if row is None:
                raise ApiError(404, {"error": "name_not_found"})
            cur.execute(
                "SELECT agent_id FROM agents"
                " WHERE name_token_id = %s AND active = TRUE",
                (row["token_id"],))
            agent = cur.fetchone()
        if agent is None:
            raise ApiError(404, {"error": "no_active_agent"})
        agent_id = int(agent["agent_id"])
    if not NAME_RE.fullmatch(full_name):
        raise ApiError(400, {"error": "bad_agent"})
    # Validate the document before any chain call (fail fast).
    if document.get("type") != tag:
        raise ApiError(400, {"error": "document_invalid"})
    if tag == "identity-verified":
        if not isinstance(document.get("signature"), str):
            raise ApiError(400, {"error": "document_invalid"})
    else:
        endpoint = document.get("endpoint")
        if (not isinstance(endpoint, str) or not endpoint
                or not endpoint.startswith(("http://", "https://"))):
            raise ApiError(400, {"error": "document_invalid"})
    doc_raw = json.dumps(document, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":")).encode("utf-8")
    if len(doc_raw) > VALIDATION_UPLOAD_MAX_DOC_BYTES:
        raise ApiError(400, {"error": "document_invalid"})
    # Target URL + requestHash (validator read on-chain, current value).
    # The URL base is normally https://haha.meme/validations; tests may
    # point it at ipfs:// so the validator fetches via a local gateway.
    filename = "%s-%s-v%d.json" % (
        full_name, VALIDATION_UPLOAD_URL_TAGS[tag], version)
    if VALIDATION_UPLOAD_URL_BASE.endswith("://"):
        request_uri = VALIDATION_UPLOAD_URL_BASE + filename
    else:
        request_uri = (VALIDATION_UPLOAD_URL_BASE.rstrip("/") + "/"
                       + filename)
    try:
        validator = _upload_chain_validator()
    except Exception as exc:
        sys.stderr.write("[upload] validator() failed: %r\n" % exc)
        raise ApiError(503, {"error": "chain_unavailable"})
    req_hash = _upload_request_hash(validator, agent_id, request_uri)
    # Auth signature: inside the document for identity-verified, in the
    # request body for endpoint-reachable.
    if tag == "identity-verified":
        signature = document.get("signature")
        sig_type = document.get("signatureType")
        if not isinstance(signature, str) or not signature:
            raise ApiError(400, {"error": "document_invalid"})
    else:
        signature = body.get("signature")
        sig_type = body.get("signatureType")
        if not isinstance(signature, str) or not signature:
            raise ApiError(403, {"error": "signature_invalid"})
    try:
        sig_bytes = bytes.fromhex(
            signature[2:] if signature.startswith("0x") else signature)
        if len(sig_bytes) != 65:
            raise ValueError("signature is not 65 bytes")
    except ValueError:
        raise ApiError(403, {"error": "signature_invalid"})
    try:
        identity = _upload_chain_identity()
        owner = _upload_chain_owner(identity, agent_id)
    except Exception as exc:
        sys.stderr.write("[upload] ownerOf failed: %r\n" % exc)
        raise ApiError(403, {"error": "not_agent_owner"})
    recovered = _upload_recover(req_hash, agent_id, sig_bytes, sig_type,
                                owner)
    if recovered is None:
        raise ApiError(403, {"error": "not_agent_owner"})
    # All checks passed: reserve a daily slot, then write atomically.
    _upload_reserve_slot(agent_id)
    target = os.path.join(VALIDATION_UPLOAD_DIR, filename)
    os.makedirs(VALIDATION_UPLOAD_DIR, exist_ok=True)
    tmp = os.path.join(VALIDATION_UPLOAD_DIR,
                       ".%s.tmp.%d" % (filename, os.getpid()))
    try:
        with open(tmp, "wb") as f:
            f.write(doc_raw)
        os.chmod(tmp, 0o644)
        os.replace(tmp, target)
    except OSError as exc:
        sys.stderr.write("[upload] write failed: %r\n" % exc)
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise ApiError(500, {"error": "upload_failed"})
    return {"url": request_uri, "requestHash": req_hash,
            "agentId": agent_id}



ROUTES = [
    (re.compile(r"^/v1/season1/days/([0-9]+)$"),
     lambda q, m: (h_season_day(m.group(1)), "no-store")),
    (re.compile(r"^/v1/season1/leaderboard/([0-9]+)$"),
     lambda q, m: (h_season_leaderboard(m.group(1), q), "no-store")),
    (re.compile(r"^/v1/season1/eligibility/(0x[0-9a-fA-F]{64})$"),
     lambda q, m: (h_season_eligibility(m.group(1), q), "no-store")),
    (re.compile(r"^/v1/season1/proof/(0x[0-9a-fA-F]{64})$"),
     lambda q, m: (h_season_proof(m.group(1), q), "no-store")),
    (re.compile(r"^/v1/season1/orders/([0-9]+)$"),
     lambda q, m: (h_season_order(m.group(1)), "no-store")),
    (re.compile(r"^/v1/season1/orders$"),
     lambda q, m: (h_season_orders(q), "no-store")),
    (re.compile(r"^/v1/season1/verify/(0x[0-9a-fA-F]{64})$"),
     lambda q, m: (h_season_verify(m.group(1), q), "no-store")),
    (re.compile(r"^/v1/season1/findings$"),
     lambda q, m: (h_season_findings_list(), "no-store")),
    (re.compile(r"^/v1/season1/findings/(0x[0-9a-fA-F]{64})$"),
     lambda q, m: (h_season_finding(m.group(1)), "no-store")),
    (re.compile(r"^/v1/season1/taskpack/([0-9]+)$"),
     lambda q, m: (h_season_taskpack(m.group(1)), "no-store")),
    (re.compile(r"^/health$"), lambda q, m: (h_health(), "no-store")),
    (re.compile(r"^/v1/listings$"), lambda q, m: (h_listings(q), LIST_CACHE)),
    (re.compile(r"^/v1/trades$"), lambda q, m: (h_trades(q), LIST_CACHE)),
    (re.compile(r"^/v1/names$"), lambda q, m: (h_names(q), LIST_CACHE)),
    (re.compile(r"^/v1/events$"), lambda q, m: (h_events(q), LIST_CACHE)),
    (re.compile(r"^/v1/agents$"), lambda q, m: (h_agents(q), LIST_CACHE)),
    (re.compile(r"^/v1/agents/by-name/([^/]+)/registration\.json$"),
     lambda q, m: (h_agent_registration_by_name(m.group(1)), "no-store")),
    (re.compile(r"^/v1/agents/([^/]+)/registration\.json$"),
     lambda q, m: (h_agent_registration_by_id(m.group(1)), "no-store")),
    (re.compile(r"^/v1/agents/([^/]+)/validations$"),
     lambda q, m: (h_agent_validations(m.group(1)), "no-store")),
    (re.compile(r"^/v1/validations/([^/]+)$"),
     lambda q, m: (h_validation_detail(m.group(1)), "no-store")),
    (re.compile(r"^/v1/leaderboard/reputation$"),
     lambda q, m: (h_reputation(q), LIST_CACHE)),
    (re.compile(r"^/v1/names/([^/]+)/generations$"),
     lambda q, m: (h_generations(m.group(1), q), LIST_CACHE)),
    (re.compile(r"^/v1/names/([^/]+)/image\.svg$"),
     lambda q, m: (h_name_image(m.group(1)), SVG_CACHE, "image/svg+xml")),
    (re.compile(r"^/v1/names/([^/]+)/metadata$"),
     lambda q, m: (h_name_metadata(m.group(1)), NAME_CACHE)),
    (re.compile(r"^/v1/names/([^/]+)$"),
     lambda q, m: (h_name(m.group(1)), NAME_CACHE)),
    (re.compile(r"^/v1/owners/(0x[0-9a-fA-F]{40})/names$"),
     lambda q, m: (h_owner_names(m.group(1)), NAME_CACHE)),
    (re.compile(r"^/v1/owners/(0x[0-9a-fA-F]{40})/primary$"),
     lambda q, m: (h_primary(m.group(1)), NAME_CACHE)),
    (re.compile(r"^/v1/reviews/latest$"),
     lambda q, m: (h_latest_reviews(q), LIST_CACHE)),
    (re.compile(r"^/v1/leaderboard/points$"),
     lambda q, m: (h_points(q), LIST_CACHE)),
    (re.compile(r"^/v1/stats$"), lambda q, m: (h_stats(), LIST_CACHE)),
]


# ---------------------------------------------------------------- findings POST guards (H9 + L5)

def _check_json_post_headers(handler):
    """H9: the findings publish endpoint is a cross-site writable POST.
    Two cheap gates stop a malicious page from firing it in a victim's
    browser as a "simple request" (no preflight):
    (1) Content-Type must be application/json — a simple request can
    only carry text/plain etc., so requiring JSON forces a preflight,
    which the API never answers with CORS headers; (2) when Origin or
    Referer is present it must be https://haha.meme. A missing Origin
    (curl, server-side callers) is allowed through.
    """
    ctype = (handler.headers.get("Content-Type") or "").split(";")[0].strip().lower()
    if ctype != "application/json":
        raise ApiError(400, {"error": "bad_content_type"})
    origin = handler.headers.get("Origin")
    if origin is not None:
        if origin.strip().rstrip("/") != "https://haha.meme":
            raise ApiError(403, {"error": "forbidden_origin"})
        return
    referer = handler.headers.get("Referer")
    if referer:
        p = urlparse(referer)
        if (p.scheme, p.netloc) != ("https", "haha.meme"):
            raise ApiError(403, {"error": "forbidden_origin"})


# L5: per-(IP + hash) rate limit for the findings publish route:
# max 3 attempts per hash per minute. The client IP is the first entry
# of X-Forwarded-For (nginx restores it); when there is no X-Forwarded-
# For header the key degrades to per-hash only (ip=None), which still
# bounds re-publishing of any single report.
_FINDINGS_RATE_LIMIT = {}
_FINDINGS_RATE_LIMIT_LOCK = threading.Lock()
_FINDINGS_RATE_LIMIT_MAX = 3
_FINDINGS_RATE_LIMIT_WINDOW = 60.0


def _findings_client_ip(handler):
    xff = handler.headers.get("X-Forwarded-For")
    if xff:
        first = xff.split(",")[0].strip()
        if first:
            return first
    return None


def _check_findings_rate_limit(handler, digest_hex):
    key = (_findings_client_ip(handler), digest_hex.lower())
    now = time.time()
    with _FINDINGS_RATE_LIMIT_LOCK:
        for k in list(_FINDINGS_RATE_LIMIT):
            kept = [t for t in _FINDINGS_RATE_LIMIT[k]
                    if now - t < _FINDINGS_RATE_LIMIT_WINDOW]
            if kept:
                _FINDINGS_RATE_LIMIT[k] = kept
            else:
                del _FINDINGS_RATE_LIMIT[k]
        hits = _FINDINGS_RATE_LIMIT.get(key, [])
        if len(hits) >= _FINDINGS_RATE_LIMIT_MAX:
            raise ApiError(429, {"error": "rate_limited"})
        hits.append(now)
        _FINDINGS_RATE_LIMIT[key] = hits


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _send(self, status, body, cache=None, content_type=None):
        if isinstance(body, (bytes, bytearray)):
            # Raw bytes (e.g. a canonical task pack file): serve byte-identical.
            data = bytes(body)
            if content_type is None:
                content_type = "application/json"
        elif content_type == "image/svg+xml":
            data = body.encode("utf-8") if isinstance(body, str) else body
        else:
            data = json.dumps(body, ensure_ascii=False).encode()
            content_type = "application/json"
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        if cache:
            self.send_header("Cache-Control", cache)
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        try:
            parsed = urlparse(self.path)
            q = parse_qs(parsed.query)
            for pat, fn in ROUTES:
                m = pat.match(parsed.path)
                if m:
                    res = fn(q, m)
                    if len(res) == 3:
                        body, cache, ctype = res
                    else:
                        body, cache = res
                        ctype = None
                    self._send(200, body, cache, ctype)
                    return
            self._send(404, {"error": "not_found"}, "no-store")
        except ApiError as e:
            self._send(e.status, e.body, "no-store")
        except Exception as e:
            sys.stderr.write("handler error: %r\n" % e)
            try:
                self._send(500, {"error": "internal"}, "no-store")
            except Exception:
                pass

    def _read_json_body(self):
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            raise ApiError(400, {"error": "bad_body"})
        if length <= 0 or length > 262144:  # 256 KB cap
            raise ApiError(400, {"error": "bad_body"})
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            raise ApiError(400, {"error": "bad_body"})

    def do_POST(self):
        try:
            parsed = urlparse(self.path)
            m = re.fullmatch(
                r"/v1/season1/findings/(0x[0-9a-fA-F]{64})/report",
                parsed.path or "")
            if m:
                _check_json_post_headers(self)
                _check_findings_rate_limit(self, m.group(1))
                body = self._read_json_body()
                res = h_season_finding_publish(m.group(1), body)
                self._send(200, res, "no-store")
                return
            if parsed.path == "/v1/validations/upload":
                _check_json_post_headers(self)
                body = self._read_json_body()
                res = h_validations_upload(body)
                self._send(200, res, "no-store")
                return
            self._send(405, {"error": "method_not_allowed"}, "no-store")
        except ApiError as e:
            self._send(e.status, e.body, "no-store")
        except Exception as e:
            sys.stderr.write("handler error: %r\n" % e)
            try:
                self._send(500, {"error": "internal"}, "no-store")
            except Exception:
                pass


def main():
    global _cfg, _rpc
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", default=None)
    ap.add_argument("--port", type=int, default=8787)
    args = ap.parse_args()
    _cfg = get_config(args.env)
    if not _cfg["database_url"]:
        sys.stderr.write("FATAL: no DATABASE_URL in env %s\n" % _cfg["env_path"])
        sys.exit(2)
    _rpc = RpcClient(_cfg["rpc_urls"], timeout=10)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    sys.stderr.write("api listening on 127.0.0.1:%d\n" % args.port)
    server.serve_forever()


if __name__ == "__main__":
    main()
