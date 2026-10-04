import starlight from "@astrojs/starlight";
import { defineConfig } from "astro/config";

export default defineConfig({
  site: "https://docs.obsei.com",
  integrations: [
    starlight({
      title: "obsei",
      logo: { src: "./src/assets/logo.png" },
      customCss: ["./src/styles/brand.css"],
      favicon: "/logo.png",
      description: "Privacy-first, self-hosted, AI-native Voice of Customer.",
      head: [{ tag: "meta", attrs: { name: "theme-color", content: "#238a91" } }],
      social: [{ icon: "github", label: "GitHub", href: "https://github.com/obsei/obsei" }],
      editLink: { baseUrl: "https://github.com/obsei/obsei/edit/master/docs/" },
      sidebar: [
        { label: "Start", items: ["quickstart", "configuration"] },
        { label: "Guides", items: [{ autogenerate: { directory: "guides" } }] },
        { label: "Privacy", items: [{ autogenerate: { directory: "privacy" } }] },
        { label: "Reference", items: [{ autogenerate: { directory: "reference" } }] },
      ],
    }),
  ],
});
