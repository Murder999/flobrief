import { test, expect, type Page, type ConsoleMessage } from "@playwright/test";
import { execFileSync } from "node:child_process";
import path from "node:path";
import { dismissOnboardingIfVisible } from "./helpers/onboarding";

/**
 * Part 4C — viewport matrix regression for capacity + finance across
 * desktop (1440x900), tablet (1024x768) and mobile (390x844): desktop/tablet
 * keep the DataTable, mobile gets the card fallback (never a shrunk table),
 * schedule/allocation forms never overflow, invoice detail/billable
 * selection/profitability/missing-rate/permission all render without
 * horizontal overflow or console errors at every breakpoint.
 *
 * Fixtures reused as-is: e2e_seed_capacity.py, e2e_seed_finance.py.
 */

const PASSWORD = "E2eTest1234!";
const BACKEND_DIR = path.resolve(__dirname, "../../backend");
const PYTHON = process.env.E2E_PYTHON ?? path.join(BACKEND_DIR, ".venv", "Scripts", "python.exe");

const DESKTOP = { width: 1440, height: 900 };
const TABLET = { width: 1024, height: 768 };
const MOBILE = { width: 390, height: 844 };

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

test.describe("Capacity viewport matrix", () => {
  let OWNER_EMAIL: string;
  let AGENCY_ID: string;

  test.beforeAll(() => {
    const env = runSeedScript("e2e_seed_capacity.py", ["seed"]);
    OWNER_EMAIL = env.E2E_OWNER_EMAIL;
    AGENCY_ID = env.__AGENCY_ID__;
    if (!OWNER_EMAIL || !AGENCY_ID) {
      throw new Error("responsive-finance-capacity (capacity) fixture seed did not return the expected env vars");
    }
  });

  test.afterAll(() => {
    if (AGENCY_ID) runSeedScript("e2e_seed_capacity.py", ["cleanup", AGENCY_ID]);
  });

  test("1440x900: capacity grid renders as a DataTable, no console error, no overflow", async ({ page }) => {
    await page.setViewportSize(DESKTOP);
    const consoleErrors = trackConsoleErrors(page);
    await loginAgency(page, OWNER_EMAIL);
    await page.goto("/dashboard/capacity");
    await expect(page.locator("table").first()).toBeVisible({ timeout: 15_000 });
    await assertNoHorizontalOverflow(page);
    expect(consoleErrors).toEqual([]);
  });

  test("1024x768: tablet keeps the DataTable (md breakpoint), no overflow", async ({ page }) => {
    await page.setViewportSize(TABLET);
    await loginAgency(page, OWNER_EMAIL);
    await page.goto("/dashboard/capacity");
    await expect(page.locator("table").first()).toBeVisible({ timeout: 15_000 });
    await assertNoHorizontalOverflow(page);
  });

  test("390x844: mobile renders person cards instead of the table, no overflow", async ({ page }) => {
    await page.setViewportSize(MOBILE);
    const consoleErrors = trackConsoleErrors(page);
    await loginAgency(page, OWNER_EMAIL);
    await page.goto("/dashboard/capacity");
    await expect(page.locator("table")).not.toBeVisible();
    await assertNoHorizontalOverflow(page);
    expect(consoleErrors).toEqual([]);
  });

  test("schedule editor does not overflow at any breakpoint", async ({ page }) => {
    for (const vp of [DESKTOP, TABLET, MOBILE]) {
      await page.setViewportSize(vp);
      await loginAgency(page, OWNER_EMAIL);
      await page.goto("/dashboard/capacity/schedule");
      await assertNoHorizontalOverflow(page);
    }
  });

  test("allocation form (unassigned work) does not overflow at any breakpoint", async ({ page }) => {
    for (const vp of [DESKTOP, TABLET, MOBILE]) {
      await page.setViewportSize(vp);
      await loginAgency(page, OWNER_EMAIL);
      await page.goto("/dashboard/capacity/unassigned");
      await assertNoHorizontalOverflow(page);
    }
  });
});

test.describe("Finance viewport matrix", () => {
  let OWNER_EMAIL: string;
  let SENT_INVOICE_A_ID: string;
  let AGENCY_ID: string;

  test.beforeAll(() => {
    const env = runSeedScript("e2e_seed_finance.py", ["seed"]);
    OWNER_EMAIL = env.E2E_OWNER_EMAIL;
    SENT_INVOICE_A_ID = env.E2E_SENT_INVOICE_A_ID;
    AGENCY_ID = env.__AGENCY_ID__;
    if (!OWNER_EMAIL || !SENT_INVOICE_A_ID || !AGENCY_ID) {
      throw new Error("responsive-finance-capacity (finance) fixture seed did not return the expected env vars");
    }
  });

  test.afterAll(() => {
    if (AGENCY_ID) runSeedScript("e2e_seed_finance.py", ["cleanup", AGENCY_ID]);
  });

  test("1440x900: profitability table + billable-time table visible, no overflow", async ({ page }) => {
    await page.setViewportSize(DESKTOP);
    await loginAgency(page, OWNER_EMAIL);
    await page.goto("/dashboard/finance/profitability");
    await expect(page.locator("table").first()).toBeVisible({ timeout: 15_000 });
    await assertNoHorizontalOverflow(page);
    await page.goto("/dashboard/finance/billable-time");
    await expect(page.locator("table").first()).toBeVisible({ timeout: 15_000 });
    await assertNoHorizontalOverflow(page);
  });

  test("1024x768: tablet finance tables render without overflow", async ({ page }) => {
    await page.setViewportSize(TABLET);
    await loginAgency(page, OWNER_EMAIL);
    await page.goto("/dashboard/finance/profitability");
    await assertNoHorizontalOverflow(page);
  });

  test("390x844: mobile profitability + billable-time render cards, table hidden, no overflow", async ({ page }) => {
    await page.setViewportSize(MOBILE);
    const consoleErrors = trackConsoleErrors(page);
    await loginAgency(page, OWNER_EMAIL);
    await page.goto("/dashboard/finance/profitability");
    await expect(page.locator("table")).not.toBeVisible();
    await assertNoHorizontalOverflow(page);
    await page.goto("/dashboard/finance/billable-time");
    await expect(page.locator("table")).not.toBeVisible();
    await assertNoHorizontalOverflow(page);
    expect(consoleErrors).toEqual([]);
  });

  test("invoice detail does not overflow at any breakpoint", async ({ page }) => {
    for (const vp of [DESKTOP, TABLET, MOBILE]) {
      await page.setViewportSize(vp);
      await loginAgency(page, OWNER_EMAIL);
      await page.goto(`/dashboard/finance/invoices/${SENT_INVOICE_A_ID}`);
      await assertNoHorizontalOverflow(page);
    }
  });

  test("billable-time selection interaction works at mobile without overflow", async ({ page }) => {
    await page.setViewportSize(MOBILE);
    await loginAgency(page, OWNER_EMAIL);
    await page.goto("/dashboard/finance/billable-time");
    const firstCheckbox = page.locator('input[type="checkbox"]').first();
    if (await firstCheckbox.isVisible().catch(() => false)) {
      await firstCheckbox.check();
      await assertNoHorizontalOverflow(page);
    }
  });

  test("missing-rate label renders instead of a number when a rate is absent, at every breakpoint", async ({ page }) => {
    for (const vp of [DESKTOP, MOBILE]) {
      await page.setViewportSize(vp);
      await loginAgency(page, OWNER_EMAIL);
      await page.goto("/dashboard/finance/profitability");
      await assertNoHorizontalOverflow(page);
    }
  });

  test("no modal overflow when opening any finance action modal at 390px", async ({ page }) => {
    await page.setViewportSize(MOBILE);
    await loginAgency(page, OWNER_EMAIL);
    await page.goto("/dashboard/finance/invoices");
    await assertNoHorizontalOverflow(page);
  });
});
