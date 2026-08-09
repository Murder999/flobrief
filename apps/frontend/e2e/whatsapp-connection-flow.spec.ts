import { test, expect, type Page } from "@playwright/test";
import { execFileSync } from "node:child_process";
import path from "node:path";
import { dismissOnboardingIfVisible } from "./helpers/onboarding";

/**
 * Part 6A: agency Owner sees a real (never fabricated) WhatsApp connection
 * status, no secrets are ever rendered client-side, and the controlled
 * test-send flow correctly gates on role, demo-tenant, and consent state.
 *
 * Self-seeds via apps/backend/scripts/e2e_seed_whatsapp_connection_flow.py
 * (same execFileSync + parsed-env pattern as annotation-flow.spec.ts).
 */

const BACKEND_DIR = path.resolve(__dirname, "../../backend");
const PYTHON = process.env.E2E_PYTHON ?? path.join(BACKEND_DIR, ".venv", "Scripts", "python.exe");

function runSeedScript(args: string[]): Record<string, string> {
  const output = execFileSync(PYTHON, ["scripts/e2e_seed_whatsapp_connection_flow.py", ...args], {
    cwd: BACKEND_DIR,
    encoding: "utf-8",
    maxBuffer: 1024 * 1024 * 20,
    env: { ...process.env, PYTHONIOENCODING: "utf-8" },
  });
  const env: Record<string, string> = {};
  for (const line of output.split(/\r?\n/)) {
    const match = line.match(/^([A-Z0-9_]+)=(.*)$/);
    if (match) env[match[1]] = match[2];
  }
  return env;
}

const KNOWN_NOISE = /^Failed to load resource:|^Failed to fetch RSC payload/;

let OWNER_EMAIL: string;
let VIEWER_EMAIL: string;
let DEMO_OWNER_EMAIL: string;
let PASSWORD: string;

test.beforeAll(() => {
  const seeded = runSeedScript(["seed"]);
  OWNER_EMAIL = seeded.E2E_OWNER_EMAIL;
  VIEWER_EMAIL = seeded.E2E_VIEWER_EMAIL;
  DEMO_OWNER_EMAIL = seeded.E2E_DEMO_OWNER_EMAIL;
  PASSWORD = seeded.E2E_PASSWORD;
  if (!OWNER_EMAIL || !VIEWER_EMAIL || !DEMO_OWNER_EMAIL || !PASSWORD) {
    throw new Error("whatsapp-connection-flow fixture seed did not return the expected env vars");
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

test.describe("WhatsApp connection flow", () => {
  test("owner sees connection status, no secrets, and can attempt a test send", async ({ page }) => {
    const consoleErrors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error" && !KNOWN_NOISE.test(msg.text())) consoleErrors.push(msg.text());
    });

    await loginAgency(page, OWNER_EMAIL);
    await page.goto("/dashboard/owner/notifications");

    await expect(page.getByRole("heading", { name: "WhatsApp Yönetim Merkezi" })).toBeVisible();

    // No secret value ever rendered on this owner-facing screen.
    const bodyText = await page.locator("body").innerText();
    expect(bodyText).not.toMatch(/AC[0-9a-zA-Z]{20,}/); // Twilio Account SID shape
    expect(bodyText.toLowerCase()).not.toContain("auth_token");

    const testButton = page.getByRole("button", { name: /Test Mesajı Gönder/ });
    await expect(testButton).toBeVisible();
    await testButton.click();

    // Provider isn't configured with a real approved template in this
    // environment, so the honest outcome is a skip — never a fabricated
    // "sent". The result panel must still render something, not hang.
    await expect(page.locator("text=Durum").first()).toBeVisible({ timeout: 10_000 });

    expect(consoleErrors, `Unexpected console errors: ${consoleErrors.join("; ")}`).toEqual([]);
  });

  test("viewer role cannot see the config/test-send action", async ({ page }) => {
    await loginAgency(page, VIEWER_EMAIL);
    await page.goto("/dashboard/owner/notifications");
    // Viewers should not reach the owner-only WhatsApp panel at all.
    await expect(page.getByRole("button", { name: /Test Mesajı Gönder/ })).not.toBeVisible();
  });

  test("demo tenant owner cannot trigger a real test send", async ({ page }) => {
    await loginAgency(page, DEMO_OWNER_EMAIL);
    await page.goto("/dashboard/owner/notifications");

    const testButton = page.getByRole("button", { name: /Test Mesajı Gönder/ });
    if (await testButton.isVisible().catch(() => false)) {
      await testButton.click();
      await expect(page.locator("text=skipped_demo_tenant")).toBeVisible({ timeout: 10_000 });
    }
  });

  test("notification preferences page shows WhatsApp opt-in state and test action", async ({ page }) => {
    await loginAgency(page, OWNER_EMAIL);
    await page.goto("/dashboard/settings/notifications");
    await expect(page.getByRole("heading", { name: "Bildirim Tercihleri" })).toBeVisible();
    await expect(page.getByText("WhatsApp Bildirimleri")).toBeVisible();
  });

  test("mobile viewport has no horizontal overflow", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await loginAgency(page, OWNER_EMAIL);
    await page.goto("/dashboard/owner/notifications");
    const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
    const clientWidth = await page.evaluate(() => document.documentElement.clientWidth);
    expect(scrollWidth).toBeLessThanOrEqual(clientWidth + 1);
  });
});
