// 直接调用 Etherscan V2 多链 API 验证 BSC 主网合约。
// 用法：node tools/deploy-panel/verify-live.mjs <API_KEY>
import { request as httpsRequest } from "node:https";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const API_KEY = process.argv[2] || process.env.ETHERSCAN_API_KEY;

const CHAIN_ID = 56; // BNB 主网

const CONTRACTS = [
  { name: "HahaNamePolicy", addr: "0x1F260aa05334f76A6E1d6Fbd416F4d07d6Bf3d96" },
  { name: "HahaMetadata", addr: "0x790B670D664Ea0046b0F2D395C182AdD3C389aB4" },
  { name: "HahaResolver", addr: "0x85C2DbdFd81A14B958B360159e8710E6c15370D6" },
  { name: "HahaRegistry", addr: "0x712Ca65E2F6F5436C846569949072C8941982987" },
  { name: "HahaRegistrar", addr: "0x43426E37a31AafDaba851858e34B81DC300650F8" },
  { name: "HahaAgentIdentity", addr: "0x54A70BF81B288d41013D7b57c2Db0922f1E1a4d4" },
  { name: "HahaPoints", addr: "0xB2D023b8B5895835EFD71C1150BeAD7bD735DfAa" },
  { name: "HahaReputation", addr: "0xf1A41B30d0c03fE178D3d76CBE6044E9D5Ce1800" },
  { name: "HahaMarketplace", addr: "0xC7294DF776344A39726b4C1256Faf0e728c99835" },
  { name: "HahaDeployer", addr: "0x3c7Bd1649ac03AfB65e6E10F949f45d764B6b601" },
];

function post(url, formBody) {
  return new Promise((resolve, reject) => {
    const u = new URL(url);
    const req = httpsRequest(
      { hostname: u.hostname, path: u.pathname + u.search, method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded", "Content-Length": Buffer.byteLength(formBody) } },
      (res) => {
        let data = "";
        res.on("data", (c) => (data += c));
        res.on("end", () => resolve(JSON.parse(data)));
      }
    );
    req.on("error", reject);
    req.write(formBody);
    req.end();
  });
}

function submitVerify(name, addr) {
  const sourceCode = readFileSync(join(__dirname, "public", "verify", `${name}.json`), "utf8");
  const form = new URLSearchParams({
    module: "contract",
    action: "verifysourcecode",
    contractaddress: addr,
    sourceCode,
    codeformat: "solidity-standard-json-input",
    contractname: `src/${name}.sol:${name}`,
    compilerversion: "v0.8.28+commit.7893614a",
    optimizationUsed: "1",
    runs: "200",
    licenseType: "3",
  });
  const url = `https://api.etherscan.io/v2/api?chainid=${CHAIN_ID}&apikey=${API_KEY}`;
  return post(url, form.toString());
}

function checkStatus(guid) {
  const form = new URLSearchParams({
    module: "contract",
    action: "checkverifystatus",
    guid,
  });
  const url = `https://api.etherscan.io/v2/api?chainid=${CHAIN_ID}&apikey=${API_KEY}`;
  return post(url, form.toString());
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function main() {
  if (!API_KEY) {
    console.error("用法: node verify-live.mjs <API_KEY>");
    process.exit(1);
  }

  for (const c of CONTRACTS) {
    try {
      const submit = await submitVerify(c.name, c.addr);
      if (submit.status !== "1") {
        console.log(`✗ ${c.name}: 提交失败 — ${submit.result}`);
        continue;
      }
      const guid = submit.result;
      console.log(`→ ${c.name}: 已提交，GUID=${guid}，等待编译...`);
      // 轮询状态（最多 60 秒）
      let done = false;
      for (let i = 0; i < 30; i++) {
        await sleep(3000);
        const st = await checkStatus(guid);
        if (st.status === "1") {
          console.log(`✓ ${c.name}: 验证成功`);
          done = true;
          break;
        }
        if (st.result && st.result.includes("Fail")) {
          console.log(`✗ ${c.name}: 验证失败 — ${st.result}`);
          done = true;
          break;
        }
      }
      if (!done) console.log(`… ${c.name}: 仍在排队，请稍后到 BscScan 查看`);
    } catch (e) {
      console.log(`✗ ${c.name}: 异常 — ${e.message}`);
    }
  }
}

main();
