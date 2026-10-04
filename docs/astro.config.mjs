import starlight from "@astrojs/starlight";
import { defineConfig } from "astro/config";

const ogImage = "https://docs.obsei.com/og.png";
const softwareJsonLd = {
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  "@id": "https://obsei.com/#software",
  name: "obsei",
  url: "https://obsei.com/",
  description: "Privacy-first, self-hosted, AI-native Voice of Customer.",
  applicationCategory: "DeveloperApplication",
  operatingSystem: "Linux, macOS, Windows",
  license: "https://www.apache.org/licenses/LICENSE-2.0",
  offers: { "@type": "Offer", price: "0", priceCurrency: "USD" },
  downloadUrl: "https://pypi.org/project/obsei/",
  softwareHelp: { "@type": "CreativeWork", url: "https://docs.obsei.com/" },
  image: ogImage,
  sameAs: ["https://github.com/obsei/obsei", "https://obsei.com/", "https://blog.obsei.com/"],
};

export default defineConfig({
  site: "https://docs.obsei.com",
  integrations: [
    starlight({
      title: "obsei",
      logo: { light: "./src/assets/mark.svg", dark: "./src/assets/mark-dark.svg" },
      customCss: ["./src/styles/brand.css"],
      routeMiddleware: "./src/routeData.ts",
      favicon: "/favicon.svg",
      description: "Privacy-first, self-hosted, AI-native Voice of Customer.",
      head: [
        { tag: "meta", attrs: { name: "theme-color", content: "#238a91" } },
        { tag: "link", attrs: { rel: "icon", href: "/logo.png", type: "image/png" } },
        { tag: "meta", attrs: { property: "og:image", content: ogImage } },
        { tag: "meta", attrs: { property: "og:image:width", content: "1200" } },
        { tag: "meta", attrs: { property: "og:image:height", content: "630" } },
        { tag: "meta", attrs: { property: "og:image:alt", content: "obsei docs: install, configure and connect private Voice of Customer to your agents" } },
        { tag: "meta", attrs: { name: "twitter:image", content: ogImage } },
        { tag: "link", attrs: { rel: "alternate", type: "application/rss+xml", title: "obsei blog", href: "https://blog.obsei.com/rss.xml" } },
        { tag: "script", attrs: { type: "application/ld+json" }, content: JSON.stringify(softwareJsonLd) },
      ],
      social: [
        { icon: "github", label: "GitHub", href: "https://github.com/obsei/obsei" },
        { icon: "rss", label: "Blog", href: "https://blog.obsei.com/" },
      ],
      editLink: { baseUrl: "https://github.com/obsei/obsei/edit/master/docs/" },
      sidebar: [
        { label: "Start", items: ["quickstart", "how-it-works", "configuration", "examples"] },
        { label: "Guides", items: [{ autogenerate: { directory: "guides" } }] },
        { label: "Privacy", items: [{ autogenerate: { directory: "privacy" } }] },
        { label: "Reference", items: [{ autogenerate: { directory: "reference" } }] },
      ],
    }),
  ],
});
