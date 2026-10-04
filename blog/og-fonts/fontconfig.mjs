// Social cards are SVGs rendered to PNG by sharp (librsvg), which finds fonts through
// fontconfig. Point fontconfig at the bundled Inter subset so cards look the same on every
// build machine, with or without system fonts. Imported first thing by astro.config.mjs,
// before sharp initialises fontconfig.
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const dir = path.dirname(fileURLToPath(import.meta.url));
const conf = path.join(os.tmpdir(), "obsei-blog-fonts.conf");
fs.writeFileSync(
  conf,
  `<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "fonts.dtd">
<fontconfig>
  <dir>${dir}</dir>
  <include ignore_missing="yes">/etc/fonts/fonts.conf</include>
  <cachedir>${path.join(os.tmpdir(), "obsei-blog-fontcache")}</cachedir>
</fontconfig>
`,
);
process.env.FONTCONFIG_FILE = conf;
