import { el, number, svg } from "./dom";
import type { Bucket, Theme } from "./types";

const SPARK_W = 96;
const SPARK_H = 28;
const SPARK_PAD = 3;

const RISING_MIN = 3;

/** A theme is rising when its last seven days at least doubled the seven days before. */
export function isRising(theme: Theme): boolean {
  return theme.last_7_days >= RISING_MIN && theme.last_7_days >= 2 * Math.max(1, theme.previous_7_days);
}

export function sparkline(values: number[], rising: boolean): SVGSVGElement {
  const max = Math.max(1, ...values);
  const step = values.length > 1 ? (SPARK_W - 2 * SPARK_PAD) / (values.length - 1) : 0;
  const points = values.map((v, i) => [SPARK_PAD + i * step, SPARK_H - SPARK_PAD - (v / max) * (SPARK_H - 2 * SPARK_PAD)] as const);
  const line = points.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)} ${y.toFixed(1)}`).join(" ");
  const first = points[0] ?? [SPARK_PAD, SPARK_H - SPARK_PAD];
  const last = points[points.length - 1] ?? first;
  const root = svg("svg", {
    viewBox: `0 0 ${SPARK_W} ${SPARK_H}`,
    width: SPARK_W,
    height: SPARK_H,
    class: rising ? "spark rising" : "spark",
    role: "img",
    "aria-label": `Records per week, last ${values.length} weeks: ${values.join(", ")}`,
  });
  const title = svg("title");
  title.textContent = `Records per week, oldest first: ${values.join(", ")}`;
  root.append(
    title,
    svg("path", { d: `${line} L${last[0].toFixed(1)} ${SPARK_H - SPARK_PAD} L${first[0].toFixed(1)} ${SPARK_H - SPARK_PAD} Z`, class: "spark-area" }),
    svg("path", { d: line, class: "spark-line" }),
    svg("circle", { cx: last[0].toFixed(1), cy: last[1].toFixed(1), r: 2.5, class: "spark-dot" }),
  );
  return root;
}

function weekLabel(key: string, month: "short" | "numeric" = "short"): string {
  const date = new Date(`${key}T00:00:00Z`);
  return Number.isNaN(date.getTime())
    ? key
    : date.toLocaleDateString(undefined, { month, day: "numeric", timeZone: "UTC" });
}

/** Records per calendar week as columns; the busiest week is highlighted and labelled. */
export function weekColumns(buckets: Bucket[]): HTMLElement {
  const section = el("section", { class: "panel volume" }, el("h2", {}, "Volume by week"));
  if (buckets.length === 0) {
    section.append(el("p", { class: "muted" }, "No feedback yet."));
    return section;
  }
  const max = Math.max(1, ...buckets.map((b) => b.count));
  const peak = buckets.findIndex((b) => b.count === max);
  const average = buckets.reduce((sum, b) => sum + b.count, 0) / buckets.length;
  const peakBucket = buckets[peak]!;
  section.append(
    el(
      "p",
      { class: "muted" },
      `Busiest week: ${weekLabel(peakBucket.key)}, ${number.format(peakBucket.count)} records`,
      average > 0 ? ` (${(peakBucket.count / average).toFixed(1)}× the weekly average)` : null,
    ),
  );
  const list = el("ol", { class: "columns", "aria-label": "Records per week" });
  buckets.forEach((b, i) => {
    const column = el("span", { class: "col" });
    column.style.setProperty("--h", `${Math.max(2, (100 * b.count) / max)}%`);
    const labelled = i === peak || i === buckets.length - 1;
    const item = el(
      "li",
      { class: i === peak ? "peak" : "", title: `Week of ${weekLabel(b.key)}: ${number.format(b.count)} records` },
      el("span", { class: labelled ? "col-value" : "col-value quiet" }, number.format(b.count)),
      el("span", { class: "col-track" }, column),
      el("span", { class: "col-label" }, weekLabel(b.key)),
      el("span", { class: "col-label short" }, weekLabel(b.key, "numeric")),
    );
    list.append(item);
  });
  section.append(list);
  return section;
}
