import starlight from "@astrojs/starlight";
import { defineConfig } from "astro/config";

export default defineConfig({
  site: "https://docs.obsei.com",
  integrations: [
    starlight({
      title: "obsei",
      logo: { src: "./public/logo.png" },
      favicon: "/logo.png",
      description: "Privacy-first, self-hosted, AI-native Voice of Customer.",
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
