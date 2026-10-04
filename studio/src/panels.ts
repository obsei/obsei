import { el, languageName, number } from "./dom";
import type { AskExample, Decisions, EgressMode, Evidence, LabelCount, Privacy, RedactionExample } from "./types";

const PLACEHOLDER = /(<[A-Z][A-Z0-9_]*>)/;

const PLACEHOLDER_NAMES: Record<string, string> = {
  EMAIL: "Email",
  PHONE: "Phone",
  CARD: "Card number",
  IBAN: "IBAN",
  IN_AADHAAR: "Aadhaar",
  BR_CPF: "CPF",
  PERSON: "Name",
  IPV4: "IP address",
  IPV6: "IP address",
};

const EGRESS: Record<EgressMode, string> = {
  air_gapped: "Air-gapped: no outbound network calls",
  private: "Private: only allowlisted hosts",
  hybrid: "Hybrid: external models allowed",
};

/** Text with redaction placeholders marked, so readers see what was removed at ingest. */
export function redacted(text: string): Node[] {
  return text
    .split(PLACEHOLDER)
    .filter((part) => part !== "")
    .map((part) => (PLACEHOLDER.test(part) ? el("mark", { class: "pii" }, part) : document.createTextNode(part)));
}

function stat(value: string, label: string): HTMLElement {
  return el("div", { class: "stat" }, el("strong", {}, value), el("span", {}, label));
}

export function privacyPanel(privacy: Privacy): HTMLElement {
  const placeholders = Object.entries(privacy.placeholders);
  const hidden = privacy.hidden_themes + privacy.hidden_groups;
  return el(
    "section",
    { class: "panel privacy", "aria-labelledby": "privacy-title" },
    el("h2", { id: "privacy-title" }, "Privacy"),
    el(
      "div",
      { class: "stats" },
      stat(number.format(privacy.redacted_records), "records had personal data redacted at ingest"),
      stat(`k = ${privacy.k_anonymity}`, `groups from fewer people are hidden (${number.format(hidden)} now)`),
      stat(number.format(privacy.pseudonymised_authors), "authors, pseudonymised; never shown"),
      privacy.egress ? stat(privacy.egress.replace("_", "-"), EGRESS[privacy.egress]) : null,
    ),
    placeholders.length
      ? el(
          "ul",
          { class: "placeholders", "aria-label": "Placeholders in stored text" },
          ...placeholders.map(([label, count]) =>
            el(
              "li",
              {},
              el("mark", { class: "pii" }, `<${label}>`),
              el("span", {}, PLACEHOLDER_NAMES[label] ?? label.replaceAll("_", " ")),
              el("strong", {}, number.format(count)),
            ),
          ),
        )
      : el("p", { class: "muted" }, "No placeholders in stored text."),
    el(
      "p",
      { class: "muted" },
      `Hidden by k-anonymity: ${number.format(privacy.hidden_themes)} theme${privacy.hidden_themes === 1 ? "" : "s"} and ${number.format(privacy.hidden_groups)} source, language or label group${privacy.hidden_groups === 1 ? "" : "s"}.`,
    ),
  );
}

export function redactionPanel(examples: RedactionExample[]): HTMLElement {
  return el(
    "section",
    { class: "panel before-after", "aria-labelledby": "before-after-title" },
    el("h2", { id: "before-after-title" }, "Before and after redaction"),
    el(
      "p",
      { class: "muted" },
      "Synthetic examples. The raw text exists only in the demo builder; obsei stores and shows only the redacted text.",
    ),
    el(
      "ul",
      { class: "cards" },
      ...examples.map((ex) =>
        el(
          "li",
          {},
          el("span", { class: "card-meta" }, `${ex.source} · ${languageName(ex.lang)}`),
          el("span", { class: "card-tag" }, "Received"),
          el("blockquote", { lang: ex.lang, class: "raw" }, ex.raw),
          el("span", { class: "card-tag" }, "Stored"),
          el("blockquote", { lang: ex.lang }, ...redacted(ex.stored)),
        ),
      ),
    ),
  );
}

export function askExamples(answers: AskExample[], onCite: (id: string) => void): HTMLElement {
  return el(
    "section",
    { class: "panel ask-examples", "aria-labelledby": "ask-examples-title" },
    el("h2", { id: "ask-examples-title" }, "Ask your data"),
    el(
      "p",
      { class: "muted" },
      "Example answers recorded from this dataset; in your deployment Ask uses your own model. Agents get the same answers via MCP.",
    ),
    ...answers.map((a, i) =>
      el(
        "details",
        i === 0 ? { open: "" } : {},
        el("summary", {}, a.question),
        el("p", {}, a.answer),
        el(
          "div",
          { class: "citations" },
          el("span", { class: "muted" }, "Sources:"),
          ...a.citations.map((id) => {
            const button = el("button", { type: "button", class: "cite", title: "Show this record in Evidence" }, id);
            button.addEventListener("click", () => onCite(id));
            return button;
          }),
        ),
      ),
    ),
  );
}

export interface Hint {
  text: string;
  action: string;
  run: () => void;
}

export function intro(summary: string, hints: Hint[]): HTMLElement {
  return el(
    "section",
    { class: "panel intro", "aria-labelledby": "intro-title" },
    el("h2", { id: "intro-title" }, "What you are looking at"),
    el("p", {}, summary),
    el(
      "ol",
      { class: "hints" },
      ...hints.map((hint) => {
        const button = el("button", { type: "button" }, hint.action);
        button.addEventListener("click", hint.run);
        return el("li", {}, el("span", {}, hint.text), button);
      }),
    ),
  );
}

const percent = new Intl.NumberFormat(undefined, { style: "percent", maximumFractionDigits: 0 });

function answerText(value: string | boolean): string {
  return value === true || value === "true" ? "yes" : value === false || value === "false" ? "no" : value;
}

/** Labels of one record with the model's confidence in each, for the evidence list. */
export function labelChips(item: Evidence): HTMLElement | null {
  const answers: Array<[string, string | boolean]> = [
    ...(["intent", "sentiment"] as const).flatMap((k): Array<[string, string]> => (item.labels[k] ? [[k, item.labels[k]!]] : [])),
    ...Object.entries(item.fields ?? {}),
  ];
  if (answers.length === 0) return null;
  const confidences = item.confidences ?? {};
  return el(
    "span",
    { class: "labels" },
    ...answers.map(([name, value]) => {
      const confidence = confidences[name];
      return el(
        "span",
        { class: "label", title: confidence === undefined ? name : `${name}: model confidence ${percent.format(confidence)}` },
        `${name}: ${answerText(value).replaceAll("_", " ")}`,
        confidence === undefined ? null : el("small", {}, ` ${percent.format(confidence)}`),
      );
    }),
    item.review ? el("span", { class: "label review", title: "An answer was below its confidence cutoff" }, "needs review") : null,
  );
}

function ordered(counts: LabelCount[]): LabelCount[] {
  return counts.some((c) => c.score !== null)
    ? [...counts].sort((a, b) => (a.score ?? 0) - (b.score ?? 0))
    : counts;
}

export function decisionsPanel(decisions: Decisions): HTMLElement {
  const fields = Object.entries(decisions.fields);
  return el(
    "section",
    { class: "panel decisions", "aria-labelledby": "decisions-title" },
    el("h2", { id: "decisions-title" }, "Decisions"),
    el(
      "p",
      { class: "muted" },
      `${number.format(decisions.labelled)} records labelled${decisions.model ? ` by ${decisions.model}` : ""}`,
      decisions.labelled
        ? ` · ${percent.format(decisions.review / decisions.labelled)} marked for review (an answer below its confidence cutoff)`
        : null,
    ),
    el(
      "div",
      { class: "decision-fields" },
      ...fields.map(([name, counts]) => {
        const max = Math.max(1, ...counts.map((c) => c.count));
        return el(
          "div",
          {},
          el("h3", {}, name.replaceAll("_", " ")),
          el(
            "ul",
            { class: "bars" },
            ...ordered(counts).map((c) => {
              const fill = el("span", { class: "bar" });
              fill.style.setProperty("--w", `${(100 * c.count) / max}%`);
              return el(
                "li",
                {},
                el("span", { class: "bar-label" }, answerText(c.value)),
                fill,
                el("span", { class: "bar-value" }, number.format(c.count)),
              );
            }),
          ),
        );
      }),
    ),
  );
}
