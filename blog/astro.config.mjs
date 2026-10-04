import "./og-fonts/fontconfig.mjs";
import mdx from "@astrojs/mdx";
import sitemap from "@astrojs/sitemap";
import { defineConfig } from "astro/config";

export default defineConfig({
  site: "https://blog.obsei.com",
  trailingSlash: "always",
  integrations: [mdx(), sitemap({ filter: (page) => !page.endsWith("/404/") })],
  build: {
    // Always emit CSS as files so the CSP can keep style-src 'self' (no inline <style>).
    inlineStylesheets: "never",
  },
  markdown: {
    // Prism highlights with classes; Shiki would add inline style attributes the CSP blocks.
    syntaxHighlight: "prism",
  },
  devToolbar: { enabled: false },
});
