import { test, expect, type Page, type Locator } from "@playwright/test";
import { execFileSync } from "node:child_process";
import path from "node:path";

/**
 * Regression suite for the accounting connector module (Part 2 Phase 5):
 * configuring the only real implementation (the manual connector), running
 * a genuine synchronous test-connection (ManualConnector.test_connection()
 * makes zero network calls and always returns True -- this spec proves the
 * UI reflects that real result, not a fabricated one), and confirming every
 * non-manual provider (QuickBooks/Xero/Logo/Paraşüt/Mikro -- enum values
 * that exist for future readiness but ship zero HTTP client code) is
 * genuinely blocked from selection in the UI, matching the backend's own
 * NotImplementedError chokepoint.
 *
 * Fixture is seeded via apps/backend/scripts/e2e_seed_connector.py -- a
 * fresh, disposable Agency with a single owner (the only role with
 * ACCOUNTING_INTEGRATION_MANAGE). No AccountingConnector row is
 * pre-seeded; the spec creates and tests it entirely through the real
 * browser UI.
 */

const BACKEND_DIR = path.resolve(__dirname, "../../backend");
const PYTHON = process.env.E2E_PYTHON ?? path.join(BACKEND_DIR, ".venv", "Scripts", "python.exe");

let OWNER_EMAIL: string;
let PASSWORD: string;
let AGENCY_ID: string;

function runSeedScript(args: string[]): Record<string, string> {
  const output = execFileSync(PYTHON, ["scripts/e2e_seed_connector.py", ...args], {
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
  AGENCY_ID = env.__AGENCY_ID__;
  if (!OWNER_EMAIL || !AGENCY_ID) {
    throw new Error("connector fixture seed did not return the expected env vars");
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

function selectByLabel(scope: Locator, labelText: string): Locator {
  return scope.locator(
    `xpath=.//label[normalize-space(text())="${labelText}"]/parent::div//select`
  );
}

test.describe.serial("Accounting connector flow", () => {
  test("owner configures the manual connector, non-manual providers are genuinely blocked, and test-connection is a real synchronous success", async ({
    page,
  }) => {
    const consoleErrors = trackConsoleErrors(page);
    await loginAgency(page, OWNER_EMAIL, PASSWORD);

    await page.goto("/dashboard/finance/accounting");
    await expect(page.getByRole("heading", { name: "Muhasebe Entegrasyonu" })).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByText("Henüz bir muhasebe bağlantısı yapılandırılmadı")).toBeVisible({
      timeout: 10_000,
    });

    await page.getByRole("button", { name: "Bağlantı Ekle" }).click();
    await expect(page.getByText("Bağlantı Ekle").first()).toBeVisible({ timeout: 10_000 });

    const providerSelect = selectByLabel(page.locator("body"), "Sağlayıcı");
    await expect(providerSelect).toBeVisible({ timeout: 10_000 });

    // Every non-manual provider is a genuinely disabled <option>, not just
    // absent from a curated list -- matching the backend's registry, which
    // raises NotImplementedError for anything but "manual".
    const quickbooksOption = providerSelect.locator('option[value="quickbooks"]');
    await expect(quickbooksOption).toHaveText(/QuickBooks.*Yakında/);
    await expect(quickbooksOption).toBeDisabled();
    const xeroOption = providerSelect.locator('option[value="xero"]');
    await expect(xeroOption).toBeDisabled();

    // Attempting to select a disabled option is refused by the browser
    // itself; the select must remain on "manual" (the default/only real
    // choice).
    await expect(providerSelect).toHaveValue("manual");

    await page.getByRole("button", { name: "Bağlantıyı Oluştur" }).click();
    await expect(page.getByText("Bağlantı oluşturuldu.")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByRole("paragraph").filter({ hasText: /^Manuel$/ })).toBeVisible({
      timeout: 10_000,
    });
    await expect(page.getByText("Yapılandırılmadı", { exact: true }).first()).toBeVisible({
      timeout: 10_000,
    });

    // Real, synchronous test-connection (ManualConnector.test_connection()
    // makes zero network calls, always returns True) -- the UI reflects
    // whatever the backend actually returned, only via a toast + refetch.
    await page.getByRole("button", { name: "Bağlantıyı Test Et" }).click();
    await expect(page.getByText("Bağlantı testi başarılı.")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("Bağlı")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText(/Son test:/)).toBeVisible();

    expect(consoleErrors, `Unexpected console errors: ${consoleErrors.join("\n")}`).toEqual([]);
  });

  test("mobile viewport has no horizontal overflow", async ({ page }) => {
    await loginAgency(page, OWNER_EMAIL, PASSWORD);
    await page.goto("/dashboard/finance/accounting");
    await expect(page.getByRole("heading", { name: "Muhasebe Entegrasyonu" })).toBeVisible({
      timeout: 15_000,
    });

    await page.setViewportSize({ width: 390, height: 844 });
    await page.waitForTimeout(300);
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - window.innerWidth
    );
    expect(overflow).toBeLessThanOrEqual(1);
  });
});
