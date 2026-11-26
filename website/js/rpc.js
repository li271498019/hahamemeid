/* 轻量 RPC 读链层：只读 BSC 主网（chainId 56），不连钱包、不签名。
 * fetch POST eth_call 到 window.HAHA_RPC_URL，无外部库，自行实现 ABI 编解码。
 * keccak256 不在浏览器里实现：aiId 一律从 statusOf(address) 返回的第一个字段拿，不要算哈希。
 * 全部方法返回 Promise；eth_call revert 或网络失败时返回 null（resolveAi / ownerOf 的
 * 零地址也返回 null），由调用方显示失败状态，绝不退回假数据。 */
(function () {
  var ZERO_ADDRESS = "0x0000000000000000000000000000000000000000";
  var idCounter = 1;

  function rpcUrl() {
    return window.HAHA_RPC_URL || "https://bsc-dataseed.binance.org";
  }

  function addrOf(key) {
    var a = window.HAHA_ADDRESSES && window.HAHA_ADDRESSES[key];
    if (!a) throw new Error("missing address: " + key);
    return a;
  }

  function strip0x(s) {
    s = String(s || "");
    return s.slice(0, 2).toLowerCase() === "0x" ? s.slice(2) : s;
  }

  function padLeft(hex, len) {
    hex = strip0x(hex);
    while (hex.length < len) hex = "0" + hex;
    return hex;
  }

  function encodeUint(value) {
    return padLeft(BigInt(value).toString(16), 64);
  }

  function encodeAddress(address) {
    return padLeft(strip0x(address), 64);
  }

  function encodeBytes32(hex) {
    return padLeft(strip0x(hex), 64);
  }

  function utf8Bytes(str) {
    if (typeof TextEncoder !== "undefined") return new TextEncoder().encode(str);
    var bytes = [];
    var s = unescape(encodeURIComponent(str));
    for (var i = 0; i < s.length; i++) bytes.push(s.charCodeAt(i));
    return bytes;
  }

  function bytesToHex(bytes) {
    var out = "";
    for (var i = 0; i < bytes.length; i++) {
      var h = bytes[i].toString(16);
      out += h.length < 2 ? "0" + h : h;
    }
    return out;
  }

  function hexToBytes(hex) {
    hex = strip0x(hex);
    var bytes = new Uint8Array(hex.length / 2);
    for (var i = 0; i < bytes.length; i++) bytes[i] = parseInt(hex.substr(i * 2, 2), 16);
    return bytes;
  }

  function hexToString(hex) {
    var bytes = hexToBytes(hex);
    if (typeof TextDecoder !== "undefined") return new TextDecoder().decode(bytes);
    var s = "";
    for (var i = 0; i < bytes.length; i++) s += String.fromCharCode(bytes[i]);
    return decodeURIComponent(escape(s));
  }

  /* types: "address" | "uint256" | "uint8" | "uint64" | "bytes32" | "string" */
  function encodeCall(selector, types, values) {
    var headSize = types.length * 32;
    var head = [];
    var tail = "";
    var tailBytes = 0;
    for (var i = 0; i < types.length; i++) {
      var t = types[i];
      var v = values[i];
      if (t === "string") {
        head.push(encodeUint(headSize + tailBytes));
        var data = utf8Bytes(String(v == null ? "" : v));
        var dataHex = bytesToHex(data);
        var paddedLen = Math.ceil(data.length / 32) * 32;
        while (dataHex.length < paddedLen * 2) dataHex += "00";
        tail += encodeUint(data.length) + dataHex;
        tailBytes += 32 + paddedLen;
      } else if (t === "address") {
        head.push(encodeAddress(v));
      } else if (t === "bytes32") {
        head.push(encodeBytes32(v));
      } else {
        head.push(encodeUint(v));
      }
    }
    return selector + head.join("") + tail;
  }

  function slot(hex, index) {
    return strip0x(hex).substr(index * 64, 64);
  }

  function decodeUintAt(hex, index) {
    return BigInt("0x" + slot(hex, index));
  }

  function decodeUintNumberAt(hex, index) {
    return Number(decodeUintAt(hex, index));
  }

  function decodeBoolAt(hex, index) {
    return slot(hex, index).slice(-2) !== "00";
  }

  function decodeAddressAt(hex, index) {
    return "0x" + slot(hex, index).slice(24);
  }

  function decodeBytes32At(hex, index) {
    return "0x" + slot(hex, index);
  }

  function decodeStringAt(hex, index) {
    var offset = Number(decodeUintAt(hex, index));
    var len = Number(BigInt("0x" + strip0x(hex).substr(offset * 2, 64)));
    var dataHex = strip0x(hex).substr((offset + 32) * 2, len * 2);
    return hexToString(dataHex);
  }

  /* ---- RPC 节点：4 节点竞速 ----
   * 查名只打 fastUrls() 的 4 个节点，同时发出去，谁先成功用谁。
   * 之前那套测速排序（对 50 个公开节点调 eth_blockNumber、按延迟排序、结果存
   * localStorage 10 分钟）已经不用了，相关代码和 50 节点表都已删掉。
   * 同源 /rpc/（本站代理）通常最快；它失败时公开节点接着答。
   * 全部失败最多等 RPC_CALL_TIMEOUT_MS，不再串行累加到一分钟。 */
  var rpcCurrent = null;    /* 最近一次成功的节点 */
  var RPC_CALL_TIMEOUT_MS = 1800;

  function postCallRaw(url, body, timeoutMs) {
    var ctrl = null;
    var timer = 0;
    try {
      if (typeof AbortController !== "undefined") {
        ctrl = new AbortController();
        timer = setTimeout(function () { ctrl.abort(); }, timeoutMs || 8000);
      }
    } catch (err) {}
    var opts = {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    };
    if (ctrl) opts.signal = ctrl.signal;
    return fetch(url, opts).then(function (res) {
      if (timer) clearTimeout(timer);
      if (!res.ok) throw new Error("rpc http " + res.status);
      return res.json();
    }).then(function (json) {
      if (json.error) throw new Error(json.error.message || "rpc error");
      return json;
    }).catch(function (err) {
      if (timer) clearTimeout(timer);
      throw err;
    });
  }

  /* 不再测速：直接返回 fastUrls() 的 4 个节点。保留这个入口是为兼容
   * 之前调 probeRpc 的地方，实际不做任何网络请求。 */
  function probeRpc() {
    var urls = fastUrls();
    if (!rpcCurrent) rpcCurrent = urls[0] || null;
    return Promise.resolve(urls.slice());
  }

  /* 查名只打这几个节点，并且同时发出去，谁先成功用谁。
   * 同源 /rpc/（本站代理）通常最快；它不可用时公开节点接着答。
   * 全部失败最多等 RPC_CALL_TIMEOUT_MS，不再串行累加到一分钟。 */
  function fastUrls() {
    var urls = [];
    function add(u) {
      if (u && urls.indexOf(u) === -1) urls.push(u);
    }
    add(rpcUrl());
    add("https://bsc-dataseed.binance.org");
    add("https://bsc-dataseed1.defibit.io");
    add("https://bsc-rpc.publicnode.com");
    return urls;
  }

  /* 新鲜度取舍（接受现状）：竞速取最先成功的节点，不比块高。
   * 落后节点可能返回旧状态（如刚成交的挂单仍显示在售），页面短暂显示过期数据，
   * 刷新即恢复；真要买时链上 buy() 会校验，挂单没了就 revert，不会丢钱。
   * 4 个节点都是主流公开节点，基本不会落后，所以不加块高校验。 */
  function rpcRace(body) {
    var urls = fastUrls();
    return new Promise(function (resolve, reject) {
      var pending = urls.length;
      var settled = false;
      var lastErr = null;
      urls.forEach(function (url) {
        postCallRaw(url, body, RPC_CALL_TIMEOUT_MS).then(function (json) {
          if (settled) return;
          settled = true;
          rpcCurrent = url;
          resolve(json);
        }).catch(function (err) {
          lastErr = err;
          if (settled) return;
          pending -= 1;
          if (pending <= 0) reject(lastErr || new Error("all rpc endpoints failed"));
        });
      });
    });
  }

  function ethCall(to, data) {
    var body = {
      jsonrpc: "2.0",
      id: idCounter++,
      method: "eth_call",
      params: [{ to: to, data: data }, "latest"]
    };
    return rpcRace(body).then(function (json) {
      var result = json && json.result;
      if (!result || result === "0x") throw new Error("eth_call reverted");
      return result;
    });
  }

  /* 一次 HTTP 里问多笔 eth_call。某一笔 revert 时那一项是 null，其它照常返回。
   * 批量不受支持时退化为逐笔 ethCall：最快节点返回非数组说明它不支持 batch，
   * 这时逐笔再问一遍（每笔失败仍返回 null）。全部节点都失败时不退化，
   * 直接抛错，让页面正常显示“链读不到”，不要误报成别的状态。 */
  function ethBatch(calls) {
    var body = calls.map(function (c, i) {
      return {
        jsonrpc: "2.0",
        id: i + 1,
        method: "eth_call",
        params: [{ to: c.to, data: c.data }, "latest"]
      };
    });
    function fallback() {
      return Promise.all(calls.map(function (c) {
        return ethCall(c.to, c.data).catch(function () { return null; });
      }));
    }
    return rpcRace(body).then(function (arr) {
      if (!Array.isArray(arr)) return fallback();
      var byId = {};
      arr.forEach(function (item) {
        if (item && item.id != null) byId[item.id] = item;
      });
      return calls.map(function (_, i) {
        var item = byId[i + 1];
        if (!item || item.error || !item.result || item.result === "0x") return null;
        return item.result;
      });
    });
  }

  /* Keccak-256（不是 NIST SHA3）。用来在浏览器里算 tokenId，省掉一次 nodeOf。 */
  var KECCAK_RC = [
    0x0000000000000001n, 0x0000000000008082n, 0x800000000000808an, 0x8000000080008000n,
    0x000000000000808bn, 0x0000000080000001n, 0x8000000080008081n, 0x8000000000008009n,
    0x000000000000008an, 0x0000000000000088n, 0x0000000080008009n, 0x000000008000000an,
    0x000000008000808bn, 0x800000000000008bn, 0x8000000000008089n, 0x8000000000008003n,
    0x8000000000008002n, 0x8000000000000080n, 0x000000000000800an, 0x800000008000000an,
    0x8000000080008081n, 0x8000000000008080n, 0x0000000080000001n, 0x8000000080008008n
  ];
  var KECCAK_ROTC = [1, 3, 6, 10, 15, 21, 28, 36, 45, 55, 2, 14, 27, 41, 56, 8, 25, 43, 62, 18, 39, 61, 20, 44];
  var KECCAK_PILN = [10, 7, 11, 17, 18, 3, 5, 16, 8, 21, 24, 4, 15, 23, 19, 13, 12, 2, 20, 14, 22, 9, 6, 1];
  var KECCAK_MASK = (1n << 64n) - 1n;
  var TLD_NODE_HEX = {
    haha: "aa5a3a58f7c8841455eecaa0c6a6a0b40ace5681fbb31361a0d45b168179128f",
    meme: "74df4ab2564a9f9bb6d4b6b77bf4fc02ac80f07bd9e1776d3967578b3fc36be4"
  };

  function keccakRotl(x, n) {
    n = BigInt(n);
    return ((x << n) | (x >> (64n - n))) & KECCAK_MASK;
  }

  function keccakF(st) {
    var bc = new Array(5);
    var round, i, j, t;
    for (round = 0; round < 24; round++) {
      for (i = 0; i < 5; i++) bc[i] = st[i] ^ st[i + 5] ^ st[i + 10] ^ st[i + 15] ^ st[i + 20];
      for (i = 0; i < 5; i++) {
        t = bc[(i + 4) % 5] ^ keccakRotl(bc[(i + 1) % 5], 1);
        for (j = 0; j < 25; j += 5) st[j + i] ^= t;
      }
      t = st[1];
      for (i = 0; i < 24; i++) {
        j = KECCAK_PILN[i];
        bc[0] = st[j];
        st[j] = keccakRotl(t, KECCAK_ROTC[i]);
        t = bc[0];
      }
      for (j = 0; j < 25; j += 5) {
        for (i = 0; i < 5; i++) bc[i] = st[j + i];
        for (i = 0; i < 5; i++) st[j + i] ^= (~bc[(i + 1) % 5]) & bc[(i + 2) % 5] & KECCAK_MASK;
      }
      st[0] ^= KECCAK_RC[round];
    }
  }

  function keccak256Bytes(bytes) {
    var rate = 136;
    var st = [];
    var i;
    for (i = 0; i < 25; i++) st.push(0n);
    var msg = [];
    for (i = 0; i < bytes.length; i++) msg.push(bytes[i]);
    msg.push(0x01);
    while (msg.length % rate !== rate - 1) msg.push(0);
    msg.push(0x80);
    var off, lane, shift;
    for (off = 0; off < msg.length; off += rate) {
      for (i = 0; i < rate; i++) {
        lane = (i / 8) | 0;
        shift = BigInt((i % 8) * 8);
        st[lane] ^= BigInt(msg[off + i]) << shift;
      }
      keccakF(st);
    }
    var out = new Uint8Array(32);
    for (i = 0; i < 32; i++) {
      lane = (i / 8) | 0;
      shift = BigInt((i % 8) * 8);
      out[i] = Number((st[lane] >> shift) & 0xffn);
    }
    return out;
  }

  function bytesTo0x(bytes) {
    var hex = "";
    for (var i = 0; i < bytes.length; i++) {
      var h = bytes[i].toString(16);
      hex += h.length < 2 ? "0" + h : h;
    }
    return "0x" + hex;
  }

  function hexToU8(hex) {
    hex = strip0x(hex);
    var out = new Uint8Array(hex.length / 2);
    for (var i = 0; i < out.length; i++) out[i] = parseInt(hex.substr(i * 2, 2), 16);
    return out;
  }

  function tldKey(tld) {
    return (tld === "meme" || tld === 1 || tld === "1") ? "meme" : "haha";
  }

  /* tokenId = uint256(keccak256(tldNode ++ keccak256(label)))，与 HahaNamehash.namehash 一致。 */
  function tokenIdOf(label, tld) {
    var labelHash = keccak256Bytes(utf8Bytes(String(label)));
    var parent = hexToU8(TLD_NODE_HEX[tldKey(tld)]);
    var packed = new Uint8Array(64);
    packed.set(parent, 0);
    packed.set(labelHash, 32);
    return bytesTo0x(keccak256Bytes(packed));
  }

  function weiToBnbString(wei) {
    var one = BigInt("1000000000000000000");
    var whole = wei / one;
    var rest = wei % one;
    if (rest === BigInt(0)) return whole.toString();
    var frac = rest.toString();
    while (frac.length < 18) frac = "0" + frac;
    frac = frac.replace(/0+$/, "");
    return whole.toString() + "." + frac;
  }

  function safe(fn) {
    return fn().catch(function () { return null; });
  }

  /* aiName 的按地址缓存：同一页多次显示同一地址只查一次链。
   * 进行中的请求也缓存同一份 Promise，避免两次重渲染在结果回来前
   * 各发一次 handleOf（H6）。 */
  var aiNameCache = {};
  var aiNamePending = {};

  window.HahaRPC = {
    call: ethCall,
    batch: ethBatch,
    tokenIdOf: tokenIdOf,
    probeRpc: probeRpc,
    rpcStatus: function () {
      var all = fastUrls();
      return { current: rpcCurrent, top: all.slice(), total: all.length };
    },

    /* ownerOfHandle(string) 0x1da94fb4，aiRegistry。零地址或 revert 视为查无此名，返回 null。 */
    resolveAi: function (label) {
      return safe(function () {
        return ethCall(addrOf("aiRegistry"), encodeCall("0x1da94fb4", ["string"], [label]))
          .then(function (hex) {
            var a = decodeAddressAt(hex, 0);
            return a.toLowerCase() === ZERO_ADDRESS ? null : a;
          });
      });
    },

    /* handleOf(address) 0xc50a1514，返回 string。
     * 注意：这里不包 safe()。RPC 失败时直接 reject，让调用方（aiName）
     * 区分“链读不到”（可重试）和“确实无 .ai”（空串，可缓存）。
     * 之前包 safe() 会把一次超时也变成 null，aiName 再把它当成“无 .ai”
     * 缓存起来，该地址本页就再也变不成 .ai。 */
    handleOf: function (address) {
      return ethCall(addrOf("aiRegistry"), encodeCall("0xc50a1514", ["address"], [address]))
        .then(function (hex) { return decodeStringAt(hex, 0); });
    },

    /* aiName(address)：把 EVM 地址换成它的 .ai（带 .ai 后缀），无 .ai 时返回 null。
     * handleOf 返回原始 handle（如 hahameme）或空串/null。调用方用 aiName || address
     * 显示：有 .ai 显示 .ai，无 .ai 照常显示 EVM 地址。 */
    aiName: function (address) {
      if (!address) return Promise.resolve(null);
      var key = String(address).toLowerCase();
      if (aiNameCache[key] !== undefined) return Promise.resolve(aiNameCache[key]);
      if (aiNamePending[key]) return aiNamePending[key];
      var p = window.HahaRPC.handleOf(address).then(function (h) {
        var v = (h && String(h).trim()) ? String(h).trim() + ".ai" : null;
        aiNameCache[key] = v;
        delete aiNamePending[key];
        return v;
      }, function (e) { delete aiNamePending[key]; throw e; });
      aiNamePending[key] = p;
      return p;
    },

    /* nodeOf(string,uint8) 0xd87b2dcb，registrar。tld 0=.haha，1=.meme。返回 bytes32 hex（即 tokenId）。
     * 各页传的 tld 有的是 "haha"/"meme" 字符串，有的是 0/1，这里统一归一化为 0/1，
     * 否则 BigInt("haha") 会抛错、safe() 吞掉后返回 null，首页会把所有名字误判为「已铸造」。 */
    nodeOf: function (label, tld) {
      var t = (tld === "meme" || tld === 1 || tld === "1") ? 1 : 0;
      return safe(function () {
        return ethCall(addrOf("registrar"), encodeCall("0xd87b2dcb", ["string", "uint8"], [label, t]))
          .then(function (hex) { return decodeBytes32At(hex, 0); });
      });
    },

    /* ownerOf(uint256) 0x6352211e，registrar。revert 视为未铸造，返回 null。 */
    ownerOf: function (tokenId) {
      return safe(function () {
        return ethCall(addrOf("registrar"), encodeCall("0x6352211e", ["uint256"], [BigInt(tokenId)]))
          .then(function (hex) {
            var a = decodeAddressAt(hex, 0);
            return a.toLowerCase() === ZERO_ADDRESS ? null : a;
          });
      });
    },

    /* available(string,uint8) 0xc7f54685，registrar。tld 同 nodeOf 归一化为 0/1。 */
    available: function (label, tld) {
      var t = (tld === "meme" || tld === 1 || tld === "1") ? 1 : 0;
      return safe(function () {
        return ethCall(addrOf("registrar"), encodeCall("0xc7f54685", ["string", "uint8"], [label, t]))
          .then(function (hex) { return decodeBoolAt(hex, 0); });
      });
    },

    /* isBlacklisted(string) 0xff626727，namePolicy。 */
    isBlacklisted: function (label) {
      return safe(function () {
        return ethCall(addrOf("namePolicy"), encodeCall("0xff626727", ["string"], [label]))
          .then(function (hex) { return decodeBoolAt(hex, 0); });
      });
    },

    /* isReserved(string) 0x3361c49e，namePolicy。 */
    isReserved: function (label) {
      return safe(function () {
        return ethCall(addrOf("namePolicy"), encodeCall("0x3361c49e", ["string"], [label]))
          .then(function (hex) { return decodeBoolAt(hex, 0); });
      });
    },

    /* nextMintAt(bytes32) 0x2d1a7c8b，registrar。返回秒数（number）。 */
    nextMintAt: function (aiId) {
      return safe(function () {
        return ethCall(addrOf("registrar"), encodeCall("0x2d1a7c8b", ["bytes32"], [aiId]))
          .then(function (hex) { return decodeUintNumberAt(hex, 0); });
      });
    },

    /* listings(uint256) 0xde74e57b，marketplace。返回 {seller, priceWei, priceBnb}。 */
    listings: function (tokenId) {
      return safe(function () {
        return ethCall(addrOf("marketplace"), encodeCall("0xde74e57b", ["uint256"], [BigInt(tokenId)]))
          .then(function (hex) {
            var priceWei = decodeUintAt(hex, 1);
            return {
              seller: decodeAddressAt(hex, 0),
              priceWei: priceWei.toString(),
              priceBnb: weiToBnbString(priceWei)
            };
          });
      });
    },

    /* pendingWithdrawal(address) 0x0964c95b，marketplace。返回待提货款（wei，十进制字符串），"0" 表示没有可提的。 */
    pendingWithdrawal: function (address) {
      return safe(function () {
        return ethCall(addrOf("marketplace"), encodeCall("0x0964c95b", ["address"], [address]))
          .then(function (hex) {
            return decodeUintAt(hex, 0).toString();
          });
      });
    },

    /* getScore(uint256) 0x0e1af57b，reputation。返回 {count, sum}。 */
    getScore: function (agentId) {
      return safe(function () {
        return ethCall(addrOf("reputation"), encodeCall("0x0e1af57b", ["uint256"], [agentId]))
          .then(function (hex) {
            return { count: decodeUintNumberAt(hex, 0), sum: decodeUintNumberAt(hex, 1) };
          });
      });
    },

    /* taskPack(uint64) 0x07a68cfc，season1。返回任务包哈希（bytes32 hex）。 */
    taskPackHash: function (dayIndex) {
      return safe(function () {
        return ethCall(addrOf("season1"), encodeCall("0x07a68cfc", ["uint64"], [dayIndex]))
          .then(function (hex) { return decodeBytes32At(hex, 0); });
      });
    },

    /* agentOfName(uint256) 0x750f6013，agentIdentity。返回 agentId（number），无 agent 时为 0。 */
    agentOfName: function (tokenId) {
      return safe(function () {
        return ethCall(addrOf("agentIdentity"), encodeCall("0x750f6013", ["uint256"], [BigInt(tokenId)]))
          .then(function (hex) { return decodeUintNumberAt(hex, 0); });
      });
    },

    /* isActive(uint256) 0x82afd23b，agentIdentity。 */
    isActive: function (agentId) {
      return safe(function () {
        return ethCall(addrOf("agentIdentity"), encodeCall("0x82afd23b", ["uint256"], [agentId]))
          .then(function (hex) { return decodeBoolAt(hex, 0); });
      });
    },

    /* operatorCount(uint256) 0xd07343ea，agentIdentity。返回当前 operator 数量（0–8）。
     * selector 已用 keccak256 验算。 */
    operatorCount: function (agentId) {
      return safe(function () {
        return ethCall(addrOf("agentIdentity"), encodeCall("0xd07343ea", ["uint256"], [agentId]))
          .then(function (hex) { return decodeUintNumberAt(hex, 0); });
      });
    },

    /* isAgentOperator(uint256,address) 0xe8d96dd2，agentIdentity。
     * selector 已用 keccak256 验算；链上实测 agentId 30 返回 false，未 revert。 */
    isAgentOperator: function (agentId, operator) {
      return safe(function () {
        return ethCall(addrOf("agentIdentity"), encodeCall("0xe8d96dd2", ["uint256", "address"], [agentId, operator]))
          .then(function (hex) { return decodeBoolAt(hex, 0); });
      });
    },

    /* getAgent(uint256) 0x2de5aaf7，agentIdentity。
     * 按 AgentView 字段顺序：address, bool, uint256, uint64, bytes32, address, string。
     * 注意：AgentView 含 string（uri），是动态 tuple，返回数据首字是 0x20 偏移，
     * 字段从第 1 字起；uri 的偏移是相对 tuple 起始（第 1 字、字节 32）的，
     * 须加上 tuple 起始字节数才是绝对偏移。旧代码从第 0 字读，全部错位，
     * uri 解码抛错导致 agent 页报“链上找不到这个名字”。 */
    getAgent: function (agentId) {
      return safe(function () {
        return ethCall(addrOf("agentIdentity"), encodeCall("0x2de5aaf7", ["uint256"], [agentId]))
          .then(function (hex) {
            var base = Number(decodeUintAt(hex, 0)); // tuple 起始字节（恒为 32）
            var bw = base / 32; // tuple 起始字
            var uriRel = Number(decodeUintAt(hex, bw + 6));
            var uriAbs = base + uriRel;
            var uriLen = Number(BigInt("0x" + strip0x(hex).substr(uriAbs * 2, 64)));
            var uri = hexToString(strip0x(hex).substr((uriAbs + 32) * 2, uriLen * 2));
            return {
              owner: decodeAddressAt(hex, bw + 0),
              active: decodeBoolAt(hex, bw + 1),
              nameTokenId: decodeBytes32At(hex, bw + 2),
              generation: decodeUintNumberAt(hex, bw + 3),
              operatorAiId: decodeBytes32At(hex, bw + 4),
              wallet: decodeAddressAt(hex, bw + 5),
              uri: uri
            };
          });
      });
    },

    /* statusOf(address) 0x97a5d5b5，points。按 PointsStatus 字段顺序解码。 */
    statusOf: function (address) {
      return safe(function () {
        return ethCall(addrOf("points"), encodeCall("0x97a5d5b5", ["address"], [address]))
          .then(function (hex) {
            return {
              aiId: decodeBytes32At(hex, 0),
              balance: decodeUintNumberAt(hex, 1),
              holdsAi: decodeBoolAt(hex, 2),
              holdsName: decodeBoolAt(hex, 3),
              currentDay: decodeUintNumberAt(hex, 4),
              nextResetAt: decodeUintNumberAt(hex, 5),
              checkInToday: decodeUintNumberAt(hex, 6),
              mintRewardsToday: decodeUintNumberAt(hex, 7),
              likeToday: decodeUintNumberAt(hex, 8),
              retweetToday: decodeUintNumberAt(hex, 9),
              commentToday: decodeUintNumberAt(hex, 10),
              gameRoundsToday: decodeUintNumberAt(hex, 11),
              reviewsGivenToday: decodeUintNumberAt(hex, 12),
              reviewsReceivedToday: decodeUintNumberAt(hex, 13),
              mintRewardsPerDay: decodeUintNumberAt(hex, 14),
              gameRoundsPerDay: decodeUintNumberAt(hex, 15),
              followClaimed: decodeBoolAt(hex, 16)
            };
          });
      });
    },

    /* balanceOf(bytes32) 0x6c7f1542，points。返回积分余额（number）。 */
    balanceOfAi: function (aiId) {
      return safe(function () {
        return ethCall(addrOf("points"), encodeCall("0x6c7f1542", ["bytes32"], [aiId]))
          .then(function (hex) { return decodeUintNumberAt(hex, 0); });
      });
    },

    /* primaryName(address) 0xeba951aa，resolver。返回主名 fullName，未设置返回 ""，失败返回 null。
     * selector 已用 keccak256 验算。主名是链上唯一能不靠索引取到用户名字的地方。 */
    primaryName: function (address) {
      return safe(function () {
        return ethCall(addrOf("resolver"), encodeCall("0xeba951aa", ["address"], [address]))
          .then(function (hex) { var s = decodeStringAt(hex, 0); return s ? s : ""; });
      });
    },

    /* uniqueKeyUsed(bytes32,bytes32,bytes32) 0x60496f96，points。激活积分是否已领过。
     * 激活调 earn(ACTION_ACTIVATE, user, ACTIVATE_ONCE)，keyMode 为 Lifetime，领过即永久 true。
     * ACTION_ACTIVATE = bytes32("ACTIVATE")，ACTIVATE_ONCE = bytes32("ACTIVATE_ONCE")，右填充。
     * selector 已用 keccak256 验算。失败返回 null（不确定时不显示「已领取」）。 */
    activateClaimed: function (aiId) {
      return safe(function () {
        return ethCall(addrOf("points"), encodeCall("0x60496f96", ["bytes32", "bytes32", "bytes32"], ["0x4143544956415445000000000000000000000000000000000000000000000000", aiId, "0x41435449564154455f4f4e434500000000000000000000000000000000000000"]))
          .then(function (hex) { return decodeBoolAt(hex, 0); });
      });
    },

    /* 一次查出黑名单、保留名、持有人。ownerOf 对未铸造的名字会 revert，该项为 null。 */
    lookupName: function (label, tld) {
      var tokenId = tokenIdOf(label, tld);
      var calls = [
        { to: addrOf("namePolicy"), data: encodeCall("0xff626727", ["string"], [label]) },
        { to: addrOf("namePolicy"), data: encodeCall("0x3361c49e", ["string"], [label]) },
        { to: addrOf("registrar"), data: encodeCall("0x6352211e", ["uint256"], [BigInt(tokenId)]) }
      ];
      return ethBatch(calls).then(function (hexes) {
        var owner = null;
        if (hexes[2]) {
          var a = decodeAddressAt(hexes[2], 0);
          if (a.toLowerCase() !== ZERO_ADDRESS) owner = a;
        }
        return {
          tokenId: tokenId,
          blacklisted: hexes[0] ? decodeBoolAt(hexes[0], 0) : null,
          reserved: hexes[1] ? decodeBoolAt(hexes[1], 0) : null,
          owner: owner
        };
      });
    },

    /* feeBps() 0x24a9d853，marketplace。 */
    feeBps: function () {
      return safe(function () {
        return ethCall(addrOf("marketplace"), encodeCall("0x24a9d853", [], []))
          .then(function (hex) { return decodeUintNumberAt(hex, 0); });
      });
    }
  };

  /* ---- 索引 API（V1-INDEXER-SPEC.md，PR #9 已合并）----
   * 字段、路径、sort 枚举均按规格原文，不编造。uint256（tokenId、agentId、
   * priceWei、balance 等）一律按 API 返回的十进制字符串原样透传，不转 Number。
   * 门控：window.HAHA_INDEXER_BASE 为空字符串/未设置时，所有方法直接返回
   * 空结果，不发任何请求，页面据此显示空状态。设成 "/api" 后才真正请求：
   * 浏览器请求 {base}/health、{base}/v1/listings（对外是 /api/health、
   * /api/v1/listings），nginx 会去掉 /api，进程内部路由不加 /api 前缀。
   * 加载顺序：config.js（定义 HAHA_INDEXER_BASE）→ addresses.js → 本文件
   * （rpc.js，HahaRPC 与 HahaIndex 都在这里，不另建 js/index.js，各页只
   * 需加载 rpc.js 即可）。base 在每次调用时读取，不在加载时固化。 */
  function indexBase() {
    var b = window.HAHA_INDEXER_BASE;
    if (typeof b !== "string") return "";
    return b.replace(/\/+$/, "");
  }

  function clampLimit(v) {
    var n = parseInt(v, 10);
    if (isNaN(n)) return 24;
    return Math.min(50, Math.max(1, n));
  }

  function clampMinReviews(v) {
    var n = parseInt(v, 10);
    if (isNaN(n)) return 1;
    return Math.min(20, Math.max(1, n));
  }

  function emptyList() {
    return { items: [], nextCursor: null };
  }

  function indexQuery(params) {
    var q = new URLSearchParams();
    Object.keys(params).forEach(function (k) {
      var v = params[k];
      if (v !== undefined && v !== null && v !== "") q.set(k, String(v));
    });
    var s = q.toString();
    return s ? "?" + s : "";
  }

  function fetchIndex(path, query) {
    var base = indexBase();
    if (!base) return Promise.resolve(null);
    return fetch(base + path + (query || "")).then(function (res) {
      if (!res.ok) throw new Error("indexer http " + res.status);
      return res.json();
    });
  }

  function fetchIndexList(path, query) {
    return fetchIndex(path, query).then(function (json) {
      if (!json || !Array.isArray(json.items)) return emptyList();
      return { items: json.items, nextCursor: json.nextCursor != null ? json.nextCursor : null };
    }).catch(function () { return emptyList(); });
  }

  function validSort(value, allowed, fallback) {
    return allowed.indexOf(value) >= 0 ? value : fallback;
  }

  window.HahaIndex = {
    /* GET {base}/health → {ok, chainId, safeBlock, headBlock, lagBlocks, lastError}。
     * base 为空时返回 null；请求失败也返回 null。 */
    health: function () {
      if (!indexBase()) return Promise.resolve(null);
      return fetchIndex("/health").catch(function () { return null; });
    },

    /* GET {base}/v1/listings。sort: listed_desc（默认）/price_asc/price_desc；
     * tld: "haha"/"meme"；q: 完整小写 label 精确匹配。
     * 返回 {items:[{tokenId,label,tld,fullName,seller,priceWei,listedAt,
     * blockNumber,txHash,logIndex}], nextCursor}。 */
    listings: function (opts) {
      opts = opts || {};
      if (!indexBase()) return Promise.resolve(emptyList());
      return fetchIndexList("/v1/listings", indexQuery({
        sort: validSort(opts.sort, ["listed_desc", "price_asc", "price_desc"], "listed_desc"),
        tld: (opts.tld === "haha" || opts.tld === "meme") ? opts.tld : undefined,
        q: opts.q || undefined,
        limit: clampLimit(opts.limit),
        cursor: opts.cursor || undefined
      }));
    },

    /* GET {base}/v1/trades。sort: time_desc（默认）/price_desc；fullName 如 abc.haha。
     * 条目 {tokenId,label,tld,fullName,seller,buyer,priceWei,feeWei,proceedsWei,
     * tradedAt,blockNumber,txHash,logIndex}。 */
    trades: function (opts) {
      opts = opts || {};
      if (!indexBase()) return Promise.resolve(emptyList());
      return fetchIndexList("/v1/trades", indexQuery({
        sort: validSort(opts.sort, ["time_desc", "price_desc"], "time_desc"),
        fullName: opts.fullName || undefined,
        limit: clampLimit(opts.limit),
        cursor: opts.cursor || undefined
      }));
    },

    /* GET {base}/v1/agents。sort: activated_desc（默认）/stars_desc/reviews_desc。
     * 条目 {agentId,tokenId,label,tld,fullName,owner,operatorAiId,generation,
     * agentURI,active,starsSum,starsCount,activatedAt,blockNumber}。 */
    agents: function (opts) {
      opts = opts || {};
      if (!indexBase()) return Promise.resolve(emptyList());
      return fetchIndexList("/v1/agents", indexQuery({
        sort: validSort(opts.sort, ["activated_desc", "stars_desc", "reviews_desc"], "activated_desc"),
        limit: clampLimit(opts.limit),
        cursor: opts.cursor || undefined
      }));
    },

    /* GET {base}/v1/leaderboard/reputation。sort 只有 stars_desc；minReviews 默认 1（1–20）。
     * 条目与 agents 相同，另加 rank（从 1 起跨页连续）。 */
    reputationLeaderboard: function (opts) {
      opts = opts || {};
      if (!indexBase()) return Promise.resolve(emptyList());
      return fetchIndexList("/v1/leaderboard/reputation", indexQuery({
        sort: "stars_desc",
        minReviews: clampMinReviews(opts.minReviews),
        limit: clampLimit(opts.limit),
        cursor: opts.cursor || undefined
      }));
    },

    /* GET {base}/v1/reviews/latest。返回 {items:[{fullName,agentId,generation,
     * rater,raterAiId,raterAi,raterName,stars,review,edited,ratedAt,txHash}],
     * nextCursor}，按评价时间倒序（最新在前）。raterAi 为评价人的 .ai（带 .ai 后缀，
     * 无 .ai 时 null），raterName 为评价人最早铸的 haha id（无时 null）。limit 默认 24（1–50）。 */
    latestReviews: function (opts) {
      opts = opts || {};
      if (!indexBase()) return Promise.resolve(emptyList());
      return fetchIndexList("/v1/reviews/latest", indexQuery({
        limit: clampLimit(opts.limit)
      }));
    },

    /* GET {base}/v1/names/{fullName}/generations，fullName 如 abc.haha。
     * 返回 {fullName,tokenId,generations:[{generation,agentId,active,owner,
     * agentURI,starsSum,starsCount,activatedAt,resetAt,
     * reviews:[{rater,raterAiId,raterAi,raterName,stars,review,edited,ratedAt,txHash}],
     * reviewsTruncated?}]}，代数从大到小。raterAi/raterName 同 latestReviews。
     * 名字从未铸出时 API 404 → 返回 null；铸出过但无 agent 时 generations 为 []。 */
    generations: function (fullName) {
      if (!indexBase() || !fullName) return Promise.resolve(null);
      return fetchIndex("/v1/names/" + encodeURIComponent(String(fullName)) + "/generations")
        .then(function (json) {
          if (!json || !Array.isArray(json.generations)) return null;
          return json;
        })
        .catch(function () { return null; });
    },

    /* GET {base}/v1/leaderboard/points。sort 只有 balance_desc。
     * 条目 {rank,aiId,handle,name,balance,updatedAt}；handle 是 .ai 的原始 handle
     * （不带 .ai 后缀），name 是该 .ai 最早铸的 haha id（无时 null）。handle 为 null
     * 时调用方用缩短的 aiId 显示，不要编 .ai 名字。 */
    pointsLeaderboard: function (opts) {
      opts = opts || {};
      if (!indexBase()) return Promise.resolve(emptyList());
      return fetchIndexList("/v1/leaderboard/points", indexQuery({
        sort: "balance_desc",
        limit: clampLimit(opts.limit),
        cursor: opts.cursor || undefined
      }));
    },

    /* GET {base}/v1/names/{fullName}
     * 已铸造：{minted:true, tokenId, label, tld, fullName, owner, mintedAt, listing}
     * 索引里没有：{minted:false, ...listing:null}，HTTP 仍是 200。
     * 旧版索引没有这个路径时返回 null，调用方改走 lookupName。 */
    name: function (fullName) {
      if (!indexBase() || !fullName) return Promise.resolve(null);
      return fetchIndex("/v1/names/" + encodeURIComponent(String(fullName)))
        .then(function (json) {
          if (!json || typeof json.minted !== "boolean") return null;
          return json;
        })
        .catch(function () { return null; });
    },

    /* GET {base}/v1/owners/{address}/names → {owner, items:[...]}。
     * 失败（含旧版 404）时 {items:[], error:true}，页面不要当成“一个名字都没有”。 */
    namesOf: function (address) {
      if (!indexBase() || !address) return Promise.resolve({ owner: address || null, items: [], error: true });
      return fetchIndex("/v1/owners/" + encodeURIComponent(String(address)) + "/names")
        .then(function (json) {
          if (!json || !Array.isArray(json.items)) return { owner: address, items: [], error: true };
          return { owner: json.owner || address, items: json.items, error: false };
        })
        .catch(function () { return { owner: address, items: [], error: true }; });
    },

    /* GET {base}/v1/stats → {participants, activeAgents, totalActivations,
     * registered:{haha,meme,total},
     * threeDigit:{total,reserved,blacklisted,haha:{minted,remaining},meme:{...}},
     * threeLetter:{...}, latest:[{fullName,label,tld,mintedAt,blockNumber}],
     * safeBlock}。失败时返回 null。 */
    stats: function () {
      if (!indexBase()) return Promise.resolve(null);
      return fetchIndex("/v1/stats").catch(function () { return null; });
    }
  };
})();
