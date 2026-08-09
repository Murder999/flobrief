import { test, expect, type Page } from "@playwright/test";
import { execFileSync } from "node:child_process";
import path from "node:path";
import { dismissOnboardingIfVisible } from "./helpers/onboarding";

/**
 * Part 6B-2: per-event WhatsApp preferences, consent, and the Owner/Admin
 * WhatsApp management center.
 *
 * Self-seeds via apps/backend/scripts/e2e_seed_whatsapp_preferences_flow.py
 * (same execFileSync + parsed-env pattern as whatsapp-connection-flow.spec.ts).
 */

const BACKEND_DIR = path.resolve(__dirname, "../../backend");
const PYTHON = process.env.E2E_PYTHON ?? path.join(BACKEND_DIR, ".venv", "Scripts", "python.exe");

function runSeedScript(args: string[]): Record<string, string> {
  const output = execFileSync(
    PYTHON,
    ["scripts/e2e_seed_whatsapp_preferences_flow.py", ...args],
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

let OWNER_A_EMAIL: string;
let OWNER_B_EMAIL: string;
let BRAND_MANAGER_EMAIL: string;
let DEMO_OWNER_EMAIL: string;
let PASSWORD: string;

test.beforeAll(() => {
  const seeded = runSeedScript(["seed"]);
  OWNER_A_EMAIL = seeded.E2E_OWNER_A_EMAIL;
  OWNER_B_EMAIL = seeded.E2E_OWNER_B_EMAIL;
  BRAND_MANAGER_EMAIL = seeded.E2E_BRAND_MANAGER_EMAIL;
  DEMO_OWNER_EMAIL = seeded.E2E_DEMO_OWNER_EMAIL;
  PASSWORD = seeded.E2E_PASSWORD;
  if (!OWNER_A_EMAIL || !OWNER_B_EMAIL || !BRAND_MANAGER_EMAIL || !DEMO_OWNER_EMAIL || !PASSWORD) {
    throw new Error("whatsapp-preferences-flow fixture seed did not return the expected env vars");
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

async function loginBrand(page: Page, email: string) {
  await page.goto("/brand/login");
  await page.locator("#brand-email").fill(email);
  await page.locator("#brand-password").fill(PASSWORD);
  await page.getByRole("button", { name: "Marka Portalına Giriş Yap" }).click();
  // "/brand/login" itself already satisfies a bare startsWith("/brand")
  // predicate, so waitForURL can resolve before the post-login redirect
  // actually happens — exclude it explicitly, matching the convention in
  // mobile-brand-approval-flow.spec.ts / mobile-navigation.spec.ts.
  await page.waitForURL((url) => url.pathname.startsWith("/brand") && url.pathname !== "/brand/login", {
    timeout: 15_000,
  });
}

function collectConsoleErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error" && !KNOWN_NOISE.test(msg.text())) errors.push(msg.text());
  });
  return errors;
}

test.describe("WhatsApp preferences flow — agency user settings", () => {
  test("owner sees masked phone and no secret on the notifications settings page", async ({
    page,
  }) => {
    const consoleErrors = collectConsoleErrors(page);
    await loginAgency(page, OWNER_A_EMAIL);
    await page.goto("/dashboard/settings/notifications");

    await expect(page.getByRole("heading", { name: "Bildirim Tercihleri" })).toBeVisible();
    await expect(page.getByText("WhatsApp Bildirimleri")).toBeVisible();

    const bodyText = await page.locator("body").innerText();
    expect(bodyText).not.toContain("+905551230001"); // raw seeded phone must never render
    expect(bodyText.toLowerCase()).not.toContain("auth_token");
    expect(bodyText.toLowerCase()).not.toContain("content_sid");

    expect(consoleErrors, `Unexpected console errors: ${consoleErrors.join("; ")}`).toEqual([]);
  });

  test("consent modal shows explanation text and opening it enables event groups", async ({
    page,
  }) => {
    await loginAgency(page, OWNER_A_EMAIL);
    await page.goto("/dashboard/settings/notifications");

    const masterToggle = page.getByRole("switch", { name: "WhatsApp bildirimlerini aç/kapat" });
    await expect(masterToggle).toBeVisible();

    // If already on from a previous run in this worker, opt out first so the
    // consent-modal flow below is exercised deterministically.
    if ((await masterToggle.getAttribute("aria-checked")) === "true") {
      await masterToggle.click();
      await expect(masterToggle).toHaveAttribute("aria-checked", "false");
    }

    await masterToggle.click();
    await expect(page.getByRole("heading", { name: "WhatsApp Bildirim Onayı" })).toBeVisible();
    await expect(page.getByText("İstediğiniz zaman bu ayarı kapatabilirsiniz.")).toBeVisible();
    await expect(page.getByText("Demo ortamlarda gerçek bir mesaj gönderilmez.")).toBeVisible();

    await page.getByRole("button", { name: "Onaylıyorum, Aç" }).click();
    await expect(page.getByRole("heading", { name: "WhatsApp Bildirim Onayı" })).not.toBeVisible();
    await expect(masterToggle).toHaveAttribute("aria-checked", "true");

    // Event groups become visible once the master toggle is on.
    await expect(page.getByText("İş ve Brief")).toBeVisible();
    await expect(page.getByText("Yorum ve İş Birliği")).toBeVisible();
  });

  test("event toggle persists after refresh", async ({ page }) => {
    await loginAgency(page, OWNER_A_EMAIL);
    await page.goto("/dashboard/settings/notifications");

    const masterToggle = page.getByRole("switch", { name: "WhatsApp bildirimlerini aç/kapat" });
    if ((await masterToggle.getAttribute("aria-checked")) !== "true") {
      await masterToggle.click();
      await page.getByRole("button", { name: "Onaylıyorum, Aç" }).click();
      await expect(masterToggle).toHaveAttribute("aria-checked", "true");
    }

    const eventToggle = page.getByRole("switch", { name: "Yeni brief oluşturuldu" });
    await expect(eventToggle).toBeVisible();
    const before = await eventToggle.getAttribute("aria-checked");
    await eventToggle.click();
    await expect(eventToggle).not.toHaveAttribute("aria-checked", before ?? "");

    await page.reload();
    const afterReload = page.getByRole("switch", { name: "Yeni brief oluşturuldu" });
    await expect(afterReload).not.toHaveAttribute("aria-checked", before ?? "");
  });

  test("master toggle off hides the event groups", async ({ page }) => {
    await loginAgency(page, OWNER_A_EMAIL);
    await page.goto("/dashboard/settings/notifications");

    const masterToggle = page.getByRole("switch", { name: "WhatsApp bildirimlerini aç/kapat" });
    if ((await masterToggle.getAttribute("aria-checked")) === "true") {
      await masterToggle.click();
      await expect(masterToggle).toHaveAttribute("aria-checked", "false");
    }
    await expect(page.getByText("İş ve Brief")).not.toBeVisible();
  });

  test("missing-template state is shown honestly, not as fake ready", async ({ page }) => {
    await loginAgency(page, OWNER_A_EMAIL);
    await page.goto("/dashboard/settings/notifications");

    const masterToggle = page.getByRole("switch", { name: "WhatsApp bildirimlerini aç/kapat" });
    if ((await masterToggle.getAttribute("aria-checked")) !== "true") {
      await masterToggle.click();
      await page.getByRole("button", { name: "Onaylıyorum, Aç" }).click();
    }
    // brief.overdue has no approved template in this fixture — must show the
    // "not ready" note, never a fabricated success state.
    await expect(page.getByText("Şablon henüz hazır değil").first()).toBeVisible();
  });

  test("mobile viewport has no horizontal overflow on the settings page", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await loginAgency(page, OWNER_A_EMAIL);
    await page.goto("/dashboard/settings/notifications");
    const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
    const clientWidth = await page.evaluate(() => document.documentElement.clientWidth);
    expect(scrollWidth).toBeLessThanOrEqual(clientWidth + 1);
  });
});

test.describe("WhatsApp preferences flow — Owner/Admin management center", () => {
  test("owner sees connection status, template matrix, and delivery summary", async ({ page }) => {
    const consoleErrors = collectConsoleErrors(page);
    await loginAgency(page, OWNER_A_EMAIL);
    await page.goto("/dashboard/owner/notifications");

    await expect(page.getByRole("heading", { name: "WhatsApp Yönetim Merkezi" })).toBeVisible();
    await expect(page.getByText("Event–Şablon Matrisi")).toBeVisible();
    await expect(page.getByText("Teslimat Geçmişi")).toBeVisible();

    const bodyText = await page.locator("body").innerText();
    expect(bodyText.toLowerCase()).not.toContain("auth_token");
    expect(bodyText).not.toMatch(/HXe2efakecontentsid/); // real content_sid value never rendered

    expect(consoleErrors, `Unexpected console errors: ${consoleErrors.join("; ")}`).toEqual([]);
  });

  test("template preview shows placeholder data only", async ({ page }) => {
    await loginAgency(page, OWNER_A_EMAIL);
    await page.goto("/dashboard/owner/notifications");

    await page.getByRole("button", { name: "Önizle →" }).first().click();
    await expect(page.getByText("Bu önizleme örnek/placeholder verilerle")).toBeVisible();
  });

  test("another tenant's owner never sees this tenant's delivery history", async ({ page }) => {
    await loginAgency(page, OWNER_B_EMAIL);
    await page.goto("/dashboard/owner/notifications");
    await expect(page.getByRole("heading", { name: "WhatsApp Yönetim Merkezi" })).toBeVisible();
    await expect(page.getByText("Henüz teslimat kaydı yok.")).toBeVisible();
  });

  test("demo tenant owner test-send is honestly reported as skipped", async ({ page }) => {
    await loginAgency(page, DEMO_OWNER_EMAIL);
    await page.goto("/dashboard/owner/notifications");

    const testButton = page.getByRole("button", { name: /Test Mesajı Gönder/ });
    await testButton.click();
    // The same status string legitimately renders in 4 places once a
    // delivery exists (24h/7d summary chips, this result panel, and the
    // delivery-history card) — scope to the result panel's own <code> (the
    // only <code> element WhatsAppOwnerCenter renders) so this asserts the
    // specific "the send I just triggered was skipped" feedback, not an
    // ambiguous page-wide text match.
    await expect(page.locator("code", { hasText: "skipped_demo_tenant" })).toBeVisible({
      timeout: 10_000,
    });
  });

  test("mobile viewport renders template matrix and delivery history as cards, no overflow", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await loginAgency(page, OWNER_A_EMAIL);
    await page.goto("/dashboard/owner/notifications");
    await expect(page.getByText("Event–Şablon Matrisi")).toBeVisible();
    const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
    const clientWidth = await page.evaluate(() => document.documentElement.clientWidth);
    expect(scrollWidth).toBeLessThanOrEqual(clientWidth + 1);
  });
});

test.describe("WhatsApp preferences flow — brand portal", () => {
  test("brand user sees the WhatsApp settings tab without finance/internal events", async ({
    page,
  }) => {
    const consoleErrors = collectConsoleErrors(page);
    await loginBrand(page, BRAND_MANAGER_EMAIL);
    await page.goto("/brand/notifications?tab=settings");

    await expect(page.getByText("WhatsApp Bildirimleri")).toBeVisible();
    const bodyText = await page.locator("body").innerText();
    expect(bodyText).not.toContain("Ödeme alındı"); // agency-only finance event

    expect(consoleErrors, `Unexpected console errors: ${consoleErrors.join("; ")}`).toEqual([]);
  });

  test("brand user mobile viewport has no horizontal overflow", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });
    await loginBrand(page, BRAND_MANAGER_EMAIL);
    await page.goto("/brand/notifications?tab=settings");
    await expect(page.getByText("WhatsApp Bildirimleri")).toBeVisible();
    const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
    const clientWidth = await page.evaluate(() => document.documentElement.clientWidth);
    expect(scrollWidth).toBeLessThanOrEqual(clientWidth + 1);
  });
});
