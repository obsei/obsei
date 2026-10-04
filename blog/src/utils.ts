import { getCollection, type CollectionEntry } from "astro:content";

export type Post = CollectionEntry<"posts">;

export async function getPosts(): Promise<Post[]> {
  const posts = await getCollection("posts", ({ data }) => import.meta.env.DEV || !data.draft);
  return posts.sort((a, b) => b.data.pubDate.valueOf() - a.data.pubDate.valueOf());
}

export const postUrl = (post: Post) => `/${post.id}/`;
export const ogUrl = (post: Post) => `/og/${post.id}.png`;

export function slugifyTag(tag: string): string {
  return tag.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}

export const tagUrl = (tag: string) => `/tags/${slugifyTag(tag)}/`;

export function tagLabel(tag: string): string {
  return tag.replace(/-/g, " ");
}

export function formatDate(date: Date): string {
  return date.toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric", timeZone: "UTC" });
}

export function readingMinutes(body: string | undefined): number {
  const text = (body ?? "")
    .replace(/^---[\s\S]*?---/, "")
    .replace(/^import .*$/gm, "")
    .replace(/<[^>]+>/g, " ");
  const words = text.split(/\s+/).filter(Boolean).length;
  return Math.max(1, Math.round(words / 220));
}

/** JSON for a <script type="application/ld+json"> block, safe against "</script>". */
export function jsonLd(data: unknown): string {
  return JSON.stringify(data).replace(/</g, "\\u003c");
}
