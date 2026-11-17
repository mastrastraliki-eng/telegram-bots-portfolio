// Render demo/out/*.html to PNG screenshots in docs/screenshots/.
// Usage: node demo/screenshot.mjs   (needs Playwright with Chromium)
import { createRequire } from "node:module";
import { readdirSync, mkdirSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const { chromium } = createRequire(import.meta.url)("playwright");
const here = dirname(fileURLToPath(import.meta.url));
const out = join(here, "out");
const shots = join(here, "..", "docs", "screenshots");
mkdirSync(shots, { recursive: true });

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 420, height: 800 }, deviceScaleFactor: 2 });
for (const f of readdirSync(out).filter((f) => f.endsWith(".html"))) {
  await page.goto(pathToFileURL(join(out, f)).href);
  await page.screenshot({ path: join(shots, f.replace(".html", ".png")), fullPage: true });
  console.log("saved", f.replace(".html", ".png"));
}
await browser.close();
