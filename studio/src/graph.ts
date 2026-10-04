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

export function renderGraph(
  host: Element,
  nodes: GraphNode[],
  edges: GraphEdge[],
  onSelect: (themeId: string) => void,
): (themeId: string | null) => void {
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
  for (const p of points.values()) {
    const group = svg("g", { class: `node kind-${p.node.kind}`, tabindex: 0 });
    group.append(svg("circle", { cx: p.x, cy: p.y, r: p.r }));
    const text = svg("text", { x: p.x, y: p.y + p.r + 13, "text-anchor": "middle" });
    text.textContent = p.node.label.length > 28 ? `${p.node.label.slice(0, 27)}…` : p.node.label;
    const title = svg("title");
    title.textContent = `${KIND_LABELS[p.node.kind]}: ${p.node.label} (${p.node.weight})`;
    group.append(text, title);
    const focus = (on: boolean) => {
      const near = neighbours.get(p.node.id) ?? new Set<string>();
      root.classList.toggle("focused", on);
      for (const [id, g] of nodeEls) g.classList.toggle("near", on && (id === p.node.id || near.has(id)));
      for (const { el, edge } of edgeEls)
        el.classList.toggle("near", on && (edge.source === p.node.id || edge.target === p.node.id));
    };
    group.addEventListener("mouseenter", () => focus(true));
    group.addEventListener("mouseleave", () => focus(false));
    if (p.node.kind === "theme") {
      group.addEventListener("click", () => onSelect(p.node.id));
      group.addEventListener("keydown", (e) => {
        if (e.key === "Enter") onSelect(p.node.id);
      });
    }
    nodeLayer.append(group);
    nodeEls.set(p.node.id, group);
  }
  root.append(edgeLayer, nodeLayer);
  host.append(root);
  return (themeId) => {
    for (const [id, g] of nodeEls) g.classList.toggle("selected", id === themeId);
  };
}
