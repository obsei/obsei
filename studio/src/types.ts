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
  weekly?: number[];
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

export type EgressMode = "air_gapped" | "private" | "hybrid";

export interface Privacy {
  k_anonymity: number;
  hidden_themes: number;
  hidden_groups: number;
  placeholders: Record<string, number>;
  redacted_records: number;
  pseudonymised_authors: number;
  egress?: EgressMode | null;
}

export interface RedactionExample {
  source: string;
  lang: string;
  raw: string;
  stored: string;
}

export interface AskExample {
  question: string;
  answer: string;
  citations: string[];
}

export interface Showcase {
  redactions: RedactionExample[];
  answers: AskExample[];
}

export interface Snapshot {
  demo?: boolean;
  embedder?: string | null;
  role?: Role | null;
  overview: Overview;
  privacy?: Privacy;
  themes: Theme[];
  graph: { nodes: GraphNode[]; edges: GraphEdge[] };
  evidence: Record<string, Evidence[]>;
  showcase?: Showcase | null;
}
