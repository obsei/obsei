import { clear, svg } from "./dom";
import type { GraphEdge, GraphNode, NodeKind } from "./types";

interface Point {
  node: GraphNode;
  x: number;
  y: number;
  vx: number;
  vy: number;
  r: number;
}

export const KIND_LABELS: Record<NodeKind, string> = {
  theme: "Theme",
  source: "Source",
  lang: "Language",
  intent: "Intent",
  sentiment: "Sentiment",
};

const WIDTH = 900;
const HEIGHT = 600;

function layout(nodes: GraphNode[], edges: GraphEdge[]): Map<string, Point> {
  const max = Math.max(1, ...nodes.map((n) => n.weight));
  const points = new Map<string, Point>();
  nodes.forEach((node, i) => {
    const angle = (i / nodes.length) * Math.PI * 2;
    const ring = node.kind === "theme" ? 140 : 260;
    points.set(node.id, {
      node,
      x: WIDTH / 2 + Math.cos(angle) * ring,
      y: HEIGHT / 2 + Math.sin(angle) * ring,
      vx: 0,
      vy: 0,
      r: (node.kind === "theme" ? 10 : 6) + 18 * Math.sqrt(node.weight / max),
    });
  });
  const list = [...points.values()];
  for (let step = 0; step < 320; step++) {
    const cooling = 1 - step / 320;
    for (let i = 0; i < list.length; i++) {
      const a = list[i]!;
      for (let j = i + 1; j < list.length; j++) {
        const b = list[j]!;
        const dx = a.x - b.x;
        const dy = a.y - b.y;
        const dist = Math.max(1, Math.hypot(dx, dy));
        const push = (9000 + (a.r + b.r) * 120) / (dist * dist);
        a.vx += (dx / dist) * push;
        a.vy += (dy / dist) * push;
        b.vx -= (dx / dist) * push;
        b.vy -= (dy / dist) * push;
      }
    }
    for (const edge of edges) {
      const a = points.get(edge.source);
      const b = points.get(edge.target);
      if (!a || !b) continue;
      const dx = b.x - a.x;
      const dy = b.y - a.y;
      const dist = Math.max(1, Math.hypot(dx, dy));
      const pull = (dist - 150) * 0.004;
      a.vx += (dx / dist) * pull * dist * 0.05;
      a.vy += (dy / dist) * pull * dist * 0.05;
      b.vx -= (dx / dist) * pull * dist * 0.05;
      b.vy -= (dy / dist) * pull * dist * 0.05;
    }
    for (const p of list) {
      p.vx += (WIDTH / 2 - p.x) * 0.002;
      p.vy += (HEIGHT / 2 - p.y) * 0.002;
      p.x = Math.min(WIDTH - p.r - 4, Math.max(p.r + 4, p.x + p.vx * cooling));
      p.y = Math.min(HEIGHT - p.r - 4, Math.max(p.r + 4, p.y + p.vy * cooling));
      p.vx *= 0.6;
      p.vy *= 0.6;
    }
  }
  fit(list);
  return points;
}

function fit(list: Point[]): void {
  const pad = 40;
  const minX = Math.min(...list.map((p) => p.x - p.r));
  const maxX = Math.max(...list.map((p) => p.x + p.r));
  const minY = Math.min(...list.map((p) => p.y - p.r));
  const maxY = Math.max(...list.map((p) => p.y + p.r));
  const sx = (WIDTH - 2 * pad) / Math.max(1, maxX - minX);
  const sy = (HEIGHT - 2 * pad) / Math.max(1, maxY - minY);
  for (const p of list) {
    p.x = pad + (p.x - minX) * sx;
    p.y = pad + (p.y - minY) * sy;
  }
}

interface Box {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

interface Label {
  point: Point;
  text: SVGTextElement;
}

const LABEL_PX = 11;

function truncate(label: string, max: number): string {
  return label.length > max ? `${label.slice(0, max - 1)}…` : label;
}

function overlaps(a: Box, b: Box): boolean {
  return a.x1 < b.x2 && b.x1 < a.x2 && a.y1 < b.y2 && b.y1 < a.y2;
}

function hitsCircle(box: Box, p: Point): boolean {
  const cx = Math.max(box.x1, Math.min(p.x, box.x2));
  const cy = Math.max(box.y1, Math.min(p.y, box.y2));
  return Math.hypot(p.x - cx, p.y - cy) < p.r;
}

/** Places labels largest-first beside their node, hiding those that would collide. */
function placeLabels(labels: Label[], scale: number): void {
  const size = Math.min(32, Math.max(LABEL_PX, LABEL_PX / scale));
  const maxChars = scale < 0.6 ? 14 : 22;
  const placed: Box[] = [];
  const points = labels.map((l) => l.point);
  const order = [...labels].sort(
    (a, b) =>
      Number(b.point.node.kind === "theme") - Number(a.point.node.kind === "theme") ||
      b.point.node.weight - a.point.node.weight,
  );
  for (const { point: p, text } of order) {
    const content = truncate(p.node.label, maxChars);
    text.textContent = content;
    text.setAttribute("font-size", size.toFixed(1));
    text.removeAttribute("visibility");
    const w = text.getComputedTextLength() || content.length * size * 0.6;
    const h = size * 1.15;
    const gap = 3;
    const candidates: Box[] = [
      { x1: p.x - w / 2, y1: p.y + p.r + gap, x2: p.x + w / 2, y2: p.y + p.r + gap + h },
      { x1: p.x - w / 2, y1: p.y - p.r - gap - h, x2: p.x + w / 2, y2: p.y - p.r - gap },
      { x1: p.x + p.r + gap, y1: p.y - h / 2, x2: p.x + p.r + gap + w, y2: p.y + h / 2 },
      { x1: p.x - p.r - gap - w, y1: p.y - h / 2, x2: p.x - p.r - gap, y2: p.y + h / 2 },
    ];
    const box = candidates.find(
      (c) =>
        c.x1 >= 0 &&
        c.y1 >= 0 &&
        c.x2 <= WIDTH &&
        c.y2 <= HEIGHT &&
        !placed.some((other) => overlaps(c, other)) &&
        !points.some((other) => other !== p && hitsCircle(c, other)),
    );
    if (!box) {
      text.setAttribute("visibility", "hidden");
      continue;
    }
    placed.push(box);
    text.setAttribute("x", ((box.x1 + box.x2) / 2).toFixed(1));
    text.setAttribute("y", (box.y2 - size * 0.25).toFixed(1));
  }
}

export interface GraphControl {
  /** Marks the selected theme. */
  select: (themeId: string | null) => void;
  /** Keeps a node and its links highlighted until it is pinned again or another node is. */
  pin: (nodeId: string) => void;
}

export function renderGraph(
  host: Element,
  nodes: GraphNode[],
  edges: GraphEdge[],
  onSelect: (themeId: string) => void,
): GraphControl {
  clear(host);
  const root = svg("svg", { viewBox: `0 0 ${WIDTH} ${HEIGHT}`, role: "img" });
  root.setAttribute("aria-label", "Knowledge graph of themes, sources, languages and intents");
  const points = layout(nodes, edges);
  const maxEdge = Math.max(1, ...edges.map((e) => e.weight));
  const edgeLayer = svg("g", { class: "edges" });
  const nodeLayer = svg("g", { class: "nodes" });
  const neighbours = new Map<string, Set<string>>();
  const edgeEls: Array<{ el: SVGLineElement; edge: GraphEdge }> = [];
  for (const edge of edges) {
    const a = points.get(edge.source);
    const b = points.get(edge.target);
    if (!a || !b) continue;
    const line = svg("line", {
      x1: a.x,
      y1: a.y,
      x2: b.x,
      y2: b.y,
      "stroke-width": 0.5 + 4 * (edge.weight / maxEdge),
    });
    edgeLayer.append(line);
    edgeEls.push({ el: line, edge });
    for (const [x, y] of [
      [edge.source, edge.target],
      [edge.target, edge.source],
    ] as const) {
      if (!neighbours.has(x)) neighbours.set(x, new Set());
      neighbours.get(x)!.add(y);
    }
  }
  const nodeEls = new Map<string, SVGGElement>();
  const labels: Label[] = [];
  let pinned: string | null = null;
  const focus = (id: string | null) => {
    const near = id ? (neighbours.get(id) ?? new Set<string>()) : new Set<string>();
    root.classList.toggle("focused", id !== null);
    for (const [other, g] of nodeEls) {
      g.classList.toggle("near", id !== null && (other === id || near.has(other)));
      g.classList.toggle("pinned", other === pinned);
    }
    for (const { el, edge } of edgeEls) el.classList.toggle("near", id !== null && (edge.source === id || edge.target === id));
  };
  const pin = (id: string) => {
    pinned = pinned === id ? null : id;
    focus(pinned);
  };
  for (const p of points.values()) {
    const group = svg("g", {
      class: `node kind-${p.node.kind}`,
      tabindex: 0,
      role: "button",
      "aria-label": `${KIND_LABELS[p.node.kind]}: ${p.node.label}, ${p.node.weight} records`,
    });
    group.append(svg("circle", { cx: p.x, cy: p.y, r: p.r }));
    const text = svg("text", { "text-anchor": "middle" });
    labels.push({ point: p, text });
    const title = svg("title");
    title.textContent = `${KIND_LABELS[p.node.kind]}: ${p.node.label} (${p.node.weight})`;
    group.append(text, title);
    group.addEventListener("mouseenter", () => focus(p.node.id));
    group.addEventListener("mouseleave", () => focus(pinned));
    const activate = () => (p.node.kind === "theme" ? onSelect(p.node.id) : pin(p.node.id));
    group.addEventListener("click", activate);
    group.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        activate();
      }
    });
    nodeLayer.append(group);
    nodeEls.set(p.node.id, group);
  }
  root.append(edgeLayer, nodeLayer);
  host.append(root);
  let size = 0;
  const relabel = () => {
    const width = root.getBoundingClientRect().width;
    const scale = width > 0 ? width / WIDTH : 1;
    const next = Math.round(Math.max(LABEL_PX, LABEL_PX / scale));
    if (next === size) return;
    size = next;
    placeLabels(labels, scale);
  };
  relabel();
  new ResizeObserver(relabel).observe(root);
  return {
    select: (themeId) => {
      for (const [id, g] of nodeEls) g.classList.toggle("selected", id === themeId);
    },
    pin,
  };
}
