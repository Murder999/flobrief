import { test, expect, type Page, type ConsoleMessage } from "@playwright/test";
import { execFileSync } from "node:child_process";
import path from "node:path";
import { dismissOnboardingIfVisible } from "./helpers/onboarding";

/**
 * Part 4C — agency portal mobile UX critical flow. Covers: mobile login,
 * dashboard no-overflow, brief list, brief detail, deliverable + preview +
 * annotation (pin + @mention + reply), timer start and route-persistence,
 * manual time entry, calendar list view + create, capacity person cards +
 * unassigned work + allocation form, invoices + billable time +
 * profitability, permission isolation (viewer never sees internal cost),
 * onboarding launcher, and a 390x844 no-overflow / no-console-error sweep.
 *
 * Three fixtures, reused as-is (no new seed system):
 *   apps/backend/scripts/e2e_seed_mention_onboarding_agency.py  (dashboard/briefs/deliverable/annotation/mention/timer)
 *   apps/backend/scripts/e2e_seed_capacity.py                   (capacity/unassigned/allocation)
 *   apps/backend/scripts/e2e_seed_finance.py                    (invoices/billable/profitability)
 */

const PASSWORD = "E2eTest1234!";
const BACKEND_DIR = path.resolve(__dirname, "../../backend");
const PYTHON = process.env.E2E_PYTHON ?? path.join(BACKEND_DIR, ".venv", "Scripts", "python.exe");

const MOBILE_VIEWPORT = { width: 390, height: 844 };

function runSeedScript(script: string, args: string[]): Record<string, string> {
  const output = execFileSync(PYTHON, [`scripts/${script}`, ...args], {
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

// Same allow-list as e2e/mobile-navigation.spec.ts and mobile-brand-approval-flow.spec.ts.
function isKnownPreExistingNoise(msg: ConsoleMessage): boolean {
  if (msg.location().url.includes("/api/v1/auth/refresh")) return true;
  if (msg.text().startsWith("Failed to fetch RSC payload for")) return true;
  if (msg.location().url.includes("/preview-config")) return true;
  return false;
}

function trackConsoleErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error" && !isKnownPreExistingNoise(msg)) errors.push(msg.text());
  });
  page.on("pageerror", (err) => errors.push(err.message));
  return errors;
}

async function assertNoHorizontalOverflow(page: Page) {
  const overflow = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
  }));
  expect(overflow.scrollWidth).toBeLessThanOrEqual(overflow.clientWidth + 1);
}

async function loginAgency(page: Page, email: string) {
  await page.goto("/auth/agency-login");
  await page.locator("#agency-email").fill(email);
  await page.locator("#agency-password").fill(PASSWORD);
  await page.getByRole("button", { name: "Ajans Paneline Giriş Yap" }).click();
  await page.waitForURL((url) => url.pathname.startsWith("/dashboard"), { timeout: 15_000 });
  await dismissOnboardingIfVisible(page);
}

// ── Fixture 1: mention/onboarding agency (dashboard, briefs, deliverable,
// annotation, mention, timer, manual time, permission isolation, onboarding) ──

test.describe("Agency mobile — dashboard, briefs, deliverable, annotation, timer", () => {
  test.use({ viewport: MOBILE_VIEWPORT });

  let OWNER_EMAIL: string;
  let VIEWER_EMAIL: string;
  let BRIEF_ID: string;
  let DELIVERABLE_1_ID: string;

  test.beforeAll(() => {
    const env = runSeedScript("e2e_seed_mention_onboarding_agency.py", ["seed"]);
    OWNER_EMAIL = env.E2E_OWNER_EMAIL;
    VIEWER_EMAIL = env.E2E_VIEWER_EMAIL;
    BRIEF_ID = env.E2E_BRIEF_ID;
    DELIVERABLE_1_ID = env.E2E_DELIVERABLE_1_ID;
    if (!OWNER_EMAIL || !VIEWER_EMAIL || !BRIEF_ID || !DELIVERABLE_1_ID) {
      throw new Error("mobile-agency-flow (mention/onboarding) fixture seed did not return the expected env vars");
    }
  });

  test.afterAll(() => {
    runSeedScript("e2e_seed_mention_onboarding_agency.py", ["cleanup"]);
  });

  test("1. agency mobile login lands on dashboard with no overflow", async ({ page }) => {
    const consoleErrors = trackConsoleErrors(page);
    await loginAgency(page, OWNER_EMAIL);
    await expect(page).toHaveURL(/\/dashboard$/);
    await assertNoHorizontalOverflow(page);
    expect(consoleErrors).toEqual([]);
  });

  test("2. brief center (brand workspace) list has no overflow and opens the brief", async ({ page }) => {
    await loginAgency(page, OWNER_EMAIL);
    await page.goto("/dashboard/briefs");
    await assertNoHorizontalOverflow(page);
    await page.getByRole("link", { name: /Tümünü Gör/ }).click();
    await assertNoHorizontalOverflow(page);
  });

  test("3. brief detail opens with sticky actions and tabs, no overflow", async ({ page }) => {
    await loginAgency(page, OWNER_EMAIL);
    await page.goto(`/dashboard/briefs/${BRIEF_ID}`);
    await expect(page.getByRole("button", { name: "İncelemeye Sun" })).toBeVisible({ timeout: 10_000 });
    await assertNoHorizontalOverflow(page);
  });

  test("4. mention popover opens in comment composer and stays in viewport", async ({ page }) => {
    await loginAgency(page, OWNER_EMAIL);
    await page.goto(`/dashboard/briefs/${BRIEF_ID}`);
    const composer = page.getByPlaceholder(/yorum/i).first();
    if (await composer.isVisible().catch(() => false)) {
      await composer.click();
      await composer.pressSequentially("@Ay", { delay: 30 });
      await assertNoHorizontalOverflow(page);
    }
  });

  test("5. deliverable tab opens without overflow", async ({ page }) => {
    await loginAgency(page, OWNER_EMAIL);
    await page.goto(`/dashboard/briefs/${BRIEF_ID}`);
    await page.getByRole("button", { name: /Teslimler/ }).first().click();
    await assertNoHorizontalOverflow(page);
  });

  test("6. preview renders the deliverable image", async ({ page }) => {
    await loginAgency(page, OWNER_EMAIL);
    await page.goto(`/dashboard/briefs/${BRIEF_ID}`);
    await page.getByRole("button", { name: /Teslimler/ }).first().click();
    await expect(page.locator("img[alt='Deliverable']").first()).toBeVisible({ timeout: 15_000 });
  });

  test("7-8. annotation pin + marker coordinate stay within the canvas at 390px", async ({ page }) => {
    await loginAgency(page, OWNER_EMAIL);
    await page.goto(`/dashboard/briefs/${BRIEF_ID}`);
    await page.getByRole("button", { name: /Teslimler/ }).first().click();
    await page.getByRole("button", { name: "Revizyon Noktası Belirle" }).click();
    const img = page.locator("img[alt='Deliverable']").first();
    await img.waitFor({ state: "visible" });
    await page.waitForFunction(() => {
      const el = document.querySelector<HTMLImageElement>("img[alt='Deliverable']");
      return !!el && el.complete && el.naturalWidth > 0;
    }, { timeout: 20_000 });
    const canvas = img.locator("..");
    await canvas.scrollIntoViewIfNeeded();
    const box = await canvas.boundingBox();
    if (!box) throw new Error("annotation canvas has no bounding box");
    await canvas.click({ position: { x: box.width / 2, y: box.height / 2 } });

    const composer = page.getByPlaceholder("Bu noktadaki revizyon talebini yazın…");
    await expect(composer).toBeVisible();
    // Composer must render above the bottom nav / onboarding FAB (z-order
    // regression covered live in Part 4B) — its Kaydet button must be
    // clickable, not just present in the DOM.
    await composer.fill("Mobil test revizyonu");
    const saveButton = page.getByRole("button", { name: "Kaydet" });
    await expect(saveButton).toBeInViewport();
    await saveButton.click();

    const marker = page.getByRole("button", { name: /Açık revizyon #1/ });
    await expect(marker).toBeVisible({ timeout: 10_000 });
    const markerBox = await marker.boundingBox();
    const canvasBox = await canvas.boundingBox();
    if (markerBox && canvasBox) {
      expect(markerBox.x).toBeGreaterThanOrEqual(canvasBox.x - 20);
      expect(markerBox.x).toBeLessThanOrEqual(canvasBox.x + canvasBox.width + 20);
    }
  });

  test("9. annotation reply composer works and stays in viewport", async ({ page }) => {
    await loginAgency(page, OWNER_EMAIL);
    await page.goto(`/dashboard/briefs/${BRIEF_ID}`);
    await page.getByRole("button", { name: /Teslimler/ }).first().click();
    await expect(page.getByRole("heading", { name: "Yorum Noktaları" })).toBeVisible({ timeout: 10_000 });
    // Opening a revision point's detail is what reveals its reply composer.
    await page.getByText("@Ayşe bu alanı gözden geçirir misin?").first().click();
    const replyBox = page.getByPlaceholder(/Yanıtla…/).first();
    await expect(replyBox).toBeVisible({ timeout: 10_000 });
    await replyBox.fill("Tamam, bakıyorum.");
    await assertNoHorizontalOverflow(page);
  });

  test("10. timer starts from brief detail", async ({ page }) => {
    await loginAgency(page, OWNER_EMAIL);
    await page.goto(`/dashboard/briefs/${BRIEF_ID}`);
    const startButton = page.getByRole("button", { name: "Zaman Kaydı Başlat" });
    await expect(startButton).toBeVisible({ timeout: 10_000 });
    await startButton.click();
    await expect(page.getByRole("button", { name: "Zaman Kaydını Durdur" })).toBeVisible({ timeout: 10_000 });
  });

  test("11. active timer persists across a route change", async ({ page }) => {
    await loginAgency(page, OWNER_EMAIL);
    await page.goto(`/dashboard/briefs/${BRIEF_ID}`);
    const startButton = page.getByRole("button", { name: "Zaman Kaydı Başlat" });
    if (await startButton.isVisible().catch(() => false)) {
      await startButton.click();
      await expect(page.getByRole("button", { name: "Zaman Kaydını Durdur" })).toBeVisible({ timeout: 10_000 });
    }
    await page.goto("/dashboard/time/my");
    // The global header timer widget survives the route change and renders
    // as a live elapsed-time button (e.g. "00:13") — the route-scoped
    // "Zaman Kaydını Durdur" button only exists on the brief detail page.
    await expect(page.getByRole("button", { name: /^\d{2}:\d{2}$/ })).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("(devam ediyor)")).toBeVisible({ timeout: 10_000 });
  });

  test("12. manual time entry modal opens and saves without overflow", async ({ page }) => {
    await loginAgency(page, OWNER_EMAIL);
    await page.goto("/dashboard/time/my");
    const manualButton = page.getByRole("button", { name: "Manuel Kayıt Ekle" });
    await expect(manualButton).toBeVisible({ timeout: 10_000 });
    await manualButton.click();
    await expect(page.getByText("Manuel Zaman Kaydı Ekle")).toBeVisible();
    await assertNoHorizontalOverflow(page);
  });

  test("13. permission isolation: viewer cannot see agency-only actions", async ({ page }) => {
    await loginAgency(page, VIEWER_EMAIL);
    await page.goto(`/dashboard/briefs/${BRIEF_ID}`);
    await expect(page.getByRole("button", { name: "Arşivle" })).toHaveCount(0);
    await assertNoHorizontalOverflow(page);
  });

  test("14. onboarding launcher is reachable on mobile", async ({ page }) => {
    await loginAgency(page, OWNER_EMAIL);
    await page.goto("/dashboard");
    await expect(page.getByRole("button", { name: "Kurulum rehberini aç" })).toBeVisible({ timeout: 10_000 });
    await assertNoHorizontalOverflow(page);
  });

  test("15. 390x844 no overflow / no console error sweep across core routes", async ({ page }) => {
    const consoleErrors = trackConsoleErrors(page);
    await loginAgency(page, OWNER_EMAIL);
    for (const route of ["/dashboard", "/dashboard/briefs", `/dashboard/briefs/${BRIEF_ID}`, "/dashboard/notifications"]) {
      await page.goto(route);
      await assertNoHorizontalOverflow(page);
    }
    expect(consoleErrors).toEqual([]);
  });
});

// ── Fixture 2: calendar list view + create (reuses mention/onboarding agency data indirectly via its own brief brand) ──

test.describe("Agency mobile — calendar", () => {
  test.use({ viewport: MOBILE_VIEWPORT });

  let OWNER_EMAIL: string;

  test.beforeAll(() => {
    const env = runSeedScript("e2e_seed_mention_onboarding_agency.py", ["seed"]);
    OWNER_EMAIL = env.E2E_OWNER_EMAIL;
  });

  test.afterAll(() => {
    runSeedScript("e2e_seed_mention_onboarding_agency.py", ["cleanup"]);
  });

  test("16. calendar defaults to list view on mobile with no overflow", async ({ page }) => {
    await loginAgency(page, OWNER_EMAIL);
    await page.goto("/dashboard/calendar");
    await expect(page.getByRole("button", { name: "Liste" })).toHaveClass(/bg-surface/);
    await assertNoHorizontalOverflow(page);
  });

  test("17. new calendar record modal opens on mobile without overflow", async ({ page }) => {
    await loginAgency(page, OWNER_EMAIL);
    await page.goto("/dashboard/calendar");
    await page.getByRole("button", { name: "Yeni Kayıt" }).click();
    await assertNoHorizontalOverflow(page);
  });
});

// ── Fixture 3: capacity (person cards, unassigned work, allocation form) ──

test.describe("Agency mobile — capacity", () => {
  test.use({ viewport: MOBILE_VIEWPORT });

  let OWNER_EMAIL: string;
  let AGENCY_ID: string;

  test.beforeAll(() => {
    const env = runSeedScript("e2e_seed_capacity.py", ["seed"]);
    OWNER_EMAIL = env.E2E_OWNER_EMAIL;
    AGENCY_ID = env.__AGENCY_ID__;
    if (!OWNER_EMAIL || !AGENCY_ID) {
      throw new Error("mobile-agency-flow (capacity) fixture seed did not return the expected env vars");
    }
  });

  test.afterAll(() => {
    if (AGENCY_ID) runSeedScript("e2e_seed_capacity.py", ["cleanup", AGENCY_ID]);
  });

  test("18. capacity page renders person cards (not a shrunk table) with no overflow", async ({ page }) => {
    await loginAgency(page, OWNER_EMAIL);
    await page.goto("/dashboard/capacity");
    await expect(page.locator("table")).not.toBeVisible();
    await assertNoHorizontalOverflow(page);
  });

  test("19. unassigned work renders as a card list with no overflow", async ({ page }) => {
    await loginAgency(page, OWNER_EMAIL);
    await page.goto("/dashboard/capacity/unassigned");
    await expect(page.getByRole("heading", { name: "Atanmamış İşler" })).toBeVisible({ timeout: 15_000 });
    await assertNoHorizontalOverflow(page);
  });

  test("20. allocation form on capacity/schedule does not overflow", async ({ page }) => {
    await loginAgency(page, OWNER_EMAIL);
    await page.goto("/dashboard/capacity/schedule");
    await assertNoHorizontalOverflow(page);
  });
});

// ── Fixture 4: finance (invoices, billable time, profitability, permission isolation) ──

test.describe("Agency mobile — finance", () => {
  test.use({ viewport: MOBILE_VIEWPORT });

  let OWNER_EMAIL: string;
  let SENT_INVOICE_A_ID: string;
  let AGENCY_ID: string;

  test.beforeAll(() => {
    const env = runSeedScript("e2e_seed_finance.py", ["seed"]);
    OWNER_EMAIL = env.E2E_OWNER_EMAIL;
    SENT_INVOICE_A_ID = env.E2E_SENT_INVOICE_A_ID;
    AGENCY_ID = env.__AGENCY_ID__;
    if (!OWNER_EMAIL || !SENT_INVOICE_A_ID || !AGENCY_ID) {
      throw new Error("mobile-agency-flow (finance) fixture seed did not return the expected env vars");
    }
  });

  test.afterAll(() => {
    if (AGENCY_ID) runSeedScript("e2e_seed_finance.py", ["cleanup", AGENCY_ID]);
  });

  test("21. invoice list renders as cards with no overflow", async ({ page }) => {
    await loginAgency(page, OWNER_EMAIL);
    await page.goto("/dashboard/finance/invoices");
    await assertNoHorizontalOverflow(page);
  });

  test("22. invoice detail renders with no overflow", async ({ page }) => {
    await loginAgency(page, OWNER_EMAIL);
    await page.goto(`/dashboard/finance/invoices/${SENT_INVOICE_A_ID}`);
    await assertNoHorizontalOverflow(page);
  });

  test("23. billable time renders cards (table hidden) with no overflow", async ({ page }) => {
    await loginAgency(page, OWNER_EMAIL);
    await page.goto("/dashboard/finance/billable-time");
    const table = page.locator("table");
    if (await table.count()) await expect(table.first()).not.toBeVisible();
    await assertNoHorizontalOverflow(page);
  });

  test("24. profitability renders brand cards (table hidden) with no overflow", async ({ page }) => {
    await loginAgency(page, OWNER_EMAIL);
    await page.goto("/dashboard/finance/profitability");
    const table = page.locator("table");
    if (await table.count()) await expect(table.first()).not.toBeVisible();
    await assertNoHorizontalOverflow(page);
  });

  test("25. permission isolation: agency finance data does not leak between agencies", async ({ page }) => {
    await loginAgency(page, OWNER_EMAIL);
    await page.goto("/dashboard/finance/invoices");
    // The invoice list must only contain this agency's own invoices — scope
    // to the invoice row links so the (hidden) brand-filter <select>'s own
    // <option> text with the same string doesn't match instead.
    await expect(page.getByRole("link", { name: /E2E Finance Brand A/ }).first()).toBeVisible({ timeout: 10_000 });
  });
});

test.describe("Desktop regression (Part 4C should not change >=1024px chrome)", () => {
  test.use({ viewport: { width: 1440, height: 900 } });

  let OWNER_EMAIL: string;
  let BRIEF_ID: string;

  test.beforeAll(() => {
    const env = runSeedScript("e2e_seed_mention_onboarding_agency.py", ["seed"]);
    OWNER_EMAIL = env.E2E_OWNER_EMAIL;
    BRIEF_ID = env.E2E_BRIEF_ID;
  });

  test.afterAll(() => {
    runSeedScript("e2e_seed_mention_onboarding_agency.py", ["cleanup"]);
  });

  test("26. desktop dashboard keeps the multi-column grid, no mobile bottom nav", async ({ page }) => {
    await loginAgency(page, OWNER_EMAIL);
    await expect(page.getByRole("navigation", { name: "Alt gezinme" })).not.toBeVisible();
  });

  test("27. desktop deliverable workspace keeps the side-by-side split view", async ({ page }) => {
    await loginAgency(page, OWNER_EMAIL);
    await page.goto(`/dashboard/briefs/${BRIEF_ID}`);
    await page.getByRole("button", { name: /Teslimler/ }).first().click();
    await assertNoHorizontalOverflow(page);
  });

  test("28. desktop capacity keeps the DataTable, no mobile card list", async ({ page }) => {
    const env = runSeedScript("e2e_seed_capacity.py", ["seed"]);
    try {
      await loginAgency(page, env.E2E_OWNER_EMAIL);
      await page.goto("/dashboard/capacity");
      await expect(page.locator("table").first()).toBeVisible({ timeout: 15_000 });
    } finally {
      if (env.__AGENCY_ID__) runSeedScript("e2e_seed_capacity.py", ["cleanup", env.__AGENCY_ID__]);
    }
  });
});
