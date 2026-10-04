import starlight from "@astrojs/starlight";
import { defineConfig } from "astro/config";

export default defineConfig({
  site: "https://docs.obsei.com",
  integrations: [
    starlight({
      title: "obsei",
      logo: { light: "./src/assets/mark.svg", dark: "./src/assets/mark-dark.svg" },
      customCss: ["./src/styles/brand.css"],
      favicon: "/favicon.svg",
      description: "Privacy-first, self-hosted, AI-native Voice of Customer.",
      head: [
        { tag: "meta", attrs: { name: "theme-color", content: "#238a91" } },
        { tag: "link", attrs: { rel: "icon", href: "/logo.png", type: "image/png" } },
      ],
      social: [{ icon: "github", label: "GitHub", href: "https://github.com/obsei/obsei" }],
      editLink: { baseUrl: "https://github.com/obsei/obsei/edit/master/docs/" },
      sidebar: [
        { label: "Start", items: ["quickstart", "how-it-works", "configuration"] },
        { label: "Guides", items: [{ autogenerate: { directory: "guides" } }] },
        { label: "Privacy", items: [{ autogenerate: { directory: "privacy" } }] },
        { label: "Reference", items: [{ autogenerate: { directory: "reference" } }] },
      ],
    }),
  ],
});
