import { defineCollection } from "astro:content";
import { glob } from "astro/loaders";
import { z } from "astro/zod";

const posts = defineCollection({
  loader: glob({ base: "./src/content/posts", pattern: "*.{md,mdx}" }),
  schema: ({ image }) =>
    z.object({
      title: z.string().max(100),
      description: z.string().max(300),
      pubDate: z.coerce.date(),
      updatedDate: z.coerce.date().optional(),
      author: z.string().default("Lalit Pagaria"),
      tags: z.array(z.string()).default([]),
      cover: image(),
      coverAlt: z.string(),
      draft: z.boolean().default(false),
    }),
});

export const collections = { posts };
