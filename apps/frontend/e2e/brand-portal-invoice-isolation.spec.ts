import { test, expect, type Page } from "@playwright/test";
import { execFileSync } from "node:child_process";
import path from "node:path";

/**
 * Regression suite for brand-portal invoice isolation (Part 2 Phase 4/7
 * security checklist): a brand-portal user sees only their own brand's
 * *sent* (non-draft) invoices, a cross-tenant direct-navigation attempt at
 * another brand's invoice id is a real IDOR refusal (not a leaked render),
 * and no cost/margin figure -- internal-only data that never belongs on a
 * customer-facing document -- ever appears anywhere on the page.
 *
 * Fixture is seeded via apps/backend/scripts/e2e_seed_finance.py (shared
 * with invoice-lifecycle-flow.spec.ts; safe because playwright.config.ts
 * runs with workers: 1 / fullyParallel: false so the two spec files never
 * run concurrently against the same fixture emails). It directly inserts,
 * for Brand A: one "sent" invoice (with a line carrying a deliberately
 * distinctive 13337.00 TRY/hour cost-rate snapshot) and one "draft"
 * invoice; for Brand B: one "sent" invoice used as the cross-tenant IDOR
 * target.
 */

const BACKEND_DIR = path.resolve(__dirname, "../../backend");
const PYTHON = process.env.E2E_PYTHON ?? path.join(BACKEND_DIR, ".venv", "Scripts", "python.exe");

const PASSWORD = "E2eTest1234!";
let BRAND_A_EMAIL: string;
let SENT_INVOICE_A_ID: string;
let DRAFT_INVOICE_A_ID: string;
let SENT_INVOICE_B_ID: string;
let AGENCY_ID: string;

function runSeedScript(args: string[]): Record<string, string> {
  const output = execFileSync(PYTHON, ["scripts/e2e_seed_finance.py", ...args], {
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
  BRAND_A_EMAIL = env.E2E_BRAND_A_EMAIL;
  SENT_INVOICE_A_ID = env.E2E_SENT_INVOICE_A_ID;
  DRAFT_INVOICE_A_ID = env.E2E_DRAFT_INVOICE_A_ID;
  SENT_INVOICE_B_ID = env.E2E_SENT_INVOICE_B_ID;
  AGENCY_ID = env.__AGENCY_ID__;
  if (!BRAND_A_EMAIL || !SENT_INVOICE_A_ID || !SENT_INVOICE_B_ID) {
    throw new Error("finance fixture seed did not return the expected env vars");
  }
});

test.afterAll(() => {
  if (AGENCY_ID) runSeedScript(["cleanup", AGENCY_ID]);
});

async function loginBrand(page: Page, email: string) {
  await page.goto("/brand/login");
  await page.waitForLoadState("networkidle");
  await page.locator("#brand-email").fill(email);
  await page.locator("#brand-password").fill(PASSWORD);
  await page.getByRole("button", { name: "Marka Portalına Giriş Yap" }).click();
  await page.waitForURL((url) => url.pathname.startsWith("/brand") && url.pathname !== "/brand/login", {
    timeout: 15_000,
  });
}

const KNOWN_NOISE = /^Failed to load resource:|^Failed to fetch RSC payload/;

function trackConsoleErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error" && !KNOWN_NOISE.test(msg.text())) errors.push(msg.text());
  });
  page.on("pageerror", (err) => errors.push(err.message));
  return errors;
}

test.describe.serial("Brand portal invoice isolation", () => {
  test("brand A sees only its own sent invoice, never the draft, and no cost figure leaks", async ({
    page,
  }) => {
    const consoleErrors = trackConsoleErrors(page);
    await loginBrand(page, BRAND_A_EMAIL);

    await page.goto("/brand/invoices");
    await expect(page.getByRole("heading", { name: "Faturalar" })).toBeVisible({ timeout: 15_000 });

    // Real, sent invoice is visible.
    await expect(page.getByText(/E2E-SENT-A-/).first()).toBeVisible({ timeout: 10_000 });
    // The draft invoice for the SAME brand is a real server-side exclusion,
    // not a UI filter -- it must never appear in the list.
    await expect(page.getByText(/E2E-DRAFT-A-/)).toHaveCount(0);

    const listText = await page.locator("body").innerText();
    expect(listText).not.toContain("13337");

    expect(consoleErrors, `Unexpected console errors: ${consoleErrors.join("\n")}`).toEqual([]);
  });

  test("brand A's own invoice detail renders real data with no cost/margin figure anywhere", async ({
    page,
  }) => {
    await loginBrand(page, BRAND_A_EMAIL);
    await page.goto(`/brand/invoices/${SENT_INVOICE_A_ID}`);

    await expect(page.getByText(/E2E-SENT-A-/).first()).toBeVisible({ timeout: 15_000 });
    await expect(page.locator("text=Gönderildi").first()).toBeVisible({ timeout: 10_000 });
    await expect(page.getByRole("button", { name: "PDF İndir" })).toBeVisible();

    const detailText = await page.locator("body").innerText();
    expect(detailText).not.toContain("13337");
    expect(detailText).not.toContain("cost_rate_snapshot_cents");
    expect(detailText).not.toContain("billing_rate_snapshot_cents");
  });

  test("direct navigation to another brand's invoice id is a real IDOR refusal, not a leaked render", async ({
    page,
  }) => {
    await loginBrand(page, BRAND_A_EMAIL);
    await page.goto(`/brand/invoices/${SENT_INVOICE_B_ID}`);

    await expect(page.getByText("Fatura bulunamadı")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByRole("link", { name: "Faturalara Dön" })).toBeVisible();
    // The foreign brand's real invoice number must never have rendered.
    await expect(page.getByText(/E2E-SENT-B-/)).toHaveCount(0);

    const refusalText = await page.locator("body").innerText();
    expect(refusalText).not.toContain("13337");
  });

  test("mobile viewport has no horizontal overflow", async ({ page }) => {
    await loginBrand(page, BRAND_A_EMAIL);
    await page.goto("/brand/invoices");
    await expect(page.getByRole("heading", { name: "Faturalar" })).toBeVisible({ timeout: 15_000 });

    await page.setViewportSize({ width: 390, height: 844 });
    await page.waitForTimeout(300);
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - window.innerWidth
    );
    expect(overflow).toBeLessThanOrEqual(1);
  });
});
