// Minimal client for the haha.meme indexer API (read-only).
// Base URL comes from HAHA_API_BASE, defaulting to the public API.
// On the production server the systemd unit sets HAHA_API_BASE to the
// local indexer (http://127.0.0.1:8787) so requests stay on the box.

export function apiBase(): string {
  const raw = (process.env.HAHA_API_BASE ?? "https://haha.meme/api").trim();
  return raw.replace(/\/+$/, "");
}

export class ApiError extends Error {
  readonly status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export async function apiGet(
  path: string,
  query: Record<string, string | number | boolean | undefined> = {},
): Promise<unknown> {
  const url = new URL(apiBase() + path);
  for (const [k, v] of Object.entries(query)) {
    if (v !== undefined && v !== null && v !== "") {
      url.searchParams.set(k, String(v));
    }
  }
  let res: Response;
  try {
    res = await fetch(url.toString(), {
      headers: { accept: "application/json" },
      signal: AbortSignal.timeout(15000),
    });
  } catch (e) {
    throw new ApiError(0, `cannot reach haha.meme API (${url.host}): ${e instanceof Error ? e.message : String(e)}`);
  }
  const text = await res.text();
  if (!res.ok) {
    throw new ApiError(res.status, `haha.meme API ${res.status} for ${path}: ${text.slice(0, 500)}`);
  }
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}
