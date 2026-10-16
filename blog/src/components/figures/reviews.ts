export interface AppStats {
  name: string;
  reviews: number;
  first: string;
  last: string;
  days: number;
  stars: number[];
  critical: number;
  areas: Record<string, number>;
  belowCutoff: number;
  ageLockouts: Record<string, number>;
}

export interface AgreementRow {
  stars: string;
  counts: number[];
}

const day = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", timeZone: "UTC" });

export const formatDay = (iso: string) => day.format(new Date(iso));

export const pct = (n: number, of: number) => `${Math.round((100 * n) / of)}%`;
