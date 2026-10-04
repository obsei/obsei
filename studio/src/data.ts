import type { Evidence, Snapshot } from "./types";

const TOKEN_KEY = "obsei-token";

export type Mode = "demo" | "live";

export class DataSource {
  private constructor(
    readonly mode: Mode,
    readonly snapshot: Snapshot,
    private readonly token: string | null,
  ) {}

  static async open(): Promise<DataSource | "unauthorized"> {
    const demo = await fetch("data.json").catch(() => null);
    if (demo?.ok) return new DataSource("demo", (await demo.json()) as Snapshot, null);
    const token = sessionStorage.getItem(TOKEN_KEY);
    const live = await fetch("../api/snapshot", { headers: authHeaders(token) });
    if (live.status === 401) return "unauthorized";
    if (!live.ok) throw new Error(`snapshot failed: ${live.status}`);
    return new DataSource("live", (await live.json()) as Snapshot, token);
  }

  static saveToken(token: string): void {
    sessionStorage.setItem(TOKEN_KEY, token);
  }

  async evidence(themeId: string): Promise<Evidence[]> {
    const cached = this.snapshot.evidence[themeId];
    if (cached && cached.length > 0) return cached;
    if (this.mode === "demo") return [];
    const response = await fetch(`../api/themes/${encodeURIComponent(themeId)}`, {
      headers: authHeaders(this.token),
    });
    return response.ok ? ((await response.json()) as Evidence[]) : [];
  }

  async ask(question: string): Promise<string> {
    const response = await fetch("../api/ask", {
      method: "POST",
      headers: { ...authHeaders(this.token), "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    const body = (await response.json()) as { answer?: string; error?: string };
    return body.answer ?? `Error: ${body.error ?? response.status}`;
  }
}

function authHeaders(token: string | null): Record<string, string> {
  return token ? { Authorization: `Bearer ${token}` } : {};
}
