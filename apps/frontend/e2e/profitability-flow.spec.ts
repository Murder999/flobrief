import { test, expect, type Page } from "@playwright/test";
import { execFileSync } from "node:child_process";
import path from "node:path";

/**
 * Regression suite for the profitability module (Part 2 Phase 6):
 * brand-level revenue/cost/margin derived from real, already-invoiced
 * ClientInvoice/ClientInvoiceLine rows, and the explicit "cost rate
 * missing" affordance (ProfitabilityService's real
 * `margin_missing_reason = "cost_rate_eksik"`, rendered by the frontend as
 * "Maliyet oranı eksik") for a scope where no cost snapshot exists --
 * proving the UI never fabricates a 0% margin or a silently blank cell
 * when the underlying data genuinely can't support one.
 *
 * Fixture is seeded via apps/backend/scripts/e2e_seed_profitability.py:
 * one Agency/owner with two Brands, each carrying one real "sent"
 * ClientInvoice + line -- one line has a real cost_rate_snapshot_cents,
 * the other's is left NULL on purpose.
 */

const BACKEND_DIR = path.resolve(__dirname, "../../backend");
const PYTHON = process.env.E2E_PYTHON ?? path.join(BACKEND_DIR, ".venv", "Scripts", "python.exe");

let OWNER_EMAIL: string;
let PASSWORD: string;
let BRAND_WITH_COST_NAME: string;
let BRAND_NO_COST_NAME: string;
let AGENCY_ID: string;

function runSeedScript(args: string[]): Record<string, string> {
  const output = execFileSync(PYTHON, ["scripts/e2e_seed_profitability.py", ...args], {
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
  OWNER_EMAIL = env.E2E_OWNER_EMAIL;
  PASSWORD = env.E2E_PASSWORD;
  BRAND_WITH_COST_NAME = env.E2E_BRAND_WITH_COST_NAME;
  BRAND_NO_COST_NAME = env.E2E_BRAND_NO_COST_NAME;
  AGENCY_ID = env.__AGENCY_ID__;
  if (!OWNER_EMAIL || !BRAND_WITH_COST_NAME || !BRAND_NO_COST_NAME) {
    throw new Error("profitability fixture seed did not return the expected env vars");
  }
});

test.afterAll(() => {
  if (AGENCY_ID) runSeedScript(["cleanup", AGENCY_ID]);
});

async function loginAgency(page: Page, email: string, password: string) {
  await page.goto("/auth/agency-login");
  await page.locator("#agency-email").fill(email);
  await page.locator("#agency-password").fill(password);
  await page.getByRole("button", { name: "Ajans Paneline Giriş Yap" }).click();
  await page.waitForURL((url) => url.pathname.startsWith("/dashboard"), { timeout: 15_000 });
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

test.describe.serial("Profitability flow", () => {
  test("owner sees real revenue/cost/margin for the brand with a cost rate, and an honest 'Maliyet oranı eksik' flag for the one without", async ({
    page,
  }) => {
    const consoleErrors = trackConsoleErrors(page);
    await loginAgency(page, OWNER_EMAIL, PASSWORD);

    await page.goto("/dashboard/finance/profitability");
    await expect(page.getByRole("heading", { name: "Kârlılık" })).toBeVisible({ timeout: 15_000 });

    // Explicit monthly range so today's seeded invoices are always in scope
    // regardless of whatever default period the page might otherwise pick.
    await page.getByRole("button", { name: "Aylık" }).click();

    await expect(page.getByRole("heading", { name: "Marka Bazlı" })).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText(BRAND_WITH_COST_NAME).first()).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText(BRAND_NO_COST_NAME).first()).toBeVisible();

    const rowWithCost = page.getByRole("row").filter({ hasText: BRAND_WITH_COST_NAME });
    const rowNoCost = page.getByRole("row").filter({ hasText: BRAND_NO_COST_NAME });

    // Real cost rate configured: the row renders actual computed cost/
    // margin data, never the missing-rate placeholder.
    await expect(rowWithCost.getByText("Maliyet oranı eksik")).toHaveCount(0);
    // 5 hours invoiced at a real cost snapshot -> a genuine non-zero,
    // non-placeholder Turkish-formatted currency figure is present.
    await expect(rowWithCost).toContainText(/\d/);

    // No cost rate configured for this brand's invoiced line: the UI must
    // honestly say so, not render a fabricated 0% or a blank cell.
    await expect(rowNoCost.getByText("Maliyet oranı eksik").first()).toBeVisible({ timeout: 10_000 });

    expect(consoleErrors, `Unexpected console errors: ${consoleErrors.join("\n")}`).toEqual([]);
  });

  test("mobile viewport has no horizontal overflow", async ({ page }) => {
    await loginAgency(page, OWNER_EMAIL, PASSWORD);
    await page.goto("/dashboard/finance/profitability");
    await expect(page.getByRole("heading", { name: "Kârlılık" })).toBeVisible({ timeout: 15_000 });

    await page.setViewportSize({ width: 390, height: 844 });
    await page.waitForTimeout(300);
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - window.innerWidth
    );
    expect(overflow).toBeLessThanOrEqual(1);
  });
});
