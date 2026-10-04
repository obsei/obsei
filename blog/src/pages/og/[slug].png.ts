import fs from "node:fs/promises";
import path from "node:path";
import type { APIRoute, GetStaticPaths } from "astro";
import { renderPng } from "../../og";
import { getPosts, type Post } from "../../utils";

export const getStaticPaths = (async () => {
  const posts = await getPosts();
  return [
    { params: { slug: "default" }, props: { post: undefined } },
    ...posts.map((post) => ({ params: { slug: post.id }, props: { post } })),
  ];
}) satisfies GetStaticPaths;

/** The cover file named in the post's frontmatter (SVG, PNG, JPEG or WebP), or the default card. */
async function coverPath(post: Post | undefined): Promise<string> {
  if (post?.filePath) {
    const source = await fs.readFile(post.filePath, "utf8");
    const cover = source.match(/^cover:\s*["']?([^"'\n]+?)["']?\s*$/m)?.[1];
    if (cover) return path.resolve(path.dirname(post.filePath), cover);
  }
  return path.resolve("src/assets/og-default.svg");
}

export const GET: APIRoute = async ({ props }) => {
  const png = await renderPng(await fs.readFile(await coverPath((props as { post?: Post }).post)));
  return new Response(new Uint8Array(png), { headers: { "Content-Type": "image/png" } });
};
