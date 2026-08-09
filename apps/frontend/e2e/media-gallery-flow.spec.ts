import { test, expect, type Page, type ConsoleMessage } from "@playwright/test";
import { execFileSync } from "node:child_process";
import path from "node:path";

/**
 * Media/notification UX regression suite: notification bell panel behavior,
 * Lightbox focus handling, authenticated download error handling, and the
 * dashboard "Dosyalar" duplicate-key regression (a brief with two AssetLink
 * rows for the same asset — see AssetRepository.list_for_brief).
 *
 * Fixture is seeded/cleaned via apps/backend/scripts/_tmp_media_gallery_e2e_seed.py
 * (real deliverables API, not hand-inserted rows) so this spec never touches
 * production data and never depends on a manually pre-set env var.
 */

const PASSWORD = "E2eTest1234!";
const BACKEND_DIR = path.resolve(__dirname, "../../backend");
const PYTHON = process.env.E2E_PYTHON ?? path.join(BACKEND_DIR, ".venv", "Scripts", "python.exe");

let AGENCY_EMAIL: string;
let BRAND_EMAIL: string;
let BRIEF_ID: string;
let AGENCY_ID: string;

function runSeedScript(args: string[]): Record<string, string> {
  const output = execFileSync(PYTHON, ["scripts/_tmp_media_gallery_e2e_seed.py", ...args], {
    cwd: BACKEND_DIR,
    encoding: "utf-8",
    maxBuffer: 1024 * 1024 * 20,
  });
  const env: Record<string, string> = {};
  for (const line of output.split(/\r?\n/)) {
    const match = line.match(/^([A-Z0-9_]+)=(.*)$/);
    if (match) env[match[1]] = match[2];
  }
  return env;
}

test.beforeAll(() => {
  const env = runSeedScript(["seed"]);
  AGENCY_EMAIL = env.E2E_AGENCY_EMAIL;
  BRAND_EMAIL = env.E2E_BRAND_EMAIL;
  BRIEF_ID = env.E2E_BRIEF_ID;
  AGENCY_ID = env.__AGENCY_ID__;
  if (!AGENCY_EMAIL || !BRIEF_ID) {
    throw new Error("media-gallery-flow fixture seed did not return the expected env vars");
  }
});

test.afterAll(() => {
  if (AGENCY_ID) runSeedScript(["cleanup", AGENCY_ID]);
});

async function loginAgency(page: Page) {
  await page.goto("/auth/agency-login");
  // Next dev serves its hydration bundle via <script async>, which doesn't
  // block the 'load' event goto() awaits — without this, the form's onSubmit
  // handler may not be attached yet and the click falls through to a native
  // (JS-less) form GET submission instead of the real login request.
  await page.waitForLoadState("networkidle");
  await page.locator("#agency-email").fill(AGENCY_EMAIL);
  await page.locator("#agency-password").fill(PASSWORD);
  await page.getByRole("button", { name: "Ajans Paneline Giriş Yap" }).click();
  await page.waitForURL((url) => url.pathname.startsWith("/dashboard"), { timeout: 15_000 });
}

async function loginBrand(page: Page) {
  await page.goto("/brand/login");
  await page.waitForLoadState("networkidle");
  await page.locator("#brand-email").fill(BRAND_EMAIL);
  await page.locator("#brand-password").fill(PASSWORD);
  await page.getByRole("button", { name: "Marka Portalına Giriş Yap" }).click();
  await page.waitForURL((url) => url.pathname.startsWith("/brand") && url.pathname !== "/brand/login", {
    timeout: 15_000,
  });
}

async function gotoAuthenticated(page: Page, url: string, loginPathPattern: RegExp) {
  await page.goto(url);
  if (loginPathPattern.test(new URL(page.url()).pathname)) {
    await page.waitForTimeout(500);
    await page.goto(url);
  }
}

// ── Notification bell ─────────────────────────────────────────────────────

test("notification bell opens/closes correctly in the agency dashboard", async ({ page }) => {
  await loginAgency(page);
  await gotoAuthenticated(page, "/dashboard", /\/auth\/(login|agency-login)$/);

  const bellButton = page.getByTitle("Bildirimler");
  await expect(bellButton).toBeVisible({ timeout: 15_000 });
  await expect(bellButton).toHaveAttribute("aria-expanded", "false");

  await bellButton.click();
  const panel = page.getByRole("dialog", { name: "Bildirimler" });
  await expect(panel).toBeVisible();
  await expect(bellButton).toHaveAttribute("aria-expanded", "true");

  // Portal-rendered: must not be visually clipped by an ancestor's overflow.
  const box = await panel.boundingBox();
  expect(box).not.toBeNull();
  const viewport = page.viewportSize();
  if (box && viewport) {
    expect(box.x).toBeGreaterThanOrEqual(0);
    expect(box.x + box.width).toBeLessThanOrEqual(viewport.width + 1);
    expect(box.y + box.height).toBeLessThanOrEqual(viewport.height + 1);
  }

  // Escape closes it.
  await page.keyboard.press("Escape");
  await expect(panel).toBeHidden();
  await expect(bellButton).toHaveAttribute("aria-expanded", "false");

  // Outside click closes it too.
  await bellButton.click();
  await expect(panel).toBeVisible();
  await page.mouse.click(10, 10);
  await expect(panel).toBeHidden();
  await expect(bellButton).toHaveAttribute("aria-expanded", "false");
});

test("notification bell opens/closes correctly in the brand portal", async ({ page }) => {
  await loginBrand(page);
  await gotoAuthenticated(page, "/brand/dashboard", /\/brand\/login$/);

  const bellButton = page.getByTitle("Bildirimler");
  await expect(bellButton).toBeVisible({ timeout: 15_000 });

  await bellButton.click();
  const panel = page.getByRole("dialog", { name: "Bildirimler" });
  await expect(panel).toBeVisible();
  await expect(bellButton).toHaveAttribute("aria-expanded", "true");

  await page.keyboard.press("Escape");
  await expect(panel).toBeHidden();
});

// ── Lightbox ───────────────────────────────────────────────────────────────

test("lightbox opens via Büyüt, traps focus, and restores focus on close", async ({ page }) => {
  await loginAgency(page);
  await gotoAuthenticated(page, `/dashboard/briefs/${BRIEF_ID}`, /\/auth\/(login|agency-login)$/);
  // "Teslimler" also appears as an inline link inside the "Genel" tab body, so
  // scope to the tab bar's first match (the tab button itself renders first).
  await page.getByRole("button", { name: "Teslimler" }).first().click();
  await expect(page.getByRole("button", { name: "E2E Galeri Görseli" })).toBeVisible({ timeout: 15_000 });
  await page.getByRole("button", { name: "E2E Galeri Görseli" }).click();

  const openMarkers = page.getByRole("button", { name: /Açık revizyon/ });
  const markerCountBefore = await openMarkers.count();

  const buyutButton = page.getByTitle("Büyüt");
  await expect(buyutButton).toBeVisible({ timeout: 10_000 });
  await buyutButton.click();

  const dialog = page.locator('[role="dialog"][aria-modal="true"]').last();
  await expect(dialog).toBeVisible();

  // Opening the lightbox must not toggle annotation mode / add a marker.
  await expect(openMarkers).toHaveCount(markerCountBefore);
  await expect(page.getByTitle("Kapat")).toBeVisible();

  // Focus enters the dialog on open.
  const activeInDialogOnOpen = await page.evaluate(() => {
    const dialogEl = document.querySelectorAll('[role="dialog"][aria-modal="true"]');
    const last = dialogEl[dialogEl.length - 1];
    return !!last && last.contains(document.activeElement);
  });
  expect(activeInDialogOnOpen).toBe(true);

  // Body scroll is locked while open.
  await expect.poll(() => page.evaluate(() => document.body.style.overflow)).toBe("hidden");

  // Shift+Tab from the first focusable element wraps to the last.
  await page.evaluate(() => {
    const dialogEl = document.querySelectorAll('[role="dialog"][aria-modal="true"]');
    const last = dialogEl[dialogEl.length - 1] as HTMLElement;
    const focusables = last.querySelectorAll<HTMLElement>('a[href], button:not([disabled])');
    focusables[0]?.focus();
  });
  await page.keyboard.press("Shift+Tab");
  const wrappedToLast = await page.evaluate(() => {
    const dialogEl = document.querySelectorAll('[role="dialog"][aria-modal="true"]');
    const last = dialogEl[dialogEl.length - 1] as HTMLElement;
    const focusables = Array.from(last.querySelectorAll<HTMLElement>('a[href], button:not([disabled])'));
    return document.activeElement === focusables[focusables.length - 1];
  });
  expect(wrappedToLast).toBe(true);

  // Tab from the last focusable element wraps back to the first.
  await page.keyboard.press("Tab");
  const wrappedToFirst = await page.evaluate(() => {
    const dialogEl = document.querySelectorAll('[role="dialog"][aria-modal="true"]');
    const last = dialogEl[dialogEl.length - 1] as HTMLElement;
    const focusables = Array.from(last.querySelectorAll<HTMLElement>('a[href], button:not([disabled])'));
    return document.activeElement === focusables[0];
  });
  expect(wrappedToFirst).toBe(true);

  // Escape closes it; body scroll unlocks; focus returns to the Büyüt trigger.
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
  await expect.poll(() => page.evaluate(() => document.body.style.overflow)).not.toBe("hidden");
  await expect(buyutButton).toBeFocused();
});

// ── Download ───────────────────────────────────────────────────────────────

test("download button hits the download endpoint, guards double-click, and surfaces errors", async ({ page }) => {
  await loginAgency(page);
  await gotoAuthenticated(page, `/dashboard/briefs/${BRIEF_ID}`, /\/auth\/(login|agency-login)$/);
  await page.getByRole("button", { name: "Referanslar" }).click();
  await expect(page.getByTitle("İndir").first()).toBeVisible({ timeout: 15_000 });

  const openMarkersBefore = await page.getByRole("button", { name: /Açık revizyon/ }).count();

  const downloadRequests: string[] = [];
  page.on("request", (req) => {
    if (/\/api\/v1\/assets\/[^/]+\/download$/.test(req.url())) downloadRequests.push(req.url());
  });

  // Double-click on the same download button must not fire two requests.
  // Dispatched via two synchronous DOM clicks in one JS tick — using two
  // separate Playwright .click() calls would let their actionability waits
  // serialize the clicks, letting the in-flight guard reset between them and
  // masking the bug this test exists to catch.
  const downloadButton = page.getByTitle("İndir").first();
  await downloadButton.evaluate((el: HTMLElement) => {
    el.click();
    el.click();
  });
  await page.waitForTimeout(1000);
  expect(downloadRequests.length).toBe(1);
  expect(downloadRequests[0]).toMatch(/\/api\/v1\/assets\/[0-9a-f-]+\/download$/);

  // No annotation is created as a side effect of downloading.
  const openMarkersAfter = await page.getByRole("button", { name: /Açık revizyon/ }).count();
  expect(openMarkersAfter).toBe(openMarkersBefore);

  // Mock a 403 on the next download call and assert a user-facing error toast.
  await page.route(/\/api\/v1\/assets\/[^/]+\/download$/, (route) =>
    route.fulfill({ status: 403, contentType: "application/json", body: "{}" })
  );
  await downloadButton.click();
  await expect(page.getByText(/İndirilemedi|indirilemedi/)).toBeVisible({ timeout: 5_000 });
  await page.unroute(/\/api\/v1\/assets\/[^/]+\/download$/);
});

// ── Gallery, navigation, and the duplicate-key regression ──────────────────

test("brief workspace: comment-gallery heading, tab switch, sidebar nav, and no duplicate-key warning", async ({ page }) => {
  const consoleErrors: ConsoleMessage[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") consoleErrors.push(msg);
  });

  await loginAgency(page);
  await gotoAuthenticated(page, `/dashboard/briefs/${BRIEF_ID}`, /\/auth\/(login|agency-login)$/);

  await expect(page.getByText("Yorumlara Eklenen Görseller")).toBeVisible({ timeout: 15_000 });

  // "Teslimler" link switches tab without a full page reload. There's also an
  // inline "Teslimler" link inside the "Genel" tab body — scope to .first()
  // (the tab button itself, which renders before that inline link in the DOM).
  await page.evaluate(() => {
    (window as unknown as { __e2eMarker: boolean }).__e2eMarker = true;
  });
  await page.getByRole("button", { name: "Teslimler" }).first().click();
  await expect(page.getByRole("button", { name: "E2E Galeri Görseli" })).toBeVisible({ timeout: 10_000 });
  const markerSurvived = await page.evaluate(
    () => (window as unknown as { __e2eMarker?: boolean }).__e2eMarker === true
  );
  expect(markerSurvived).toBe(true);

  // The "Referanslar" tab's "Dosyalar & Ekler" list renders the duplicate-linked
  // asset exactly once — the regression this fixture exists to catch (see
  // AssetRepository.list_for_brief). The filename shows as the <img alt>,
  // which is present regardless of the hover-revealed caption underneath it.
  await page.getByRole("button", { name: "Referanslar" }).click();
  await expect(page.getByText("Dosyalar & Ekler")).toBeVisible({ timeout: 10_000 });
  const assetImages = page.locator('img[alt="e2e-gallery.png"]');
  await expect(assetImages.first()).toBeAttached({ timeout: 10_000 });
  expect(await assetImages.count()).toBe(1);

  // Sidebar navigation to a different category is client-side (no full reload).
  await page.getByRole("link", { name: "Takvim" }).click();
  await expect(page).toHaveURL(/\/dashboard\/calendar/);
  const markerSurvivedNav = await page.evaluate(
    () => (window as unknown as { __e2eMarker?: boolean }).__e2eMarker === true
  );
  expect(markerSurvivedNav).toBe(true);

  const duplicateKeyWarnings = consoleErrors.filter((m) => /duplicate key|same key/i.test(m.text()));
  expect(duplicateKeyWarnings).toEqual([]);
});
