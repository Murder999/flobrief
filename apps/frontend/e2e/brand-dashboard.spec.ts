import { test, expect, type Page } from "@playwright/test";
import { execFileSync } from "node:child_process";
import path from "node:path";

/**
 * Regression suite for the redesigned brand-portal overview dashboard
 * (apps/frontend/app/brand/dashboard/page.tsx): compact 4-card KPI row,
 * the action-queue cap (4, "Tum N aksiyonu gor" beyond that), Son Briefler /
 * Son Hareketler row caps (5), Turkish labels (no raw status enums leaking
 * to the UI), deep-link navigation, and no horizontal overflow on
 * tablet/mobile.
 *
 * Fixture is seeded via apps/backend/scripts/e2e_seed_brand_dashboard.py
 * (real briefs/notifications via the DB, no mocking) so this spec never
 * touches production data.
 */

const PASSWORD = "E2eTest1234!";
const BACKEND_DIR = path.resolve(__dirname, "../../backend");
const PYTHON = process.env.E2E_PYTHON ?? path.join(BACKEND_DIR, ".venv", "Scripts", "python.exe");

let BRAND_EMAIL: string;
let AGENCY_ID: string;
let ACTION_BRIEF_ID: string;
let APPROVED_BRIEF_ID: string;

function runSeedScript(args: string[]): Record<string, string> {
  const output = execFileSync(PYTHON, ["scripts/e2e_seed_brand_dashboard.py", ...args], {
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
  BRAND_EMAIL = env.E2E_BRAND_EMAIL;
  AGENCY_ID = env.__AGENCY_ID__;
  ACTION_BRIEF_ID = env.E2E_ACTION_BRIEF_ID;
  APPROVED_BRIEF_ID = env.E2E_APPROVED_BRIEF_ID;
  if (!BRAND_EMAIL || !ACTION_BRIEF_ID) {
    throw new Error("brand-dashboard fixture seed did not return the expected env vars");
  }
});

test.afterAll(() => {
  if (AGENCY_ID) runSeedScript(["cleanup", AGENCY_ID]);
});

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

async function gotoDashboard(page: Page) {
  await loginBrand(page);
  if (!page.url().includes("/brand/dashboard")) {
    await page.goto("/brand/dashboard");
  }
  // "E2E Onay Bekleyen Brief 1" legitimately appears twice (Aksiyon Bekleyenlerim
  // + Son Briefler are different-purpose sections, per design) so wait on a
  // section heading instead of the ambiguous brief text.
  await expect(page.getByRole("heading", { name: "Aksiyon Bekleyenlerim" })).toBeVisible({ timeout: 15_000 });
}

test.describe("brand dashboard redesign", () => {
  test("renders all critical sections within 1440x900 with no excessive scroll", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await gotoDashboard(page);

    await expect(page.getByRole("heading", { name: "Aksiyon Bekleyenlerim" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Bu Hafta" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Son Briefler" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Son Hareketler" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Hızlı İşlemler" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Operasyon Sağlığı" })).toBeVisible();

    const scrollHeight = await page.evaluate(() => document.documentElement.scrollHeight);
    expect(scrollHeight).toBeLessThanOrEqual(900 * 1.3);
  });

  test("KPI row shows exactly 4 consolidated cards", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await gotoDashboard(page);

    await expect(page.getByText("Toplam Brief")).toBeVisible();
    await expect(page.getByText("Onay Süreci")).toBeVisible();
    await expect(page.getByText("Revizyon", { exact: true })).toBeVisible();
    await expect(page.getByText("Onaylanan", { exact: true })).toBeVisible();
  });

  test("action queue caps at 4 rows and shows a see-all link for the rest", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await gotoDashboard(page);

    // 6 "ready_for_review" briefs (5 seeded in the loop + the this-week one) +
    // 1 overdue legacy "in_review" brief = 7 actionable items total.
    const actionCard = page.getByRole("heading", { name: "Aksiyon Bekleyenlerim" }).locator("..").locator("..").locator("..");
    const rows = actionCard.locator("a[href^='/brand/briefs/']");
    await expect(rows).toHaveCount(4);
    await expect(page.getByText(/Tüm 7 aksiyonu gör/)).toBeVisible();
  });

  test("Son Briefler shows at most 5 rows with no duplicate titles", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await gotoDashboard(page);

    const briefsCard = page.getByRole("heading", { name: "Son Briefler" }).locator("..").locator("..");
    const rows = briefsCard.locator("a[href^='/brand/briefs/']");
    const count = await rows.count();
    expect(count).toBeLessThanOrEqual(5);

    const titles = await rows.allTextContents();
    expect(new Set(titles).size).toBe(titles.length);
  });

  test("Son Hareketler shows at most 5 rows and is clickable to the source brief", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await gotoDashboard(page);

    const activityCard = page.getByRole("heading", { name: "Son Hareketler" }).locator("..").locator("..");
    const rows = activityCard.locator("button");
    const count = await rows.count();
    expect(count).toBeLessThanOrEqual(5);

    await page.getByText("Brief onaylandi").click();
    await page.waitForURL((url) => url.pathname === `/brand/briefs/${APPROVED_BRIEF_ID}`, { timeout: 10_000 });
  });

  test("no raw status enum leaks into the UI", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await gotoDashboard(page);

    const bodyText = await page.locator("body").innerText();
    expect(bodyText).not.toContain("ready_for_review");
    expect(bodyText).not.toContain("revision_requested");
    expect(bodyText).not.toContain("in_review");
    expect(bodyText).not.toContain("in_production");
  });

  test("action row navigates to the correct brief", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await gotoDashboard(page);

    await page.locator(`a[href="/brand/briefs/${ACTION_BRIEF_ID}"]`).first().click();
    await page.waitForURL((url) => url.pathname === `/brand/briefs/${ACTION_BRIEF_ID}`, { timeout: 10_000 });
  });

  test("quick actions and calendar link navigate correctly", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await gotoDashboard(page);

    const main = page.getByRole("main");
    await expect(main.getByRole("link", { name: /Onayları İncele/ })).toHaveAttribute("href", "/brand/approvals");
    await expect(main.getByRole("link", { name: /Takvimi Gör/ })).toHaveAttribute("href", "/brand/calendar");
    await expect(main.getByRole("link", { name: /Dosyalar/ })).toHaveAttribute("href", "/brand/files");
    await expect(page.getByRole("link", { name: "Tümünü gör" })).toHaveAttribute("href", "/brand/calendar");
  });

  for (const [label, size] of [
    ["tablet", { width: 834, height: 1112 }],
    ["mobile", { width: 390, height: 844 }],
  ] as const) {
    test(`no horizontal overflow on ${label}`, async ({ page }) => {
      await page.setViewportSize(size);
      await gotoDashboard(page);
      const [scrollWidth, clientWidth] = await page.evaluate(() => [
        document.documentElement.scrollWidth,
        document.documentElement.clientWidth,
      ]);
      expect(scrollWidth).toBeLessThanOrEqual(clientWidth + 1);
    });
  }
});
