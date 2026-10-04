import { isRising, sparkline, weekColumns } from "./charts";
import { DataSource, type EvidenceResult, type Mode, type Refusal } from "./data";
import { clear, el, languageName, number } from "./dom";
import { type GraphControl, KIND_LABELS, renderGraph } from "./graph";
import { askExamples, decisionsPanel, intro, labelChips, privacyPanel, redacted, redactionPanel } from "./panels";
import type { Bucket, Evidence, Snapshot, Theme } from "./types";

const app = document.getElementById("app")!;
const EVIDENCE_SHOWN = 6;
const WEBSITE = "https://obsei.com";

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
          ...buckets.slice(0, 12).map((b) =>
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
      .slice(0, 6)
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

function evidenceItem(item: Evidence): HTMLElement {
  const node = el(
    "li",
    {},
    el("blockquote", { lang: item.lang ?? "" }, ...redacted(item.text)),
    labelChips(item),
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
  );
  node.dataset.id = item.id;
  return node;
}

function evidenceList(items: Evidence[]): HTMLElement {
  if (items.length === 0) return el("p", { class: "muted" }, "No evidence available for this theme.");
  const list = el("ol", { class: "evidence" }, ...items.slice(0, EVIDENCE_SHOWN).map(evidenceItem));
  if (items.length <= EVIDENCE_SHOWN) return list;
  const more = el("button", { type: "button", class: "more" }, `Show all ${items.length}`);
  more.addEventListener("click", () => {
    list.append(...items.slice(EVIDENCE_SHOWN).map(evidenceItem));
    more.remove();
  });
  return el("div", {}, list, more);
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

function brand(): HTMLElement {
  return el(
    "h1",
    {},
    el(
      "a",
      { href: WEBSITE, rel: "noopener", class: "brand", "aria-label": "obsei website" },
      el("img", { src: "logo.png", alt: "", width: "32", height: "32" }),
      "obsei ",
      el("span", {}, "Studio"),
    ),
  );
}

function demoSummary(snapshot: Snapshot): string {
  const { overview, embedder, showcase } = snapshot;
  const fields = ["sentiment", "intent", ...Object.keys(overview.decisions?.fields ?? {})].join(", ");
  const labelled = showcase?.labelled_by ? ` Labels (${fields}) were produced by ${showcase.labelled_by}.` : "";
  const grouped = embedder?.startsWith("hashing")
    ? "This build used the offline hashing embedder, so each language forms its own theme; built with the multilingual model, the same issue in any language becomes one theme."
    : "The multilingual model groups the same issue in different languages into one theme.";
  return (
    `Synthetic customer feedback in ${overview.by_lang.length} languages from ${overview.by_source.map((b) => b.key).join(", ")}. ` +
    `Personal data was redacted at ingest. ${grouped} ` +
    `Every group shown comes from at least ${overview.k_anonymity} people (k-anonymity).${labelled}`
  );
}

function render(data: DataSource): void {
  const snapshot = data.snapshot;
  const { overview, themes, graph, privacy } = snapshot;
  const showcase = data.mode === "demo" ? snapshot.showcase : null;
  clear(app);
  const negative = overview.by_sentiment.find((b) => b.key === "negative")?.count ?? 0;
  const header = el(
    "header",
    {},
    brand(),
    el("span", { class: `badge ${data.mode}` }, BADGES[data.mode]),
    el(
      "span",
      { class: "muted" },
      `Updated ${new Date(overview.generated_at).toLocaleString()} · groups under ${overview.k_anonymity} people hidden`,
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
  const evidencePanel = el("section", { class: "panel evidence-panel" }, evidenceTitle, evidenceHost);
  const graphHost = el("div", { class: "graph" });
  const themeList = el("ul", { class: "themes" });
  let control: GraphControl = { select: () => undefined, pin: () => undefined };
  const select = async (id: string, focus: string | null = null) => {
    const theme = themes.find((t) => t.id === id);
    for (const item of themeList.querySelectorAll("li")) item.classList.toggle("selected", item.dataset.id === id);
    control.select(id);
    evidenceTitle.textContent = theme?.label ? `Evidence: ${theme.label}` : "Evidence";
    clear(evidenceHost);
    evidenceHost.append(el("p", { class: "muted" }, "Loading…"));
    const result = await data.evidence(id);
    clear(evidenceHost);
    evidenceHost.append(evidenceView(result));
    if (focus === null) return;
    let item = evidenceHost.querySelector<HTMLElement>(`li[data-id="${CSS.escape(focus)}"]`);
    if (!item) {
      evidenceHost.querySelector<HTMLButtonElement>("button.more")?.click();
      item = evidenceHost.querySelector<HTMLElement>(`li[data-id="${CSS.escape(focus)}"]`);
    }
    if (item) {
      item.classList.add("cited");
      item.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  };
  const cite = (recordId: string) => {
    const owner = Object.entries(snapshot.evidence).find(([, items]) => items.some((e) => e.id === recordId));
    if (owner) void select(owner[0], recordId);
  };
  const rising = themes.filter((t) => isRising(t));
  for (const theme of themes) {
    const up = rising.includes(theme);
    const item = el(
      "li",
      { tabindex: "0", class: up ? "rising" : "" },
      el(
        "div",
        { class: "theme-head" },
        el("strong", {}, theme.label ?? theme.id),
        up ? el("span", { class: "rising-badge" }, "Rising") : null,
        trend(theme),
      ),
      theme.description ? el("p", {}, theme.description) : null,
      el(
        "div",
        { class: "theme-body" },
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
        theme.weekly && theme.weekly.length > 1 ? sparkline(theme.weekly, up) : null,
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
          const input = el("input", { type: "text", placeholder: "Ask about your feedback, in any language", "aria-label": "Question" });
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
  const themesPanel = el(
    "section",
    { class: "panel", id: "themes" },
    el("h2", {}, "Themes"),
    themes.length ? themeList : el("p", { class: "muted" }, "No themes yet. Run obsei themes."),
  );
  const graphPanel = el(
    "section",
    { class: "panel" },
    el("h2", {}, "Knowledge graph"),
    legend,
    graphHost,
    el("p", { class: "muted hint" }, "Click a theme to read its evidence; click any other node to keep its links highlighted."),
  );
  const firstRedacted = Object.entries(snapshot.evidence).find(([, items]) => items.some((e) => /<[A-Z][A-Z0-9_]*>/.test(e.text)));
  const languages = graph.nodes.filter((n) => n.kind === "lang").sort((a, b) => b.weight - a.weight);
  const topLanguage = languages.find((n) => n.label !== "en") ?? languages[0];
  const introPanel =
    data.mode === "demo"
      ? intro(demoSummary(snapshot), [
          ...(rising[0]
            ? [{
                text: `“${rising[0].label ?? "A theme"}” is rising after an app update.`,
                action: "Open the rising theme",
                run: () => {
                  void select(rising[0]!.id);
                  themesPanel.scrollIntoView({ behavior: "smooth", block: "start" });
                },
              }]
            : []),
          ...(topLanguage
            ? [{
                text: `See which themes customers write about in ${languageName(topLanguage.label)}.`,
                action: `Highlight ${languageName(topLanguage.label)} in the graph`,
                run: () => {
                  control.pin(topLanguage.id);
                  graphPanel.scrollIntoView({ behavior: "smooth", block: "start" });
                },
              }]
            : []),
          ...(firstRedacted
            ? [{
                text: "Read evidence with personal data replaced by placeholders.",
                action: "Read redacted evidence",
                run: () => {
                  const target = firstRedacted[1].find((e) => /<[A-Z][A-Z0-9_]*>/.test(e.text));
                  void select(firstRedacted[0], target?.id ?? null);
                  evidencePanel.scrollIntoView({ behavior: "smooth", block: "start" });
                },
              }]
            : []),
        ])
      : null;
  const privacyRow = privacy
    ? showcase && showcase.redactions.length
      ? el("div", { class: "grid even" }, privacyPanel(privacy), redactionPanel(showcase.redactions))
      : privacyPanel(privacy)
    : null;
  app.append(
    ...[
      header,
      introPanel,
      kpis,
      el("div", { class: "grid" }, themesPanel, graphPanel),
      ask,
      evidencePanel,
      showcase && showcase.answers.length ? askExamples(showcase.answers, cite) : null,
      privacyRow,
      overview.decisions && Object.keys(overview.decisions.fields).length ? decisionsPanel(overview.decisions) : null,
      weekColumns(overview.by_week),
      el(
        "div",
        { class: "grid three" },
        bars("Sources", overview.by_source),
        bars("Languages", overview.by_lang, languageName),
        bars("Intents", overview.by_intent),
      ),
      el(
        "footer",
        { class: "muted" },
        `obsei ${overview.version} · text is redacted at ingest; authors are never shown · `,
        el("a", { href: WEBSITE, rel: "noopener" }, "obsei.com"),
      ),
    ].filter((node): node is HTMLElement => node !== null),
  );
  const nodes = graph.nodes.map((n) => (n.kind === "lang" ? { ...n, label: languageName(n.label) } : n));
  control = renderGraph(graphHost, nodes, graph.edges, (id) => void select(id));
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
