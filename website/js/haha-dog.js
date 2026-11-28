/* Haha Dog shared reads: ABI helpers, BSC RPC with an explicit gas limit, and the
 * in-browser Haha AI model. Read-only: no wallet, no signing, no transactions.
 * Needs window.HAHA_ADDRESSES (addresses.js) and window.HahaAIModel (haha-ai-model.js). */
(function () {
  "use strict";
  var A = window.HAHA_ADDRESSES || {};
  var M = window.HahaAIModel;

  /* Every read goes through the same-origin proxy first. nginx sends /rpc/ to the site's keyed nodes and fails over
   * to the official BSC node by itself; keys never reach the browser. /rpc-bsc/ is the browser's own second try
   * (official node, no keyed node) for the case nginx cannot see: a JSON-RPC error inside an HTTP 200. It answers
   * 404 until that location exists, which just moves on to the next entry. publicnode is the only direct host the
   * CSP allows. */
  var RPCS = [window.HAHA_RPC_URL || "/rpc/", "/rpc-bsc/", "https://bsc-rpc.publicnode.com"];
  var LIMITISH = /limit|rate|timeout|capacity|too large|unauthor|exceed/i;
  /* HahaDog was deployed at block 136153154 (2026-11-28 02:47:48 UTC = 10:47:48 UTC+8). Fixed values, shown as the mint start. */
  var START = { block: 136153154, ts: 1795834068, local: "2026-11-28 10:47", utc: "2026-11-28 02:47" };
  /* tokenURI is about 4.5M gas and svgOf about 2.3M gas inside eth_call. */
  var GAS_HEAVY = 30000000;
  var STATUS = { none: 0, generating: 1, ready: 2, stalled: 3 };
  var SEL = {
    totalSupply: "0x18160ddd", quotaOf: "0xef23b3a3", dogOf: "0x2f403afd", tokenURI: "0xc87b56dd",
    ownerOf: "0x6352211e", balanceOf: "0x70a08231", getApproved: "0x081812fc", svgOf: "0xb951bff3",
    listings: "0xde74e57b", isValid: "0xf577a500", pending: "0x0964c95b", modelHash: "0x5e3b773d", modelData: "0xbd0a9d4e"
  };
  var idc = 1;

  function strip(h) { h = String(h || ""); return h.slice(0, 2) === "0x" ? h.slice(2) : h; }
  function pad(h) { return ("0000000000000000000000000000000000000000000000000000000000000000" + h).slice(-64); }
  function encUint(v) { return pad(BigInt(v).toString(16)); }
  function encAddr(a) { return pad(strip(a).toLowerCase()); }
  function word(hex, i) { return strip(hex).slice(i * 64, i * 64 + 64); }
  function wUint(hex, i) { return BigInt("0x" + word(hex, i)); }
  function wAddr(hex, i) { return "0x" + word(hex, i).slice(24); }
  function wStr(hex) {
    var h = strip(hex), off = Number(BigInt("0x" + h.slice(0, 64))) * 2;
    var len = Number(BigInt("0x" + h.slice(off, off + 64)));
    var body = h.slice(off + 64, off + 64 + len * 2), bytes = new Uint8Array(len);
    for (var i = 0; i < len; i++) bytes[i] = parseInt(body.substr(i * 2, 2), 16);
    return new TextDecoder().decode(bytes);
  }
  function wBytes(hex) {
    var h = strip(hex), off = Number(BigInt("0x" + h.slice(0, 64))) * 2;
    var len = Number(BigInt("0x" + h.slice(off, off + 64)));
    var body = h.slice(off + 64, off + 64 + len * 2), bytes = new Uint8Array(len);
    for (var i = 0; i < len; i++) bytes[i] = parseInt(body.substr(i * 2, 2), 16);
    return bytes;
  }
  var ZERO = "0x0000000000000000000000000000000000000000";

  function post(url, body, ms) {
    var ctrl = new AbortController(), timer = setTimeout(function () { ctrl.abort(); }, ms || 20000);
    return fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body), signal: ctrl.signal })
      .then(function (r) { clearTimeout(timer); if (!r.ok) throw new Error("rpc http " + r.status); return r.json(); })
      .catch(function (e) { clearTimeout(timer); throw e; });
  }
  /* Try the nodes in order; the first usable answer wins. A revert is a real answer. */
  function rpc(body, ms) {
    var i = 0, last = null;
    function next() {
      if (i >= RPCS.length) return Promise.reject(last || new Error("rpc failed"));
      var url = RPCS[i++];
      return post(url, body, ms).then(function (j) {
        /* A node that only says "rate limited" for every item is not an answer: try the next one. */
        var items = Array.isArray(j) ? j : [j], errs = items.filter(function (x) { return x && x.error; });
        if (errs.length && errs.length === items.length && errs.every(function (x) { return LIMITISH.test(String(x.error.message)); })) {
          last = new Error(errs[0].error.message); return next();
        }
        j.__host = /^https?:/.test(url) ? url.replace(/^https:\/\//, "") : "haha.meme" + url.replace(/\/$/, "");
        return j;
      }).catch(function (e) { last = e; return next(); });
    }
    return next();
  }
  function call(to, data, gas) {
    var p = { to: to, data: data };
    if (gas) p.gas = "0x" + gas.toString(16);
    return rpc({ jsonrpc: "2.0", id: idc++, method: "eth_call", params: [p, "latest"] }).then(function (j) {
      if (j.error) throw new Error(j.error.message || "eth_call error");
      if (!j.result || j.result === "0x") throw new Error("empty result");
      return { result: j.result, host: j.__host };
    });
  }
  /* Many small calls in one HTTP request. A failed item is null. */
  function batch(calls) {
    if (!calls.length) return Promise.resolve([]);
    var body = calls.map(function (c, i) {
      return { jsonrpc: "2.0", id: i + 1, method: "eth_call", params: [{ to: c.to, data: c.data }, "latest"] };
    });
    return rpc(body).then(function (arr) {
      if (!Array.isArray(arr)) throw new Error("batch unsupported");
      var by = {};
      arr.forEach(function (x) { by[x.id] = x; });
      return calls.map(function (_, i) {
        var x = by[i + 1];
        return x && !x.error && x.result && x.result !== "0x" ? x.result : null;
      });
    });
  }
  function chunked(calls, size) {
    var parts = [];
    for (var i = 0; i < calls.length; i += size) parts.push(calls.slice(i, i + size));
    var out = [];
    return parts.reduce(function (p, part) {
      return p.then(function () { return batch(part).then(function (r) { out = out.concat(r); }); });
    }, Promise.resolve()).then(function () { return out; });
  }

  function dogCall(sel, arg) { return { to: A.dog, data: sel + (arg == null ? "" : arg) }; }

  /* Indexer (haha.meme/api/v1/dog/*). Optional: every caller has a chain fallback. */
  function indexBase() { var b = window.HAHA_INDEXER_BASE; return typeof b === "string" ? b.replace(/\/+$/, "") : ""; }
  function idx(path, ms) {
    var base = indexBase();
    if (!base) return Promise.reject(new Error("no indexer"));
    var ctrl = new AbortController(), timer = setTimeout(function () { ctrl.abort(); }, ms || 6000);
    return fetch(base + path, { headers: { accept: "application/json" }, signal: ctrl.signal })
      .then(function (r) { clearTimeout(timer); if (!r.ok) throw new Error("indexer http " + r.status); return r.json(); })
      .catch(function (e) { clearTimeout(timer); throw e; });
  }
  /* Indexer token item -> the same shape parseDog returns. status "check" (indexer has no hash) becomes 0 and is
   * completed from the chain by completeFromChain. */
  function fromIdx(t) {
    var st = t.status === "ready" ? STATUS.ready : t.status === "generating" ? STATUS.generating : 0;
    return { id: Number(t.tokenId), commitBlock: t.commitBlock, targetBlock: t.targetBlock, rerolls: t.rerolls, status: st, seed: t.seed || null, owner: t.owner, via: "indexer" };
  }
  function completeFromChain(ds) {
    var need = ds.filter(function (d) { return d.status === 0 || (d.status === STATUS.ready && !d.seed); }).map(function (d) { return d.id; });
    if (!need.length) return Promise.resolve(ds);
    return api.dogsOf(need).then(function (cs) {
      var by = {}; cs.forEach(function (c) { if (c) by[c.id] = c; });
      return ds.map(function (d) { var c = by[d.id]; return c ? Object.assign({}, c, { owner: d.owner, via: "indexer+chain" }) : d; });
    });
  }
  var Sold_SIG = "Sold(uint256,address,address,uint256,uint256,uint256)";
  function topic0(sig) { var b = new TextEncoder().encode(sig); return "0x" + M.hex(M.keccak256(b)); }

  var api = {
    ADDR: A, STATUS: STATUS, SEL: SEL, ZERO: ZERO, GAS_HEAVY: GAS_HEAVY,
    encUint: encUint, encAddr: encAddr, wUint: wUint, wAddr: wAddr, wStr: wStr, wBytes: wBytes,
    bscscan: function (a) { return "https://bscscan.com/address/" + a + "#code"; },
    isAddr: function (s) { return /^0x[0-9a-fA-F]{40}$/.test(String(s || "")); },
    short: function (a) { a = String(a || ""); return a.slice(0, 6) + "…" + a.slice(-4); },
    weiToBnb: function (wei) {
      var s = BigInt(wei).toString();
      if (s.length <= 18) { var f = s.padStart(18, "0").replace(/0+$/, ""); return f ? "0." + f : "0"; }
      var ip = s.slice(0, s.length - 18), fp = s.slice(s.length - 18).replace(/0+$/, "");
      return fp ? ip + "." + fp : ip;
    },
    call: call, batch: batch, chunked: chunked,

    START: START, idx: idx, indexBase: indexBase, fromIdx: fromIdx, completeFromChain: completeFromChain,
    balanceOf: function (addr) { return call(A.dog, SEL.balanceOf + encAddr(addr)).then(function (r) { return Number(wUint(r.result, 0)); }); },
    /* My dogs with state, newest first. Indexer first (one request), checked against the chain's balanceOf so a lagging
     * or empty index never hides a dog; falls back to scanning ownerOf from the newest token down. */
    myDogs: function (addr) {
      return api.balanceOf(addr).then(function (bal) {
        if (!bal) return { dogs: [], via: "chain" };
        return idx("/v1/dog/owners/" + String(addr).toLowerCase() + "/tokens").then(function (j) {
          var items = j.items || [];
          if (items.length !== bal) throw new Error("index behind");
          return completeFromChain(items.map(fromIdx)).then(function (ds) { return { dogs: ds, via: "indexer" }; });
        }).catch(function () {
          return api.totalSupply().then(function (n) { return api.tokensOf(addr, n, bal); }).then(function (ids) {
            return api.dogsOf(ids).then(function (ds) { return { dogs: ds.filter(Boolean), via: "chain" }; });
          });
        });
      }).then(function (r) { r.dogs.sort(function (a, b) { return b.id - a.id; }); return r; });
    },
    /* Floor, latest sale and 24h volume from Sold logs when the indexer is not answering. Scans back in 5000-block
     * windows from the head, at most `maxWindows` of them, and says whether it reached the 24h mark. */
    recentSales: function (maxWindows) {
      var t0 = topic0(Sold_SIG), WIN = 5000, DAY = 192000, sales = [], from, head;
      return rpc({ jsonrpc: "2.0", id: idc++, method: "eth_blockNumber", params: [] }).then(function (j) {
        head = parseInt(j.result, 16);
        var wins = [];
        for (var i = 0; i < (maxWindows || 20); i++) { var hi = head - i * WIN, lo = Math.max(START.block, hi - WIN + 1); if (hi < START.block) break; wins.push([lo, hi]); }
        var out = [];
        function run(k) {
          if (k >= wins.length) return Promise.resolve();
          var part = wins.slice(k, k + 4);
          return Promise.all(part.map(function (w) {
            return rpc({ jsonrpc: "2.0", id: idc++, method: "eth_getLogs", params: [{ fromBlock: "0x" + w[0].toString(16), toBlock: "0x" + w[1].toString(16), address: A.dogMarket, topics: [t0] }] }).then(function (r) {
              if (r.error) throw new Error(r.error.message || "getLogs");
              (r.result || []).forEach(function (l) { out.push({ id: Number(BigInt(l.topics[1])), price: wUint(l.data, 0), block: parseInt(l.blockNumber, 16) }); });
            });
          })).then(function () { return run(k + 4); });
        }
        return run(0).then(function () {
          out.sort(function (a, b) { return b.block - a.block; });
          var lowest = wins.length ? wins[wins.length - 1][0] : head;
          return { sales: out, complete24h: lowest <= head - DAY || lowest <= START.block, head: head, day: DAY };
        });
      });
    },

    totalSupply: function () { return call(A.dog, SEL.totalSupply).then(function (r) { return Number(wUint(r.result, 0)); }); },
    /* quotaOf returns (0, 0) for a wallet without a usable .ai. */
    quotaOf: function (addr) {
      return call(A.dog, SEL.quotaOf + encAddr(addr)).then(function (r) { return { allowed: Number(wUint(r.result, 0)), used: Number(wUint(r.result, 1)) }; });
    },
    parseDog: function (hex, id) {
      if (!hex) return null;
      var seed = word(hex, 4);
      return {
        id: id, commitBlock: Number(wUint(hex, 0)), targetBlock: Number(wUint(hex, 1)), rerolls: Number(wUint(hex, 2)),
        status: Number(wUint(hex, 3)), seed: /^0+$/.test(seed) ? null : "0x" + seed
      };
    },
    dogsOf: function (ids) {
      return chunked(ids.map(function (id) { return dogCall(SEL.dogOf, encUint(id)); }), 60).then(function (rs) {
        return rs.map(function (h, i) { return api.parseDog(h, ids[i]); });
      });
    },
    ownersOf: function (ids) {
      return chunked(ids.map(function (id) { return dogCall(SEL.ownerOf, encUint(id)); }), 100).then(function (rs) {
        return rs.map(function (h) { return h ? wAddr(h, 0) : null; });
      });
    },
    /* Token ids held by an account: ownerOf from the newest token down (the NFT is not enumerable). With `want`
     * (balanceOf) it stops as soon as that many are found. */
    tokensOf: function (addr, total, want) {
      var lower = String(addr).toLowerCase(), found = [], top = total;
      function step() {
        if (top < 1 || (want != null && found.length >= want)) return Promise.resolve(found.sort(function (a, b) { return a - b; }));
        var ids = [];
        for (var i = 0; i < 100 && top - i >= 1; i++) ids.push(top - i);
        top -= ids.length;
        return api.ownersOf(ids).then(function (owners) {
          ids.forEach(function (id, i) { if (owners[i] && owners[i].toLowerCase() === lower) found.push(id); });
          return step();
        });
      }
      return step();
    },
    listingsOf: function (ids) {
      return chunked(ids.map(function (id) { return { to: A.dogMarket, data: SEL.listings + encUint(id) }; }), 100).then(function (rs) {
        return rs.map(function (h, i) {
          if (!h) return null;
          var seller = wAddr(h, 0);
          if (seller === ZERO) return null;
          return { id: ids[i], seller: seller, priceWei: wUint(h, 1), rerolls: Number(wUint(h, 2)) };
        });
      });
    },
    validOf: function (ids) {
      return chunked(ids.map(function (id) { return { to: A.dogMarket, data: SEL.isValid + encUint(id) }; }), 100).then(function (rs) {
        return rs.map(function (h) { return !!h && wUint(h, 0) === 1n; });
      });
    },
    pendingOf: function (addr) {
      return call(A.dogMarket, SEL.pending + encAddr(addr)).then(function (r) { return wUint(r.result, 0); });
    },
    /* On-chain SVG for a seed: HahaDogRenderer.svgOf(seed) at a high gas limit. */
    chainSvg: function (seedHex) {
      return call(A.dogRenderer, SEL.svgOf + strip(seedHex).toLowerCase(), GAS_HEAVY).then(function (r) { return { svg: wStr(r.result), host: r.host }; });
    },
    /* HahaDog.tokenURI(tokenId): data:application/json;base64 with name, image and attributes. */
    chainToken: function (id) {
      return call(A.dog, SEL.tokenURI + encUint(id), GAS_HEAVY).then(function (r) {
        var uri = wStr(r.result), b64 = uri.replace(/^data:application\/json;base64,/, "");
        var bin = atob(b64), bytes = new Uint8Array(bin.length);
        for (var i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
        var meta = JSON.parse(new TextDecoder().decode(bytes));
        var img = String(meta.image || "").replace(/^data:image\/svg\+xml;base64,/, "");
        var sb = atob(img), sbytes = new Uint8Array(sb.length);
        for (var j = 0; j < sb.length; j++) sbytes[j] = sb.charCodeAt(j);
        return { meta: meta, svg: new TextDecoder().decode(sbytes), host: r.host };
      });
    },
    modelDataCheck: function () {
      return Promise.all([call(A.dogModel, SEL.modelHash), call(A.dogModel, SEL.modelData, 30000000)]).then(function (a) {
        var bytes = wBytes(a[1].result);
        return { declared: "0x" + word(a[0].result, 0), computed: "0x" + M.hex(M.keccak256(bytes)), size: bytes.length, host: a[1].host };
      });
    }
  };

  /* In-browser model: same integer inference as the contracts, loaded once. */
  var modelReady = null;
  api.model = function () {
    if (!modelReady) {
      var get = function (n) { return fetch("/ai-model/" + n, { cache: "force-cache" }).then(function (r) { if (!r.ok) throw new Error(n); return r.json(); }); };
      modelReady = Promise.all([get("weights-int8.json"), get("trait-templates.json")]).then(function (a) { return { W: a[0], TPL: a[1] }; });
    }
    return modelReady;
  };
  api.render = function (seedHex) {
    return api.model().then(function (m) {
      var t = M.traits(m.W, m.TPL, M.fromHex(seedHex));
      return { t: t, svg: M.svgFor(t) };
    });
  };
  window.HahaDog = api;
})();
