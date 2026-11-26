import { describe, it, expect } from "vitest";
import { ANNOUNCEMENT, withAnnouncement } from "../src/announcement.js";

describe("announcement", () => {
  it("is the copy L approved (Season 1 + contacts + tagline)", () => {
    expect(ANNOUNCEMENT).toBe(
      "【公告】第一季进行中：200 积分兑换一个 2 位名字，每天 20 个，截止 12 月 9 日。haha.meme 是基于币安 .ai Agent ID 的链上agent身份信誉协议。X @aihahameme｜Telegram https://t.me/idhahameme",
    );
    expect(ANNOUNCEMENT).toContain("第一季");
    expect(ANNOUNCEMENT).toContain("200 积分");
    expect(ANNOUNCEMENT).toContain("12 月 9 日");
    expect(ANNOUNCEMENT).toContain("基于币安 .ai Agent ID");
    expect(ANNOUNCEMENT).toContain("@aihahameme");
    expect(ANNOUNCEMENT).toContain("t.me/idhahameme");
  });

  it("is short (one line, under 200 chars)", () => {
    expect(ANNOUNCEMENT).not.toContain("\n");
    expect(ANNOUNCEMENT.length).toBeLessThan(200);
  });

  it("withAnnouncement appends it after a separator, keeping the data first", () => {
    const out = withAnnouncement('{"total":859}');
    expect(out.startsWith('{"total":859}')).toBe(true);
    expect(out).toContain("\n\n---\n");
    expect(out.endsWith(ANNOUNCEMENT)).toBe(true);
  });
});
