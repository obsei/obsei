import type { Evidence, Role, Snapshot } from "./types";

const TOKEN_KEY = "obsei-token";

export type Mode = "demo" | "export" | "live";

export type Refusal = "unauthorized" | "forbidden";

export interface Denied {
  denied: Refusal;
  hadToken: boolean;
}

export type EvidenceResult = { items: Evidence[] } | { denied: Refusal };

export class DataSource {
  private constructor(
    readonly mode: Mode,
    readonly snapshot: Snapshot,
    private readonly token: string | null,
  ) {}

  static async open(): Promise<DataSource | Denied> {
    const exported = document.querySelector<HTMLMetaElement>('meta[name="obsei-data"]')?.content;
    if (exported && exported !== "api") {
      const response = await fetch(exported);
      if (!response.ok) throw new Error(`${exported} failed: ${response.status}`);
      const snapshot = (await response.json()) as Snapshot;
      return new DataSource(snapshot.demo ? "demo" : "export", snapshot, null);
    }
    const token = DataSource.token();
    const live = await fetch("../api/snapshot", { headers: authHeaders(token) });
    const denied = refusal(live.status);
    if (denied) return { denied, hadToken: token !== null };
    if (!live.ok) throw new Error(`snapshot failed: ${live.status}`);
    return new DataSource("live", (await live.json()) as Snapshot, token);
  }

  private static token(): string | null {
    try {
      return sessionStorage.getItem(TOKEN_KEY);
    } catch {
      return null;
    }
  }

  static saveToken(token: string): void {
    try {
      sessionStorage.setItem(TOKEN_KEY, token);
    } catch {
      // Storage is blocked; the token is then asked for again on reload.
    }
  }

  get role(): Role | null {
    return this.snapshot.role ?? null;
  }

  get canReadEvidence(): boolean {
    return this.mode !== "live" || this.role !== "viewer";
  }

  async evidence(themeId: string): Promise<EvidenceResult> {
    const cached = this.snapshot.evidence[themeId];
    if (cached && cached.length > 0) return { items: cached };
    if (this.mode !== "live") return { items: [] };
    if (!this.canReadEvidence) return { denied: "forbidden" };
    const response = await fetch(`../api/themes/${encodeURIComponent(themeId)}`, {
      headers: authHeaders(this.token),
    });
    const denied = refusal(response.status);
    if (denied) return { denied };
    return { items: response.ok ? ((await response.json()) as Evidence[]) : [] };
  }

  async ask(question: string): Promise<string> {
    const response = await fetch("../api/ask", {
      method: "POST",
      headers: { ...authHeaders(this.token), "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    const denied = refusal(response.status);
    if (denied) return denied === "forbidden" ? "Ask needs the analyst role." : "Invalid token.";
    const body = (await response.json().catch(() => ({}))) as { answer?: string; error?: string };
    return body.answer ?? `Error: ${body.error ?? response.status}`;
  }
}

function refusal(status: number): Refusal | null {
  return status === 401 ? "unauthorized" : status === 403 ? "forbidden" : null;
}

function authHeaders(token: string | null): Record<string, string> {
  return token ? { Authorization: `Bearer ${token}` } : {};
}
