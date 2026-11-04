#!/usr/bin/env node
// Generate favicon.ico and PNG icons from SVG
// Run: npx tsx scripts/generate-icons.ts

import { writeFileSync, mkdirSync, existsSync } from "fs";
import { join } from "path";

const publicDir = join(process.cwd(), "public");

if (!existsSync(join(publicDir, "icon.svg"))) {
  console.error("icon.svg not found in public/");
  process.exit(1);
}

console.log("Icon generation script placeholder.");
console.log("For production, use a tool like sharp or ImageMagick to generate:");
console.log("  - favicon.ico (16x16, 32x32, 48x48)");
console.log("  - icon-192.png (192x192)");
console.log("  - icon-512.png (512x512)");
console.log("  - apple-touch-icon.png (180x180)");
console.log("");
console.log("Example with ImageMagick:");
console.log("  magick icon.svg -define icon:auto-resize=16,32,48,64 favicon.ico");
console.log("  magick icon.svg -resize 192x192 icon-192.png");
console.log("  magick icon.svg -resize 512x512 icon-512.png");
console.log("  magick icon.svg -resize 180x180 apple-touch-icon.png");