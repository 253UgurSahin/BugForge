// Example Playwright spec for forge-test, with how to set up e2e/ at the top. It holds two flows
// to show the patterns; your app gets one spec per flow (e2e/f01-sign-in.spec.ts,
// e2e/f02-items.spec.ts, ...), with the shared part below exported from e2e/helpers.ts. Change
// the paths, labels, button names and the seed record to match your app. The case IDs (F01-N1)
// come from forge-work/test-plan.md. It works for every profile: it only talks to the app over
// HTTP.
//
// Set up e2e/ once, from the project root:
//   mkdir -p e2e && cd e2e && npm init -y && npm pkg set scripts.test="playwright test"
//   npm i -D -E @playwright/test @axe-core/playwright && npx playwright install chromium
// Keep it out of the app: e2e/ in .dockerignore; e2e/node_modules/, e2e/test-results/,
// e2e/playwright-report/ and e2e/.auth/ in .gitignore. next: "e2e" in tsconfig.json's exclude, or
// `next build` type-checks the specs and fails. next and static: exclude:
// [...configDefaults.exclude, 'e2e/**'] in the Vitest config's test block, or Vitest runs them.
//
// Every sign-in counts against the app's rate limit, so the seed users sign in once per run, in a
// setup project, and the specs reuse their cookies. e2e/playwright.config.ts:
//   import { defineConfig } from '@playwright/test';
//   export default defineConfig({
//     workers: 1,
//     use: { baseURL: process.env.FORGE_BASE_URL || 'http://localhost:8080' },
//     projects: [
//       { name: 'setup', testMatch: /auth\.setup\.ts/ },
//       { name: 'chromium', testMatch: /\.spec\.ts$/, dependencies: ['setup'] },
//     ],
//   });
// e2e/auth.setup.ts, which also tests the happy path of signing in (F01-H1):
//   import { test as setup, expect } from '@playwright/test';
//   import { ALICE, AUTH, BOB, PASSWORD, signIn } from './helpers';
//   for (const [email, file] of [[ALICE, AUTH.alice], [BOB, AUTH.bob]]) {
//     setup(`F01-H1 ${email} signs in and sees the dashboard`, async ({ page }) => {
//       setup.skip(!PASSWORD, 'set E2E_PASSWORD to the password of the seed users');
//       await signIn(page, email);
//       await expect(page.getByRole('heading', { name: /dashboard/i })).toBeVisible();
//       await page.context().storageState({ path: file });
//     });
//   }
// Keep the other specs that sign in or sign up within the limit, setup included (Better Auth: 3
// per 10 s from one address; Laravel Fortify: 5 a minute per email).
//
// Run it against your own compose stack, never against someone else's site, from e2e/:
//   FORGE_BASE_URL=http://localhost:8080 E2E_PASSWORD=... npx playwright test
// The browser download fails (a proxy, a sandbox): run it in Playwright's own image, which has the
// browser, of the exact version in package.json (here 1.64.1), with both variables exported:
//   docker run --rm --ipc=host --network host -u "$(id -u)" -e HOME=/tmp -v "$PWD":/e2e -w /e2e \
//     -e FORGE_BASE_URL -e E2E_PASSWORD mcr.microsoft.com/playwright:v1.64.1-noble \
//     npx playwright test
// Without E2E_PASSWORD the signed-in tests are skipped and Playwright still exits 0: write each
// skip in test-plan.md.
//
// Selectors use roles and labels, never CSS classes, so they survive restyling and the rebrand.
import { test, expect, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

// The app under test. The default is the port the forge compose stack publishes.
const BASE_URL = process.env.FORGE_BASE_URL || 'http://localhost:8080';
test.use({ baseURL: BASE_URL });

// Seed users made by your seed script: fake people with one shared test password that comes
// from the environment (E2E_PASSWORD). Never a real password, never written in this file.
const PASSWORD = process.env.E2E_PASSWORD || '';
const ALICE = 'alice@example.test';
const BOB = 'bob@example.test';
// Where the setup project saves their cookies, relative to e2e/ (git-ignored).
const AUTH = { alice: '.auth/alice.json', bob: '.auth/bob.json' };
// A record that belongs to ALICE in your seed data, and a text that only that record shows.
const ALICE_RECORD = { path: '/items/1', text: 'Alice first item' };

// Every test fails on a console error, an uncaught page error, a 5xx response, or a 4xx on one
// of the app's own scripts, stylesheets, images or fonts (a broken asset), not only on a failed
// expect.
const ASSETS = ['script', 'stylesheet', 'image', 'font'];
let problems: string[] = [];

test.beforeEach(async ({ page }) => {
  problems = [];
  page.on('console', (message) => {
    // The browser also logs every failed response as "Failed to load resource". The response
    // check below decides which failed responses count, so those lines are skipped here.
    if (message.type() === 'error' && !message.text().startsWith('Failed to load resource')) {
      problems.push(`console error: ${message.text()}`);
    }
  });
  page.on('pageerror', (error) => problems.push(`page error: ${error.message}`));
  page.on('response', (response) => {
    const status = response.status();
    const ownAsset = ASSETS.includes(response.request().resourceType())
      && new URL(response.url()).origin === new URL(BASE_URL).origin;
    if (status >= 500 || (status >= 400 && ownAsset)) problems.push(`${status} on ${response.url()}`);
  });
});

test.afterEach(() => {
  expect(problems).toEqual([]);
});

// WCAG 2.0, 2.1 and 2.2 level A and AA checks with axe (touch target size and autocomplete
// included) on the screen that is open now. Run it on every screen.
async function expectAccessible(page: Page) {
  const result = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'])
    .analyze();
  expect(result.violations.map((violation) => `${violation.id}: ${violation.help}`)).toEqual([]);
}

async function signIn(page: Page, email: string, password = PASSWORD) {
  await page.goto('/login');
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password').fill(password);
  await page.getByRole('button', { name: /log in|sign in/i }).click();
}

// Works for every app, the static profile too.
test('home page loads without errors and passes the accessibility scan', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
  await expectAccessible(page);
});

// Delete the groups below when your app has no accounts.
test.describe('F01 sign in', () => {
  test.skip(!PASSWORD, 'set E2E_PASSWORD to the password of the seed users');

  test('F01-N1 a wrong password shows an error and does not sign in', async ({ page }) => {
    await signIn(page, ALICE, `wrong-${Date.now()}`);
    // The filter skips empty alerts: Next.js puts one on every page (its route announcer).
    await expect(page.getByRole('alert').filter({ hasText: /\S/ })).toBeVisible();
    await expect(page).toHaveURL(/login/);
  });
});

// Signed in as ALICE with the cookies the setup project saved: no new sign-in.
test.describe('F02 items', () => {
  test.skip(!PASSWORD, 'set E2E_PASSWORD to the password of the seed users');
  test.use({ storageState: AUTH.alice });

  test('F02-E1 a second user cannot open the first user\'s item', async ({ page, browser }) => {
    // First the owner: ALICE opens her record and sees it. This proves the URL is right; a wrong
    // path or a missing seed record gives a 404 to everyone and would pass the check below.
    const own = await page.goto(ALICE_RECORD.path);
    expect(own?.status()).toBe(200);
    await expect(page.getByText(ALICE_RECORD.text)).toBeVisible();
    await expectAccessible(page);

    // Then BOB, with his own cookies, asks for the same URL. First what matters most: none of
    // her data reaches him.
    const bob = await browser.newContext({ baseURL: BASE_URL, storageState: AUTH.bob });
    const response = await bob.request.get(ALICE_RECORD.path);
    expect(await response.text()).not.toContain(ALICE_RECORD.text);
    // Then a 403 or 404. That needs the owner check to run before the page starts streaming: a
    // Next.js page that checks inside <Suspense> has already sent 200. Report that as its own bug.
    expect([403, 404]).toContain(response.status());
    await bob.close();
  });

  test('F02-E2 the same form sent twice at once creates one item, not two', async ({ page }) => {
    const name = `Double submit ${Date.now()}`;
    await page.goto('/items/new');
    await page.getByLabel('Name').fill(name);
    // A double click on a slow connection: send the filled-in form twice at the same moment, with
    // this user's cookies and the form's hidden fields (such as the CSRF token). Two clicks in the
    // browser are not reliable for a classic form: the browser often drops the first request.
    // A Next.js Server Action cannot be called this way (it needs Next's own action header): there,
    // replace the lines from `const form` to the `for` loop with
    // `await page.getByRole('button', { name: /save/i }).dblclick()` and wait for the list.
    const form = page.locator('form', { has: page.getByRole('button', { name: /save/i }) });
    const fields = await form.evaluate((element) =>
      Object.fromEntries(new FormData(element as HTMLFormElement)) as Record<string, string>);
    const responses = await Promise.all([
      page.request.post('/items', { form: fields }),
      page.request.post('/items', { form: fields }),
    ]);
    for (const response of responses) expect(response.status()).toBeLessThan(500);
    await page.goto('/items');
    await expect(page.getByText(name)).toHaveCount(1);
  });
});
