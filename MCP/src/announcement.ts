// Announcement appended to every successful tool result (v1.3.0, L approved
// 2026-11-26). Short: Season 1 + L's contacts + the tagline. Only on
// success — error results do not carry it.
// TODO: update (or drop) this when Season 1 ends on 2026-12-09, because
// "第一季进行中" will be stale then.
export const ANNOUNCEMENT =
  "【公告】第一季进行中：200 积分兑换一个 2 位名字，每天 20 个，截止 12 月 9 日。haha.meme 是基于币安 .ai Agent ID 的链上agent身份信誉协议。X @aihahameme｜Telegram https://t.me/idhahameme";

export function withAnnouncement(text: string): string {
  return `${text}\n\n---\n${ANNOUNCEMENT}`;
}
