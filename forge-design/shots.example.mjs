// Screenshots of your own app for forge-design design's look review (../forge-design/review.md).
// Copy it to forge-work/design/shots.mjs and run it where Playwright is installed (e2e/ has it):
//
//   node forge-work/design/shots.mjs http://localhost:8080 forge-work/design/shots/round-1 / /login
//   node forge-work/design/shots.mjs BASE OUT --state e2e/.auth/alice.json /dashboard /settings
//
// Each path gives a full-page PNG at 390px and 1440px wide, in light and in dark: OUT/<name>-390-light.png.
// --no-dark leaves the dark shots out (an app without a dark theme). --state FILE signs in with a
// Playwright storage state (the file forge-check test's setup project writes). It only loads pages, as a
// visitor would, and only from the base URL you give: run it against your own stack.
import { chromium } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import { join } from 'node:path';

const WIDTHS = [390, 1440];
const args = process.argv.slice(2);
const flags = { dark: !args.includes('--no-dark'), state: undefined };
const at = args.indexOf('--state');
if (at !== -1) flags.state = args.splice(at, 2)[1]; // takes the flag and its file out of args
const rest = args.filter((arg) => arg !== '--no-dark');
const [base, out, ...paths] = rest;

if (!base || !out || !/^https?:\/\//.test(base)) {
  console.error('usage: node shots.mjs BASE_URL OUT_DIR [--no-dark] [--state FILE] [PATH...]');
  process.exit(2);
}

// "/" becomes "home", "/settings/billing?tab=2" becomes "settings-billing-tab-2".
const nameOf = (path) => path.replace(/[^a-zA-Z0-9]+/g, '-').replace(/^-+|-+$/g, '') || 'home';

await mkdir(out, { recursive: true });
const browser = await chromium.launch();
let failed = 0;
try {
  for (const scheme of flags.dark ? ['light', 'dark'] : ['light']) {
    for (const width of WIDTHS) {
      const context = await browser.newContext({
        viewport: { width, height: width < 600 ? 844 : 900 },
        colorScheme: scheme,
        deviceScaleFactor: 1, // 100%: eyedropper.py and imgdiff.py read real pixels
        reducedMotion: 'reduce', // a still frame, not the middle of an animation
        storageState: flags.state,
      });
      const page = await context.newPage();
      for (const path of paths.length ? paths : ['/']) {
        const url = new URL(path, base);
        if (url.origin !== new URL(base).origin) {
          console.error(`skipped ${path}: not on ${base}`);
          failed += 1;
          continue;
        }
        try {
          const response = await page.goto(url.href, { waitUntil: 'networkidle', timeout: 30000 });
          await page.evaluate(() => document.fonts.ready);
          const file = join(out, `${nameOf(path)}-${width}-${scheme}.png`);
          await page.screenshot({ path: file, fullPage: true });
          console.log(`${response ? response.status() : '---'} ${file}`);
        } catch (error) {
          console.error(`failed ${path} at ${width}px ${scheme}: ${String(error).split('\n')[0]}`);
          failed += 1;
        }
      }
      await context.close();
    }
  }
} finally {
  await browser.close();
}
process.exit(failed ? 1 : 0);
