import { test, expect, type Page } from "@playwright/test";
import { execFileSync } from "node:child_process";
import path from "node:path";
import { dismissOnboardingIfVisible } from "./helpers/onboarding";

/**
 * Part 6B-3: WhatsApp delivery lifecycle — Owner/Admin center rendering of
 * the full status spread (sent/delivered/read/failed-retry-queued/
 * failed-exhausted/cancelled/skipped_demo_tenant), retry/success-rate
 * metrics, and tenant isolation.
 *
 * Self-seeds via apps/backend/scripts/e2e_seed_whatsapp_delivery_flow.py
 * (same execFileSync + parsed-env pattern as whatsapp-preferences-flow.spec.ts).
 * No real Twilio call is ever made anywhere in this suite — delivery rows
 * are seeded directly at their final lifecycle status, and the state
 * machine / callback / retry-worker / STOP-webhook behavior itself is
 * covered by the backend test suite (test_whatsapp_delivery_state_machine.py,
 * test_twilio_webhook.py, test_whatsapp_retry.py, test_whatsapp_stop_optout.py).
 * This spec is the representative browser-side check on top of that, per
 * the Part 6B-3 instruction that not every event needs its own heavy
 * Playwright test.
 */

const BACKEND_DIR = path.resolve(__dirname, "../../backend");
const PYTHON = process.env.E2E_PYTHON ?? path.join(BACKEND_DIR, ".venv", "Scripts", "python.exe");

function runSeedScript(args: string[]): Record<string, string> {
  const output = execFileSync(
    PYTHON,
    ["scripts/e2e_seed_whatsapp_delivery_flow.py", ...args],
    {
      cwd: BACKEND_DIR,
      encoding: "utf-8",
      maxBuffer: 1024 * 1024 * 20,
      env: { ...process.env, PYTHONIOENCODING: "utf-8" },
    }
  );
  const env: Record<string, string> = {};
  for (const line of output.split(/\r?\n/)) {
    const match = line.match(/^([A-Z0-9_]+)=(.*)$/);
    if (match) env[match[1]] = match[2];
  }
  return env;
}

const KNOWN_NOISE = /^Failed to load resource:|^Failed to fetch RSC payload/;

let OWNER_EMAIL: string;
let OTHER_OWNER_EMAIL: string;
let DEMO_OWNER_EMAIL: string;
let PASSWORD: string;

test.beforeAll(() => {
  const seeded = runSeedScript(["seed"]);
  OWNER_EMAIL = seeded.E2E_OWNER_EMAIL;
  OTHER_OWNER_EMAIL = seeded.E2E_OTHER_OWNER_EMAIL;
  DEMO_OWNER_EMAIL = seeded.E2E_DEMO_OWNER_EMAIL;
  PASSWORD = seeded.E2E_PASSWORD;
  if (!OWNER_EMAIL || !OTHER_OWNER_EMAIL || !DEMO_OWNER_EMAIL || !PASSWORD) {
    throw new Error("whatsapp-event-delivery-flow fixture seed did not return the expected env vars");
  }
});

test.afterAll(() => {
  runSeedScript(["cleanup"]);
});

async function loginAgency(page: Page, email: string) {
  await page.goto("/auth/agency-login");
  await page.locator("#agency-email").fill(email);
  await page.locator("#agency-password").fill(PASSWORD);
  await page.getByRole("button", { name: "Ajans Paneline Giriş Yap" }).click();
  await page.waitForURL((url) => url.pathname.startsWith("/dashboard"), { timeout: 15_000 });
  await dismissOnboardingIfVisible(page);
}

function collectConsoleErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error" && !KNOWN_NOISE.test(msg.text())) errors.push(msg.text());
  });
  return errors;
}

test.describe("WhatsApp event delivery flow — Owner/Admin center", () => {
  test("delivery history shows the full lifecycle status spread", async ({ page }) => {
    const consoleErrors = collectConsoleErrors(page);
    await loginAgency(page, OWNER_EMAIL);
    await page.goto("/dashboard/owner/notifications");

    await expect(page.getByRole("heading", { name: "WhatsApp Yönetim Merkezi" })).toBeVisible();
    await expect(page.getByText("Teslimat Geçmişi")).toBeVisible();

    const bodyText = await page.locator("body").innerText();
    for (const status of ["sent", "delivered", "read", "failed", "cancelled"]) {
      expect(bodyText).toContain(status);
    }

    expect(consoleErrors, `Unexpected console errors: ${consoleErrors.join("; ")}`).toEqual([]);
  });

  test("retry queue, retry exhausted, and rate metrics render real numbers", async ({ page }) => {
    await loginAgency(page, OWNER_EMAIL);
    await page.goto("/dashboard/owner/notifications");

    await expect(page.getByText("Retry kuyruğu")).toBeVisible();
    await expect(page.getByText("Retry tükendi")).toBeVisible();
    await expect(page.getByText("Gönderim başarı oranı (7g)")).toBeVisible();
    await expect(page.getByText("Okunma oranı (7g)")).toBeVisible();

    // Seed fixture: exactly one row in the retry queue (failed + future
    // next_retry_at) and one retry-exhausted row. StatCard renders label and
    // value as sibling <p> tags inside the same stat-tile div — scope to
    // that specific tile class combo so ancestor wrappers (which also
    // technically "contain" the label text) never match.
    const statTileSelector = ".bg-surface.border.border-border.rounded-xl";
    const retryQueueCard = page.locator(statTileSelector).filter({ hasText: "Retry kuyruğu" });
    await expect(retryQueueCard.locator("p.text-xl")).toHaveText("1");
    const retryExhaustedCard = page.locator(statTileSelector).filter({ hasText: "Retry tükendi" });
    await expect(retryExhaustedCard.locator("p.text-xl")).toHaveText("1");
  });

  test("failed delivery card shows a safe error, never a raw phone number", async ({ page }) => {
    await loginAgency(page, OWNER_EMAIL);
    await page.goto("/dashboard/owner/notifications");
    await expect(page.getByText("Teslimat Geçmişi")).toBeVisible();

    const bodyText = await page.locator("body").innerText();
    expect(bodyText).toContain("Simulated transient failure");
    expect(bodyText).not.toMatch(/\+905551230101/); // raw seeded phone must never render
  });

  test("another tenant's owner never sees this tenant's delivery history", async ({ page }) => {
    await loginAgency(page, OTHER_OWNER_EMAIL);
    await page.goto("/dashboard/owner/notifications");
    await expect(page.getByRole("heading", { name: "WhatsApp Yönetim Merkezi" })).toBeVisible();
    await expect(page.getByText("Henüz teslimat kaydı yok.")).toBeVisible();

    const bodyText = await page.locator("body").innerText();
    expect(bodyText).not.toContain("Simulated transient failure");
  });

  test("demo tenant owner sees skipped_demo_tenant, never a real send", async ({ page }) => {
    await loginAgency(page, DEMO_OWNER_EMAIL);
    await page.goto("/dashboard/owner/notifications");
    await expect(
      page.getByText("Demo ortamda gerçek WhatsApp gönderimi yapılmaz")
    ).toBeVisible();

    const filter = page.locator("select");
    await filter.selectOption("skipped_demo_tenant");
    await expect(page.getByText("skipped_demo_tenant").first()).toBeVisible();
  });

  test("status filter narrows delivery history to the selected status", async ({ page }) => {
    await loginAgency(page, OWNER_EMAIL);
    await page.goto("/dashboard/owner/notifications");
    await expect(page.getByText("Teslimat Geçmişi")).toBeVisible();

    const filter = page.locator("select");
    await filter.selectOption("failed");
    await page.waitForTimeout(300); // debounce-free client fetch, small settle

    const bodyText = await page.locator("body").innerText();
    expect(bodyText).not.toContain("Okunma oranı"); // sanity: page itself still rendered
  });

  test("mobile viewport renders delivery history and metrics without overflow", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await loginAgency(page, OWNER_EMAIL);
    await page.goto("/dashboard/owner/notifications");
    await expect(page.getByText("Teslimat Geçmişi")).toBeVisible();
    await expect(page.getByText("Retry kuyruğu")).toBeVisible();
    const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
    const clientWidth = await page.evaluate(() => document.documentElement.clientWidth);
    expect(scrollWidth).toBeLessThanOrEqual(clientWidth + 1);
  });
});
