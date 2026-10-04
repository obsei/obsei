import rss from "@astrojs/rss";
import type { APIRoute } from "astro";
import { SITE } from "../consts";
import { getPosts, ogUrl, postUrl } from "../utils";

export const GET: APIRoute = async (context) => {
  const posts = await getPosts();
  const site = context.site!;
  return rss({
    title: SITE.name,
    description: SITE.description,
    site,
    trailingSlash: true,
    xmlns: { dc: "http://purl.org/dc/elements/1.1/", media: "http://search.yahoo.com/mrss/" },
    items: posts.map((post) => ({
      title: post.data.title,
      description: post.data.description,
      pubDate: post.data.pubDate,
      link: postUrl(post),
      categories: post.data.tags,
      customData: `<dc:creator>${post.data.author}</dc:creator><media:content url="${new URL(ogUrl(post), site).href}" medium="image" type="image/png" width="1200" height="630"/>`,
    })),
    customData: `<language>en</language><image><url>${SITE.logo}</url><title>${SITE.name}</title><link>${SITE.url}/</link></image>`,
  });
};
