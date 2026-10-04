import { DataSource, type EvidenceResult, type Mode, type Refusal } from "./data";
import { clear, el, languageName, number } from "./dom";
import { KIND_LABELS, renderGraph } from "./graph";
import type { Bucket, Evidence, Theme } from "./types";

const app = document.getElementById("app")!;

function bars(title: string, buckets: Bucket[], label: (key: string) => string = (k) => k): HTMLElement {
  const max = Math.max(1, ...buckets.map((b) => b.count));
  return el(
    "section",
    { class: "panel" },
    el("h2", {}, title),
    buckets.length === 0
      ? el("p", { class: "muted" }, "No groups above the privacy threshold yet.")
      : el(
          "ul",
          { class: "bars" },
          ...buckets.slice(0, 10).map((b) =>
            el(
              "li",
              {},
              el("span", { class: "bar-label" }, label(b.key)),
              bar((100 * b.count) / max),
              el("span", { class: "bar-value" }, number.format(b.count)),
            ),
          ),
        ),
  );
}

function bar(percent: number): HTMLElement {
  const node = el("span", { class: "bar" });
  node.style.setProperty("--w", `${percent}%`);
  return node;
}

function trend(theme: Theme): HTMLElement {
  const delta = theme.last_7_days - theme.previous_7_days;
  const cls = delta > 0 ? "up" : delta < 0 ? "down" : "flat";
  const sign = delta > 0 ? "▲" : delta < 0 ? "▼" : "•";
  return el("span", { class: `trend ${cls}`, title: "Last 7 days vs previous 7 days" }, `${sign} ${Math.abs(delta)}`);
}

function chips(counts: Record<string, number>, label: (key: string) => string = (k) => k): HTMLElement {
  return el(
    "span",
    { class: "chips" },
    ...Object.entries(counts)
      .slice(0, 4)
      .map(([key, count]) => el("span", { class: "chip" }, `${label(key)} ${count}`)),
  );
}

function safeUrl(url: string): string | null {
  try {
    const parsed = new URL(url);
    return parsed.protocol === "https:" || parsed.protocol === "http:" ? parsed.href : null;
  } catch {
    return null;
  }
}

function original(url: string): HTMLElement {
  const href = safeUrl(url);
  return href
    ? el("a", { href, rel: "noopener noreferrer", target: "_blank" }, "original")
    : el("span", { class: "url" }, url);
}

function evidenceView(result: EvidenceResult): HTMLElement {
  if ("denied" in result)
    return el(
      "p",
      { class: "muted" },
      result.denied === "forbidden" ? "Evidence needs the analyst role." : "Invalid token.",
    );
  return evidenceList(result.items);
}

function evidenceList(items: Evidence[]): HTMLElement {
  if (items.length === 0) return el("p", { class: "muted" }, "No evidence available for this theme.");
  return el(
    "ol",
    { class: "evidence" },
    ...items.map((item) =>
      el(
        "li",
        {},
        el("blockquote", { lang: item.lang ?? "" }, item.text),
        el(
          "div",
          { class: "meta" },
          el("span", {}, item.source),
          item.lang ? el("span", {}, languageName(item.lang)) : null,
          item.rating !== null ? el("span", {}, "★".repeat(Math.round(item.rating))) : null,
          el("span", {}, new Date(item.created_at).toLocaleDateString()),
          item.url ? original(item.url) : null,
          el("code", {}, item.id),
        ),
      ),
    ),
  );
}

const REFUSALS: Record<Refusal, string> = {
  unauthorized: "Invalid token",
  forbidden: "Not allowed: this token has no access to Studio",
};

const BADGES: Record<Mode, string> = { demo: "Demo data", export: "Snapshot", live: "Live" };

function tokenForm(error: string | null): void {
  clear(app);
  const input = el("input", { type: "password", placeholder: "OBSEI_API_TOKEN", "aria-label": "API token" });
  const form = el(
    "form",
    { class: "panel token" },
    el("h2", {}, "Connect to obsei"),
    el("p", { class: "muted" }, "Enter the API token of this obsei server. It is kept for this tab only."),
    error ? el("p", { class: "error", role: "alert" }, error) : null,
    input,
    el("button", { type: "submit" }, "Open Studio"),
  );
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    DataSource.saveToken(input.value.trim());
    void start();
  });
  app.append(form);
}

function render(data: DataSource): void {
  const { overview, themes, graph } = data.snapshot;
  clear(app);
  const negative = overview.by_sentiment.find((b) => b.key === "negative")?.count ?? 0;
  const header = el(
    "header",
    {},
    el("h1", {}, el("img", { src: "logo.png", alt: "", width: "32", height: "32" }), "obsei ", el("span", {}, "Studio")),
    el("span", { class: `badge ${data.mode}` }, BADGES[data.mode]),
    el(
      "span",
      { class: "muted" },
      `Updated ${new Date(overview.generated_at).toLocaleString()} · groups under ${overview.k_anonymity} records hidden`,
    ),
  );
  const kpis = el(
    "section",
    { class: "kpis" },
    ...[
      ["Feedback", number.format(overview.total)],
      ["Themes", number.format(themes.length)],
      ["Negative", overview.total && overview.by_sentiment.length ? `${Math.round((100 * negative) / overview.total)}%` : "–"],
      ["Languages", number.format(overview.by_lang.length)],
    ].map(([label, value]) => el("div", { class: "kpi" }, el("span", {}, label!), el("strong", {}, value!))),
  );
  const evidenceHost = el("div", {});
  const evidenceTitle = el("h2", {}, "Evidence");
  const graphHost = el("div", { class: "graph" });
  const themeList = el("ul", { class: "themes" });
  let highlight: (id: string | null) => void = () => undefined;
  const select = async (id: string) => {
    const theme = themes.find((t) => t.id === id);
    for (const item of themeList.querySelectorAll("li")) item.classList.toggle("selected", item.dataset.id === id);
    highlight(id);
    evidenceTitle.textContent = theme?.label ? `Evidence: ${theme.label}` : "Evidence";
    clear(evidenceHost);
    evidenceHost.append(el("p", { class: "muted" }, "Loading…"));
    const result = await data.evidence(id);
    clear(evidenceHost);
    evidenceHost.append(evidenceView(result));
  };
  for (const theme of themes) {
    const item = el(
      "li",
      { tabindex: "0" },
      el("div", { class: "theme-head" }, el("strong", {}, theme.label ?? theme.id), trend(theme)),
      theme.description ? el("p", {}, theme.description) : null,
      el(
        "div",
        { class: "theme-meta" },
        el("span", {}, `${number.format(theme.size)} records`),
        theme.avg_rating !== null
          ? el("span", {}, `★ ${theme.avg_rating.toFixed(1)}`)
          : el("span", { class: "muted", title: "No rating, or too few people to show one" }, "★ –"),
        chips(theme.sources),
        chips(theme.languages, languageName),
      ),
    );
    item.dataset.id = theme.id;
    item.addEventListener("click", () => void select(theme.id));
    item.addEventListener("keydown", (e) => {
      if (e.key === "Enter") void select(theme.id);
    });
    themeList.append(item);
  }
  const legend = el(
    "div",
    { class: "legend" },
    ...Object.entries(KIND_LABELS).map(([kind, label]) => el("span", { class: `kind-${kind}` }, label)),
  );
  const ask =
    data.mode === "live" && data.canReadEvidence
      ? (() => {
          const input = el("input", { type: "text", placeholder: "Ask about your feedback, in any language" });
          const answer = el("div", { class: "answer" });
          const form = el("form", { class: "panel ask" }, el("h2", {}, "Ask"), input, el("button", { type: "submit" }, "Ask"), answer);
          form.addEventListener("submit", async (event) => {
            event.preventDefault();
            answer.textContent = "Thinking…";
            answer.textContent = await data.ask(input.value);
          });
          return form;
        })()
      : null;
  app.append(
    ...[
    header,
    kpis,
    el(
      "div",
      { class: "grid" },
      el("section", { class: "panel" }, el("h2", {}, "Themes"), themes.length ? themeList : el("p", { class: "muted" }, "No themes yet. Run obsei themes.")),
      el("section", { class: "panel" }, el("h2", {}, "Knowledge graph"), legend, graphHost),
    ),
    ask,
    el("section", { class: "panel" }, evidenceTitle, evidenceHost),
    el(
      "div",
      { class: "grid three" },
      bars("Sources", overview.by_source),
      bars("Languages", overview.by_lang, languageName),
      bars("Intents", overview.by_intent),
    ),
    bars("Volume by week", overview.by_week),
    overview.by_route?.length ? bars("Routes", overview.by_route) : null,
    el("footer", { class: "muted" }, `obsei ${overview.version} · text is redacted at ingest; authors are never shown`),
    ].filter((node): node is HTMLElement => node !== null),
  );
  const nodes = graph.nodes.map((n) => (n.kind === "lang" ? { ...n, label: languageName(n.label) } : n));
  highlight = renderGraph(graphHost, nodes, graph.edges, (id) => void select(id));
  const first = themes[0];
  if (first) void select(first.id);
}

async function start(): Promise<void> {
  try {
    const data = await DataSource.open();
    if (data instanceof DataSource) render(data);
    else tokenForm(data.hadToken || data.denied === "forbidden" ? REFUSALS[data.denied] : null);
  } catch (error) {
    clear(app);
    app.append(el("p", { class: "panel" }, `Could not load data: ${String(error)}`));
  }
}

void start();
