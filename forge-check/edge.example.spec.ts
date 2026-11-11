// Edge cases for forge-check test: helpers you can reuse for every form, and one worked example (F02,
// the "new item" form of ../forge-check/e2e.example.spec.ts). Copy it to e2e/edge.spec.ts (an app with
// its own Playwright setup: edge.spec.ts beside its specs, where its config runs it), keep the
// helpers (or move them to e2e/helpers.ts), and write one `describe` per form of your app: change
// FORM below (the paths, the label, the button, where the saved record shows). The case IDs
// (F02-E3) come from forge-work/test-plan.md.
//
// Set-up and running are the same as for the other specs (the top of e2e.example.spec.ts): the
// base URL from FORGE_BASE_URL, the seed users' cookies from the setup project, your own stack only.
// Each case that fails leaves a screenshot in forge-work/test/evidence/<case>.png: name that file
// on the bug's `evidence:` line in forge-work/bugs.md.
//
// The cases: nothing filled in, a 300-character value, emoji and accents, text that looks like
// HTML or SQL (it must come back as plain text and never run), a double click on submit (one
// record), the back button mid-flow, a refresh mid-flow, offline, an expired session and a slow
// network. Wrong input for one kind of field (letters in a number, "abc" as an email) works like
// the empty case: fill it in, submit, then expectRejected().
//
// Selectors use roles and labels, never CSS classes.
import { test, expect, type Locator, type Page, type Route } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';

const BASE_URL = process.env.FORGE_BASE_URL || 'http://localhost:8080';
test.use({ baseURL: BASE_URL });
const PASSWORD = process.env.E2E_PASSWORD || '';
const AUTH = { alice: '.auth/alice.json' }; // saved by the setup project, relative to e2e/

// forge-work/ is in the project root: one folder up when this runs from e2e/.
const WORK = process.env.FORGE_WORK
  || [path.resolve('forge-work'), path.resolve('..', 'forge-work')].find((dir) => fs.existsSync(dir))
  || path.resolve('..', 'forge-work');
const EVIDENCE = path.join(WORK, 'test', 'evidence');

// ---- The helpers ----

// Values to type. Every one gets Date.now() in front, so each run makes records of its own.
export const LONG = (length = 300) => 'L'.repeat(length);
export const ACCENTS = 'Zoë Ångström-Müller 😀 日本';
// If the app ever runs this as HTML, the picture's error handler sets window.__forgeRan.
export const HTML_TEXT = '<img src=x onerror="window.__forgeRan=1"><b>bold</b>';
export const SQL_TEXT = "Robert'); DROP TABLE items;--";

// Run one case; when it fails, save a full-page screenshot as evidence and fail as usual.
export async function withEvidence(page: Page, caseId: string, steps: () => Promise<void>) {
  try {
    await steps();
  } catch (error) {
    fs.mkdirSync(EVIDENCE, { recursive: true });
    const file = path.join(EVIDENCE, `${caseId.replace(/[^\w-]/g, '-')}.png`);
    await page.screenshot({ path: file, fullPage: true }).catch(() => {}); // offline pages may not draw
    throw error;
  }
}

// The app said no in a way the user can see: the field is marked invalid (by the browser or with
// aria-invalid), or there is an alert with text. And it did not crash.
export async function expectRejected(page: Page, field: Locator) {
  await expect(async () => {
    const invalid = await field.evaluate((element) =>
      element.getAttribute('aria-invalid') === 'true'
      || ('checkValidity' in element && !(element as HTMLInputElement).checkValidity()));
    const alerts = await page.getByRole('alert').filter({ hasText: /\S/ }).count();
    expect(invalid || alerts > 0, 'no visible sign that the input was refused').toBe(true);
  }).toPass({ timeout: 5_000 });
}

// The text is on the page as text: the user sees it letter for letter, the browser made no
// element out of it, and nothing in it ran.
export async function expectShownAsText(page: Page, text: string) {
  await expect(page.getByText(text, { exact: false }).first()).toBeVisible();
  expect(await page.evaluate(() => (window as any).__forgeRan), 'the typed HTML ran as code').toBeUndefined();
  expect(await page.locator('img[src="x"]').count(), 'the typed HTML became an element').toBe(0);
}

// A double click that fails when its second click would miss the button (see doubleClick in
// e2e.example.spec.ts for why Locator.dblclick() is not enough).
export async function doubleClick(page: Page, button: Locator) {
  await button.scrollIntoViewIfNeeded();
  const element = (await button.elementHandle())!;
  const box = (await element.boundingBox())!;
  const at = { x: box.x + box.width / 2, y: box.y + box.height / 2 };
  await page.mouse.click(at.x, at.y);
  const stillThere = await element.evaluate(
    (node, point) => node.contains(document.elementFromPoint(point.x, point.y)), at).catch(() => false);
  if (!stillThere) return; // the first click already left the page: a second one has nothing to hit
  await page.mouse.down({ clickCount: 2 });
  await page.mouse.up({ clickCount: 2 });
}

// Every request waits this long first, like a weak phone connection. Returns a function that
// makes the network fast again.
export async function slowNetwork(page: Page, delayMs = 1_500) {
  const handler = async (route: Route) => {
    await new Promise((resolve) => setTimeout(resolve, delayMs));
    await route.continue().catch(() => {}); // the page may have moved on
  };
  await page.route('**/*', handler);
  return () => page.unroute('**/*', handler);
}

// The session ended while the form was open: the cookies are gone, as after a time-out.
export async function expireSession(page: Page) {
  await page.context().clearCookies();
}

// A 5xx answer or an uncaught script error is a crash, whatever the case was testing.
export function watchForCrashes(page: Page) {
  const crashes: string[] = [];
  page.on('pageerror', (error) => crashes.push(`page error: ${error.message}`));
  page.on('response', (response) => {
    if (response.status() >= 500) crashes.push(`${response.status()} on ${response.url().split('?')[0]}`);
  });
  return crashes;
}

// ---- The worked example: the "new item" form ----

const FORM = {
  path: '/items/new', // where the form is
  list: '/items', // where a saved record shows
  field: (page: Page) => page.getByLabel('Name'),
  submit: (page: Page) => page.getByRole('button', { name: /save/i }),
  login: /login|sign-?in/, // where an expired session should land
};

async function fillAndSave(page: Page, value: string) {
  await page.goto(FORM.path);
  await FORM.field(page).fill(value);
  await FORM.submit(page).click();
  await page.waitForLoadState('networkidle');
}

async function expectSaved(page: Page, value: string, times = 1) {
  await page.goto(FORM.list);
  await expect(page.getByText(value, { exact: false })).toHaveCount(times);
}

test.describe('F02 new item: edge cases', () => {
  test.skip(!PASSWORD, 'set E2E_PASSWORD to the password of the seed users');
  test.use({ storageState: AUTH.alice });
  let crashes: string[] = [];

  test.beforeEach(({ page }) => { crashes = watchForCrashes(page); });
  test.afterEach(() => { expect(crashes).toEqual([]); });

  test('F02-E3 nothing filled in: refused with a visible message, nothing saved', async ({ page }) => {
    await withEvidence(page, 'F02-E3', async () => {
      await page.goto(FORM.path);
      await FORM.submit(page).click();
      await expectRejected(page, FORM.field(page));
      await expect(page).toHaveURL(new RegExp(FORM.path)); // still on the form
    });
  });

  test('F02-E4 a 300-character value: saved whole or refused, never a crash or a broken page', async ({ page }) => {
    await withEvidence(page, 'F02-E4', async () => {
      const value = `${Date.now()} ${LONG(300)}`;
      await fillAndSave(page, value);
      const refused = await FORM.field(page).isVisible().catch(() => false);
      if (refused) {
        await expectRejected(page, FORM.field(page)); // a limit is fine when the user is told
      } else {
        await expectSaved(page, value.slice(0, 40));
        // The long word must wrap or be cut with an ellipsis: the page may not scroll sideways.
        const sideways = await page.evaluate(() =>
          document.documentElement.scrollWidth - document.documentElement.clientWidth);
        expect(sideways, 'the long value makes the page scroll sideways').toBeLessThanOrEqual(0);
      }
    });
  });

  test('F02-E5 emoji and accents come back exactly as typed', async ({ page }) => {
    await withEvidence(page, 'F02-E5', async () => {
      const value = `${Date.now()} ${ACCENTS}`;
      await fillAndSave(page, value);
      await expectSaved(page, value);
    });
  });

  for (const [caseId, kind, text] of [['F02-E6', 'HTML', HTML_TEXT], ['F02-E7', 'SQL', SQL_TEXT]]) {
    test(`${caseId} text that looks like ${kind} is shown as text and never runs`, async ({ page }) => {
      await withEvidence(page, caseId, async () => {
        page.on('dialog', (dialog) => { crashes.push(`a dialog opened: ${dialog.message()}`); void dialog.dismiss(); });
        const value = `${Date.now()} ${text}`;
        await fillAndSave(page, value);
        await page.goto(FORM.list);
        await expectShownAsText(page, value);
        // The list still works, with the seed record in it: nothing was dropped or cut short.
        await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
      });
    });
  }

  test('F02-E8 a double click on Save makes one record', async ({ page }) => {
    await withEvidence(page, 'F02-E8', async () => {
      const value = `Double ${Date.now()}`;
      await page.goto(FORM.path);
      await FORM.field(page).fill(value);
      await doubleClick(page, FORM.submit(page));
      await page.waitForLoadState('networkidle');
      await expectSaved(page, value, 1);
    });
  });

  test('F02-E9 back button mid-flow: the form still works and saves once', async ({ page }) => {
    await withEvidence(page, 'F02-E9', async () => {
      const value = `Back ${Date.now()}`;
      await page.goto(FORM.list);
      await page.goto(FORM.path);
      await FORM.field(page).fill(value);
      await page.goBack();
      await page.goForward();
      await expect(FORM.field(page)).toBeVisible(); // no blank page, no "document expired"
      await FORM.field(page).fill(value); // whether the browser kept the text or not
      await FORM.submit(page).click();
      await page.waitForLoadState('networkidle');
      // And back again after saving must not send the form a second time.
      await page.goBack();
      await expectSaved(page, value, 1);
    });
  });

  test('F02-E10 refresh mid-flow: no error, and the form saves once after it', async ({ page }) => {
    await withEvidence(page, 'F02-E10', async () => {
      const value = `Refresh ${Date.now()}`;
      await page.goto(FORM.path);
      await FORM.field(page).fill(value);
      await page.reload();
      await expect(FORM.field(page)).toBeVisible();
      await FORM.field(page).fill(value);
      await FORM.submit(page).click();
      await page.waitForLoadState('networkidle');
      await expectSaved(page, value, 1);
    });
  });

  test('F02-E11 offline: nothing is saved twice or lost without a word, and it works again online', async ({ page, context }) => {
    await withEvidence(page, 'F02-E11', async () => {
      const value = `Offline ${Date.now()}`;
      await page.goto(FORM.path);
      await FORM.field(page).fill(value);
      await context.setOffline(true);
      await FORM.submit(page).click().catch(() => {});
      // A form the page's own script sends should now say so (an alert) and keep the text. A
      // classic form shows the browser's own "no internet" page: that is the browser, not a bug.
      await page.waitForTimeout(1_000);
      await context.setOffline(false);
      if (!(await FORM.field(page).isVisible().catch(() => false))) await page.goto(FORM.path);
      await FORM.field(page).fill(value);
      await FORM.submit(page).click();
      await page.waitForLoadState('networkidle');
      await expectSaved(page, value, 1);
    });
  });

  test('F02-E12 expired session: sent to sign in, nothing saved, no crash', async ({ page }) => {
    await withEvidence(page, 'F02-E12', async () => {
      const value = `Expired ${Date.now()}`;
      await page.goto(FORM.path);
      await FORM.field(page).fill(value);
      await expireSession(page);
      await FORM.submit(page).click();
      await page.waitForLoadState('networkidle');
      // Either the sign-in page, or a plain message on the form (a 419 "page expired" page with
      // no way on is a medium bug: report it).
      const onLogin = FORM.login.test(new URL(page.url()).pathname);
      const told = await page.getByRole('alert').filter({ hasText: /\S/ }).count();
      expect(onLogin || told > 0, 'no sign-in page and no message after the session ended').toBe(true);
      // Nothing was saved without a session. A fresh context with the saved cookies looks.
      const again = await page.context().browser()!.newContext({ baseURL: BASE_URL, storageState: AUTH.alice });
      const list = await again.newPage();
      await list.goto(FORM.list);
      await expect(list.getByText(value)).toHaveCount(0);
      await again.close();
    });
  });

  test('F02-E13 slow network: an impatient second click still makes one record', async ({ page }) => {
    await withEvidence(page, 'F02-E13', async () => {
      const value = `Slow ${Date.now()}`;
      await page.goto(FORM.path);
      await FORM.field(page).fill(value);
      const fast = await slowNetwork(page);
      await FORM.submit(page).click();
      // While the first request waits, the user clicks again if the button lets them.
      await FORM.submit(page).click({ timeout: 1_000 }).catch(() => {}); // disabled or gone: good
      await fast();
      await page.waitForLoadState('networkidle');
      await expectSaved(page, value, 1);
    });
  });
});
