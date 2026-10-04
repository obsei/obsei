import { AUTHORS, SITE } from "./consts";

export const publisher = {
  "@type": "Organization",
  "@id": "https://obsei.com/#organization",
  name: "obsei",
  url: "https://obsei.com/",
  logo: { "@type": "ImageObject", url: SITE.logo, width: 200, height: 200 },
  sameAs: ["https://github.com/obsei/obsei", "https://docs.obsei.com/", "https://pypi.org/project/obsei/"],
};

export function person(name: string) {
  const author = AUTHORS[name];
  return { "@type": "Person", name, ...(author ? { url: author.url, sameAs: author.sameAs } : {}) };
}
