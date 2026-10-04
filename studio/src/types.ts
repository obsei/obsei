export interface Bucket {
  key: string;
  count: number;
  avg_rating: number | null;
}

export interface Overview {
  generated_at: string;
  version: string;
  k_anonymity: number;
  total: number;
  by_source: Bucket[];
  by_sentiment: Bucket[];
  by_intent: Bucket[];
  by_lang: Bucket[];
  by_week: Bucket[];
}

export interface Theme {
  id: string;
  label: string | null;
  description: string | null;
  size: number;
  duplicates: number;
  avg_rating: number | null;
  last_7_days: number;
  previous_7_days: number;
  sources: Record<string, number>;
  languages: Record<string, number>;
  intents: Record<string, number>;
}

export type NodeKind = "theme" | "source" | "lang" | "intent" | "sentiment";

export interface GraphNode {
  id: string;
  kind: NodeKind;
  label: string;
  weight: number;
}

export interface GraphEdge {
  source: string;
  target: string;
  weight: number;
}

export interface Evidence {
  id: string;
  source: string;
  instance: string;
  url: string | null;
  created_at: string;
  rating: number | null;
  lang: string | null;
  text: string;
  labels: Record<string, string>;
}

export type Role = "viewer" | "analyst" | "admin";

export interface Snapshot {
  demo?: boolean;
  role?: Role | null;
  overview: Overview;
  themes: Theme[];
  graph: { nodes: GraphNode[]; edges: GraphEdge[] };
  evidence: Record<string, Evidence[]>;
}
