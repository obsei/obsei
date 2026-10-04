// Renders SVG social cards to 1200x630 PNG at build time with sharp, which Astro already uses.
// Fonts come from og-fonts/ (see og-fonts/fontconfig.mjs, loaded by astro.config.mjs).
import sharp from "sharp";

export async function renderPng(source: Buffer): Promise<Buffer> {
  return sharp(source).resize(1200, 630, { fit: "cover" }).png({ compressionLevel: 9 }).toBuffer();
}
