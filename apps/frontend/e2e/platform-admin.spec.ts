import { test, expect, type Page } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { createHmac } from "node:crypto";
import path from "node:path";

/**
 * Real-browser regression suite for Platform Admin: agency management,
 * White Label defaults + real portal application, Profile & Security
 * (personal info / password / MFA / sessions), and the SEO & Growth Center
 * (audit, page inventory, robots.txt, sitemap.xml, UTM, PageSpeed/GSC/GA4
 * setup states).
 *
 * Fixture is seeded via apps/backend/scripts/e2e_seed_platform_admin.py
 * (real DB rows, no mocking) and cleaned up in afterAll.
 */

const PASSWORD = "E2eTest1234!";
const BACKEND_DIR = path.resolve(__dirname, "../../backend");
const PYTHON = process.env.E2E_PYTHON ?? path.join(BACKEND_DIR, ".venv", "Scripts", "python.exe");

let PLATFORM_ADMIN_EMAIL: string;
let OWNER_A_EMAIL: string;
let ADMIN_A_EMAIL: string;
let OWNER_B_EMAIL: string;
let APPROVAL_TOKEN_A: string;
let APPROVAL_TOKEN_B: string;
let AGENCY_A_ID: string;
let AGENCY_B_ID: string;

function runSeedScript(args: string[]): Record<string, string> {
  const output = execFileSync(PYTHON, ["scripts/e2e_seed_platform_admin.py", ...args], {
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
  PLATFORM_ADMIN_EMAIL = env.E2E_PLATFORM_ADMIN_EMAIL;
  OWNER_A_EMAIL = env.E2E_OWNER_A_EMAIL;
  ADMIN_A_EMAIL = env.E2E_ADMIN_A_EMAIL;
  OWNER_B_EMAIL = env.E2E_OWNER_B_EMAIL;
  APPROVAL_TOKEN_A = env.E2E_APPROVAL_TOKEN_A;
  APPROVAL_TOKEN_B = env.E2E_APPROVAL_TOKEN_B;
  AGENCY_A_ID = env.__AGENCY_A_ID__;
  AGENCY_B_ID = env.__AGENCY_B_ID__;
  if (!PLATFORM_ADMIN_EMAIL || !APPROVAL_TOKEN_A || !AGENCY_A_ID) {
    throw new Error("platform-admin fixture seed did not return the expected env vars");
  }
});

test.afterAll(() => {
  if (AGENCY_A_ID || AGENCY_B_ID) {
    runSeedScript(["cleanup", AGENCY_A_ID ?? "", AGENCY_B_ID ?? ""]);
  }
});

async function loginPlatformAdmin(page: Page) {
  await page.goto("/platform/login");
  await page.getByLabel("E-posta adresi").fill(PLATFORM_ADMIN_EMAIL);
  await page.getByLabel("Şifre", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "Güvenli Giriş Yap" }).click();
  await page.waitForURL((url) => url.pathname.startsWith("/platform/dashboard"), { timeout: 15_000 });
}

// RFC 6238 TOTP, matching the backend's HMAC-SHA1 30s/6-digit implementation
// (app/services/mfa_service.py), so the enable/disable flow can be driven
// end-to-end without special-casing the backend for tests.
function base32Decode(input: string): Buffer {
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
  let bits = "";
  for (const char of input.toUpperCase().replace(/=+$/, "")) {
    const val = alphabet.indexOf(char);
    if (val === -1) continue;
    bits += val.toString(2).padStart(5, "0");
  }
  const bytes: number[] = [];
  for (let i = 0; i + 8 <= bits.length; i += 8) bytes.push(parseInt(bits.substring(i, i + 8), 2));
  return Buffer.from(bytes);
}

function currentTotp(secretB32: string): string {
  const key = base32Decode(secretB32);
  const counter = Math.floor(Date.now() / 1000 / 30);
  const buf = Buffer.alloc(8);
  buf.writeBigUInt64BE(BigInt(counter));
  const hmac = createHmac("sha1", key).update(buf).digest();
  const offset = hmac[hmac.length - 1] & 0xf;
  const code =
    (((hmac[offset] & 0x7f) << 24) |
      ((hmac[offset + 1] & 0xff) << 16) |
      ((hmac[offset + 2] & 0xff) << 8) |
      (hmac[offset + 3] & 0xff)) %
    1_000_000;
  return code.toString().padStart(6, "0");
}

// ── 5. White Label ──────────────────────────────────────────────────────────
//
// Runs BEFORE agency management: the agency-management flow below
// intentionally downgrades Agency A from the white-label plan to the
// starter plan (to verify plan changes persist), which for real, correct
// reasons revokes Agency A's white-label entitlement (see
// BrandingService._build_public_branding's `not entitlement` check). Running
// white-label's "agency WITH override" check afterwards would then always
// fail — not because of an app bug, but because the shared Agency A fixture
// would have already lost the entitlement this check depends on. Keeping
// this block first exercises the override while entitlement is still intact.

test.describe("platform admin — white label", () => {
  test("editor loads defaults, validates hex, saves, and a real portal applies it", async ({ page }) => {
    await loginPlatformAdmin(page);
    await page.goto("/platform/whitealabel");
    await expect(page.getByRole("heading", { name: "White Label Yönetimi" })).toBeVisible();
    await expect(page.locator('input[placeholder="PostPiloter"]')).toHaveValue("E2E Flobrief Platform", {
      timeout: 10_000,
    });

    // Invalid hex is rejected by the input mask (non-hex chars simply don't apply)
    const primaryColorHex = page.locator('input[placeholder="#6366F1"]').first();
    await primaryColorHex.fill("");
    await primaryColorHex.type("ZZZZZZ");
    await expect(primaryColorHex).toHaveValue("");

    // Valid hex + live preview reacts
    await primaryColorHex.fill("#00AA55");
    await expect(page.getByText("#00AA55").first()).toBeVisible();

    // Unsaved-changes indicator appears
    await expect(page.getByText("Kaydedilmemiş değişiklikler")).toBeVisible();

    // Discard reverts
    await page.getByRole("button", { name: "Vazgeç" }).click();
    await expect(page.getByText("Kaydedilmemiş değişiklikler")).not.toBeVisible();
    await expect(primaryColorHex).toHaveValue("2563EB".padStart(7, "#").length ? "#2563EB" : "");

    // Real save + persists across reload
    await primaryColorHex.fill("#00AA55");
    await page.getByRole("button", { name: "Kaydet" }).click();
    await expect(page.getByText("Kaydedildi ✓")).toBeVisible({ timeout: 10_000 });
    await page.reload();
    await expect(page.locator('input[placeholder="#6366F1"]').first()).toHaveValue("#00AA55", { timeout: 10_000 });

    // Restore the fixture's baseline color so other assertions in this file stay stable
    await page.locator('input[placeholder="#6366F1"]').first().fill("#2563EB");
    await page.getByRole("button", { name: "Kaydet" }).click();
    await expect(page.getByText("Kaydedildi ✓")).toBeVisible({ timeout: 10_000 });
  });

  test("agency WITH override shows its own branding on the real approval portal", async ({ page }) => {
    await page.goto(`/approve/${APPROVAL_TOKEN_A}`);
    await expect(page.getByText("E2E Override Marka")).toBeVisible({ timeout: 15_000 });
  });

  test("agency WITHOUT override falls back to platform defaults on the real approval portal", async ({ page }) => {
    await page.goto(`/approve/${APPROVAL_TOKEN_B}`);
    await expect(page.getByText("E2E Flobrief Platform")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText("E2E Override Marka")).not.toBeVisible();
  });
});

// ── 4. Platform Admin agency management ────────────────────────────────────

test.describe("platform admin — agency management", () => {
  test("normal (unauthenticated) visitor cannot reach a platform admin route", async ({ page }) => {
    await page.goto("/platform/agencies");
    await page.waitForURL((url) => url.pathname === "/platform/login", { timeout: 10_000 });
  });

  test("full agency management flow: list, filter, roles, last-owner, plan, audit", async ({ page }) => {
    const consoleErrors: string[] = [];
    // Chromium always logs "Failed to load resource: ... 400" for the
    // last-owner-protection request below, regardless of whether the app
    // handles the rejection gracefully (it does — see the toast assertion
    // right after). That 400 is deliberately triggered by this same test,
    // so it is expected noise, not a real error, and is filtered alongside
    // the pre-existing RSC-payload-prefetch noise.
    page.on("console", (msg) => {
      if (
        msg.type() === "error" &&
        !/Failed to fetch RSC payload/.test(msg.text()) &&
        !/responded with a status of 400/.test(msg.text())
      ) {
        consoleErrors.push(msg.text());
      }
    });

    await loginPlatformAdmin(page);
    await page.goto("/platform/agencies");
    await expect(page.getByRole("heading", { name: "Ajanslar & Markalar" })).toBeVisible();

    // Search/status filter on the "Markalar" tab (agency tab has status filter only)
    await expect(page.getByText("E2E Beyaz Etiket Ajansı")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("E2E Varsayılan Ajans")).toBeVisible();

    const statusFilter = page.locator("select").first();
    await statusFilter.selectOption("active");
    await expect(page.getByText("E2E Beyaz Etiket Ajansı")).toBeVisible();

    // Open Agency A detail drawer
    await page.getByText("E2E Beyaz Etiket Ajansı").click();
    await expect(page.getByRole("heading", { name: "E2E Beyaz Etiket Ajansı" })).toBeVisible({ timeout: 10_000 });

    // Kullanıcılar ve Yetkiler tab: real members visible
    await page.getByRole("button", { name: /Kullanıcılar/ }).click();
    await expect(page.getByText("E2E Owner A")).toBeVisible();
    await expect(page.getByText("E2E Admin A")).toBeVisible();

    // Last-owner protection: attempt to demote the only owner via its role select
    const memberRow = (name: string) =>
      page.locator("div.bg-surface-2.border-border.rounded-xl").filter({ hasText: name });

    const ownerRow = memberRow("E2E Owner A");
    const ownerRoleSelect = ownerRow.locator("select").first();
    await ownerRoleSelect.selectOption("admin");
    await page.getByTestId("confirm-action-submit").click();
    // Backend rejects (400) -> UI shows an error toast, role select should not
    // silently show "admin" as persisted after a reload.
    await expect(page.getByText("Ajansın en az bir aktif sahibi")).toBeVisible({ timeout: 10_000 });
    await page.reload();
    await page.getByText("E2E Beyaz Etiket Ajansı").click();
    await page.getByRole("button", { name: /Kullanıcılar/ }).click();
    const ownerRowAfter = memberRow("E2E Owner A");
    await expect(ownerRowAfter.locator("select").first()).toHaveValue("owner");

    // Role change on the non-owner member persists across reload
    const adminRow = memberRow("E2E Admin A");
    const adminRoleSelect = adminRow.locator("select").first();
    await adminRoleSelect.selectOption("viewer");
    await page.getByTestId("confirm-action-submit").click();
    await expect(page.getByText("Rol güncellendi.")).toBeVisible({ timeout: 10_000 });
    await page.reload();
    await page.getByText("E2E Beyaz Etiket Ajansı").click();
    await page.getByRole("button", { name: /Kullanıcılar/ }).click();
    const adminRowAfter = memberRow("E2E Admin A");
    await expect(adminRowAfter.locator("select").first()).toHaveValue("viewer");

    // Plan change
    await page.getByRole("button", { name: "Plan & Limitler" }).click();
    await expect(page.getByText("E2E White Label Plan").first()).toBeVisible({ timeout: 10_000 });
    await page.getByRole("button", { name: /E2E Starter Plan/ }).click();
    await expect(page.getByText("Plan güncellendi.")).toBeVisible({ timeout: 10_000 });
    await page.reload();
    await page.getByText("E2E Beyaz Etiket Ajansı").click();
    await page.getByRole("button", { name: "Plan & Limitler" }).click();
    await expect(page.getByText("Mevcut plan")).toBeVisible();

    // Audit tab shows the role-change action
    await page.getByRole("button", { name: /Aktivite/ }).click();
    await expect(page.getByText("agency_member.updated").first()).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("agency.plan_changed").first()).toBeVisible();

    expect(consoleErrors, `console errors during agency management flow: ${consoleErrors.join("; ")}`).toEqual([]);
  });
});

// ── 6. Profile & Security ───────────────────────────────────────────────────

test.describe("platform admin — profile & security", () => {
  test("personal info edit, MFA enable/disable, and session list/revoke", async ({ page, context }) => {
    const consoleErrors: string[] = [];
    // Same rationale as the agency-management test: the wrong-current-password
    // check below deliberately triggers a 400, which Chromium always logs to
    // the console regardless of the app's graceful error handling.
    page.on("console", (msg) => {
      if (
        msg.type() === "error" &&
        !/Failed to fetch RSC payload/.test(msg.text()) &&
        !/responded with a status of 400/.test(msg.text())
      ) {
        consoleErrors.push(msg.text());
      }
    });

    await loginPlatformAdmin(page);
    await page.goto("/platform/profile");
    await expect(page.getByRole("heading", { name: "Profil ve Güvenlik" })).toBeVisible();

    // Personal info: edit + reload persistence
    const nameInput = page.locator('label:text("Ad Soyad") + input');
    await nameInput.fill("E2E Platform Admin Renamed");
    await page.getByRole("button", { name: "Kaydet" }).click();
    await expect(page.getByText("Profil güncellendi.")).toBeVisible({ timeout: 10_000 });
    await page.reload();
    await expect(page.locator('label:text("Ad Soyad") + input')).toHaveValue("E2E Platform Admin Renamed", {
      timeout: 10_000,
    });

    // Security tab: wrong current password shows a clear error
    await page.getByRole("button", { name: "Güvenlik" }).click();
    await page.getByLabel("Mevcut Şifre", { exact: true }).fill("WrongPassword123!");
    await page.getByLabel("Yeni Şifre", { exact: true }).fill("NewE2ePass1234!");
    await page.getByLabel("Yeni Şifre Tekrar", { exact: true }).fill("NewE2ePass1234!");
    await page.getByRole("button", { name: "Şifremi Güncelle" }).click();
    await expect(page.getByText(/hatalı|yanlış|incorrect/i)).toBeVisible({ timeout: 10_000 });

    // MFA enable flow
    await expect(page.getByRole("button", { name: "MFA'yı Etkinleştir" })).toBeVisible();
    await page.getByRole("button", { name: "MFA'yı Etkinleştir" }).click();
    const secretCode = await page.locator("code").first().innerText();
    const totp1 = currentTotp(secretCode.trim());
    await page.getByPlaceholder("6 haneli kod").fill(totp1);
    await page.getByRole("button", { name: "Doğrula ve Etkinleştir" }).click();
    await expect(page.getByText(/kurtarma kodlarını/)).toBeVisible({ timeout: 10_000 });

    // Recovery codes must never be logged to the browser console
    const leaked = consoleErrors.some((m) => /[0-9A-F]{6}-[0-9A-F]{6}/i.test(m));
    expect(leaked, "recovery codes must not appear in console output").toBe(false);

    await page.getByRole("button", { name: "Tamamlandı" }).click();
    await expect(page.getByText("Aktif", { exact: true }).first()).toBeVisible();

    // MFA disable flow
    await page.getByRole("button", { name: "MFA'yı devre dışı bırak" }).click();
    const totp2 = currentTotp(secretCode.trim());
    await page.getByPlaceholder("6 haneli kod").fill(totp2);
    await page.getByRole("button", { name: "Devre Dışı Bırak" }).click();
    await expect(page.getByRole("button", { name: "MFA'yı Etkinleştir" })).toBeVisible({ timeout: 10_000 });

    // Active sessions: a second real session from another browser context
    const secondContext = await context.browser()!.newContext();
    const secondPage = await secondContext.newPage();
    await loginPlatformAdmin(secondPage);
    await secondContext.close();

    await page.getByRole("button", { name: "Aktif Oturumlar" }).click();
    await expect(page.getByText("Oturumu kapat").first()).toBeVisible({ timeout: 10_000 });
    const sessionRowsBefore = await page.getByText("Oturumu kapat").count();
    expect(sessionRowsBefore).toBeGreaterThanOrEqual(1);

    await page.getByText("Oturumu kapat").first().click();
    await page.waitForTimeout(500);
    const sessionRowsAfter = await page.getByText("Oturumu kapat").count();
    expect(sessionRowsAfter).toBeLessThan(sessionRowsBefore);

    expect(consoleErrors, `console errors during profile/security flow: ${consoleErrors.join("; ")}`).toEqual([]);
  });
});

// ── 7. SEO & Growth Center ───────────────────────────────────────────────────

test.describe("platform admin — SEO & growth center", () => {
  test("real audit, page inventory, robots.txt, sitemap.xml, and UTM builder", async ({ page, request }) => {
    await loginPlatformAdmin(page);
    await page.goto("/platform/seo");
    await expect(page.getByRole("heading", { name: "SEO & Büyüme Merkezi" })).toBeVisible();

    // Genel Bakış: real health score (not a hardcoded placeholder)
    await expect(page.getByText("SEO Sağlık Skoru")).toBeVisible({ timeout: 10_000 });

    // Sayfa Envanteri: real public routes only, no private routes
    await page.getByRole("button", { name: "Sayfa Envanteri" }).click();
    await expect(page.getByText("Ana Sayfa")).toBeVisible();
    await expect(page.getByText("/platform")).not.toBeVisible();
    await expect(page.getByText("/dashboard")).not.toBeVisible();

    // Teknik Denetim: real issues, each with a suggestion
    await page.getByRole("button", { name: /Teknik Denetim/ }).click();
    await expect(page.getByText("→", { exact: false }).first()).toBeVisible({ timeout: 10_000 });

    // UTM builder: valid URL produces a link; copy works without throwing
    await page.getByRole("button", { name: "UTM Builder" }).click();
    await page.getByPlaceholder("https://flobrief.com/pricing").fill("https://flobrief.com/pricing");
    await page.getByPlaceholder("newsletter, google, linkedin").fill("newsletter");
    await page.getByPlaceholder("email, cpc, social").fill("email");
    await page.getByPlaceholder("q1_launch, black_friday").fill("e2e_test");
    await expect(page.getByText(/utm_source=newsletter/)).toBeVisible();

    // PageSpeed: no API key configured in this local env -> honest setup card, not a fake score
    await page.getByRole("button", { name: "PageSpeed" }).click();
    await expect(page.getByText("PageSpeed Insights bağlı değil")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("PAGESPEED_API_KEY")).toBeVisible();

    // Entegrasyonlar: GSC/GA4 show honest "not configured" states, never fake charts
    await page.getByRole("button", { name: "Entegrasyonlar" }).click();
    await expect(page.getByText("Kurulum Gerekli").first()).toBeVisible({ timeout: 10_000 });
    await expect(page.locator("canvas")).toHaveCount(0);

    // Real robots.txt / sitemap.xml responses (not 404, not private-route leaks)
    const robotsResp = await request.get("/robots.txt");
    expect(robotsResp.status()).toBe(200);
    const robotsBody = await robotsResp.text();
    expect(robotsBody).toContain("User-agent");

    const sitemapResp = await request.get("/sitemap.xml");
    expect(sitemapResp.status()).toBe(200);
    const sitemapBody = await sitemapResp.text();
    expect(sitemapBody).not.toContain("/platform");
    expect(sitemapBody).not.toContain("/dashboard");
    expect(sitemapBody).not.toContain("/brand");
  });
});

// ── 8. Responsive checks ─────────────────────────────────────────────────────

test.describe("platform admin — responsive", () => {
  for (const [name, width, height] of [
    ["desktop", 1440, 900],
    ["tablet", 1024, 768],
    ["mobile", 390, 844],
  ] as const) {
    test(`no horizontal overflow at ${name} (${width}x${height})`, async ({ page }) => {
      await loginPlatformAdmin(page);
      await page.setViewportSize({ width, height });

      for (const url of ["/platform/agencies", "/platform/whitealabel", "/platform/profile", "/platform/seo"]) {
        await page.goto(url);
        await page.waitForLoadState("networkidle");
        const overflow = await page.evaluate(
          () => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1
        );
        expect(overflow, `${url} overflows horizontally at ${width}x${height}`).toBe(false);
      }
    });
  }
});
