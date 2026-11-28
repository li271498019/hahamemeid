/**
 * Render haha.meme Open Graph cards (1200×630 PNG).
 *
 *   node tools/og/render.mjs
 *
 * Needs Chrome and puppeteer-core. Chinese type uses WenQuanYi Micro Hei
 * when that file is present; otherwise the system CJK fallback.
 * Output: web/site/assets/og/*.png
 */
import { readFileSync, mkdirSync } from "fs";
import { createRequire } from "node:module";
import { dirname, resolve } from "path";
import { fileURLToPath } from "url";

const require = createRequire(import.meta.url);
const puppeteer = require("puppeteer-core");

const root = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const outDir = resolve(root, "web/site/assets/og");
const logo = resolve(root, "web/site/assets/logo/haha-logo-transparent.png");
const template = readFileSync(new URL("./card.html", import.meta.url), "utf8");

const CARDS = [
  {
    file: "og-default.png",
    kicker: "HAHA.MEME",
    title: "haha id",
    sub: "链上 agent 身份与信誉",
    en: "On-chain identity for agents",
    size: 84
  },
  {
    file: "og-home.png",
    kicker: "HAHA ID",
    title: "免费铸造您的\nhaha id",
    sub: "永久免费，复制指令给 agent",
    en: "Free forever. Your agent mints it.",
    size: 68
  },
  {
    file: "og-market.png",
    kicker: "MARKET",
    title: "交易市场",
    sub: "手续费 1%，卖家支付",
    en: "Listings in BNB. Fee 1%.",
    size: 80
  },
  {
    file: "og-erc8004.png",
    kicker: "ERC-8004",
    title: "身份和信誉",
    sub: "haha id，就是 Agent 的简历",
    en: "Reputation, written on-chain.",
    size: 76
  },
  {
    file: "og-earn.png",
    kicker: "EARN",
    title: "赚取积分",
    sub: "记在 .ai 上，不可转让",
    en: "Points sit on your .ai.",
    size: 80
  },
  {
    file: "og-how.png",
    kicker: "HOW IT WORKS",
    title: "公开、可核对",
    sub: "合约开源，谁都能查",
    en: "Open contracts. Check them yourself.",
    size: 72
  },
  {
    file: "og-scan.png",
    kicker: "HAHA SCAN",
    title: "区块浏览器",
    sub: "名字、交易、信誉，链上可验",
    en: "Names, trades, reputation. On-chain.",
    size: 76
  },
  {
    file: "og-season.png",
    kicker: "SEASON 1",
    title: "稀有域名空投",
    sub: "200 积分兑换 2 位字母名",
    en: "Two letters. 200 points.",
    size: 72
  }
];

function chromePath() {
  if (process.env.CHROME) return process.env.CHROME;
  return "/usr/local/bin/google-chrome";
}

mkdirSync(outDir, { recursive: true });

const browser = await puppeteer.launch({
  executablePath: chromePath(),
  headless: "new",
  args: ["--no-sandbox", "--disable-dev-shm-usage", "--font-render-hinting=none"]
});

const page = await browser.newPage();
await page.setViewport({ width: 1200, height: 630, deviceScaleFactor: 2 });
const logoUrl = "data:image/png;base64," + readFileSync(logo).toString("base64");

for (const card of CARDS) {
  await page.setContent(template, { waitUntil: "load" });
  await page.evaluate((card, logoUrl) => {
    document.getElementById("logo").src = logoUrl;
    document.getElementById("kicker").textContent = card.kicker;
    document.getElementById("title").textContent = card.title;
    document.getElementById("title").style.fontSize = card.size + "px";
    document.getElementById("sub").textContent = card.sub;
    document.getElementById("en").textContent = card.en;
  }, card, logoUrl);
  await page.waitForFunction(() => {
    const img = document.getElementById("logo");
    return img.complete && img.naturalWidth > 0;
  });
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({
    path: resolve(outDir, card.file),
    type: "png",
    clip: { x: 0, y: 0, width: 1200, height: 630 }
  });
  console.log(card.file);
}

await browser.close();
