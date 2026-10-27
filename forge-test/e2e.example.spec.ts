// Example Playwright spec for forge-test. It holds two flows to show the patterns; your app gets
// one spec per flow: the F01 group in e2e/f01-sign-in.spec.ts, the F02 group in
// e2e/f02-create-item.spec.ts, and so on, each with the shared part at the top (or that part in
// e2e/helpers.ts). Change the paths, labels, button names and the seed record to match your app.
// The case IDs (F01-H1) come from forge-work/test-plan.md. It works for every profile: it only
// talks to the app over HTTP.
//
// Run it against your own compose stack, never against someone else's site:
//   FORGE_BASE_URL=http://localhost:8080 E2E_PASSWORD=... npx playwright test
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

  test('F01-H1 a seed user signs in and sees the dashboard', async ({ page }) => {
    await signIn(page, ALICE);
    await expect(page.getByRole('heading', { name: /dashboard/i })).toBeVisible();
    await expectAccessible(page);
  });

  test('F01-N1 a wrong password shows an error and does not sign in', async ({ page }) => {
    await signIn(page, ALICE, `wrong-${Date.now()}`);
    await expect(page.getByRole('alert')).toBeVisible();
    await expect(page).toHaveURL(/login/);
  });

  test('F01-E1 a second user cannot open the first user\'s record', async ({ page, browser }) => {
    // First the owner: ALICE opens her record and sees it. This proves the URL is right; a wrong
    // path or a missing seed record gives a 404 to everyone and would pass the check below.
    await signIn(page, ALICE);
    const own = await page.goto(ALICE_RECORD.path);
    expect(own?.status()).toBe(200);
    await expect(page.getByText(ALICE_RECORD.text)).toBeVisible();

    // Then BOB, in a browser context of his own (his own cookies), asks for the same URL.
    // He must get 403 or 404, never the data.
    const context = await browser.newContext({ baseURL: BASE_URL });
    const bobPage = await context.newPage();
    await signIn(bobPage, BOB);
    await expect(bobPage.getByRole('heading', { name: /dashboard/i })).toBeVisible();
    const response = await bobPage.request.get(ALICE_RECORD.path);
    expect([403, 404]).toContain(response.status());
    expect(await response.text()).not.toContain(ALICE_RECORD.text);
    await context.close();
  });
});

test.describe('F02 create an item', () => {
  test.skip(!PASSWORD, 'set E2E_PASSWORD to the password of the seed users');

  test('F02-E1 the same form sent twice at once creates one item, not two', async ({ page }) => {
    await signIn(page, ALICE);
    const name = `Double submit ${Date.now()}`;
    await page.goto('/items/new');
    await page.getByLabel('Name').fill(name);
    // A double click on a slow connection: send the filled-in form twice at the same moment, with
    // this user's cookies and the form's hidden fields (such as the CSRF token). Two clicks in the
    // browser are not reliable for this: the browser often drops the first request.
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
