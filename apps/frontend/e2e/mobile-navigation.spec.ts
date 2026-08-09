import { test, expect, type Page } from "@playwright/test";
import { dismissOnboardingIfVisible } from "./helpers/onboarding";

/**
 * Part 4A shell coverage: mobile hamburger/drawer/bottom-nav for both
 * portals, browser-back support, desktop regression (chrome stays hidden
 * above `lg`), no horizontal overflow at 390px, and a smoke check that the
 * shell change didn't break the Part 3 onboarding welcome modal or the
 * @mention popover.
 *
 * Fixtures reused as-is (no new seed script):
 *   apps/backend/scripts/e2e_seed_mention_onboarding_agency.py  seed
 *   apps/backend/scripts/e2e_seed_brand_dashboard.py            seed
 */

const AGENCY_OWNER_EMAIL = process.env.E2E_OWNER_EMAIL;
const AGENCY_BRIEF_ID = process.env.E2E_BRIEF_ID;
const BRAND_EMAIL = process.env.E2E_BRAND_EMAIL;
const PASSWORD = process.env.E2E_PASSWORD ?? "E2eTest1234!";

const AGENCY_READY = Boolean(AGENCY_OWNER_EMAIL && AGENCY_BRIEF_ID);
const BRAND_READY = Boolean(BRAND_EMAIL);

const MOBILE_VIEWPORT = { width: 390, height: 844 };
const DESKTOP_VIEWPORT = { width: 1440, height: 900 };

// AuthProvider unconditionally probes `/api/v1/auth/refresh` on every app
// mount (context/auth-context.tsx) to opportunistically restore a session
// from the refresh cookie; on a fresh login there is no such cookie yet, so
// this logs a benign 401 in the console on every single page load,
// completely independent of the shell change under test here. Filtered by
// its resource URL (Chrome attributes "Failed to load resource" messages to
// the failing URL via ConsoleMessage#location) rather than by message text,
// so a genuine 401 against any other endpoint still fails the assertion.
function isKnownPreExistingNoise(msg: import("@playwright/test").ConsoleMessage): boolean {
  if (msg.location().url.includes("/api/v1/auth/refresh")) return true;
  // Next.js App Router aborts in-flight RSC prefetch requests for any
  // <Link> that was on-screen when the page navigates away before the
  // prefetch settles, and logs the abort as a console error. Pre-existing
  // dashboard-page content (unrelated to this shell change) triggers this
  // whenever a test jumps to another route immediately after login.
  if (msg.text().startsWith("Failed to fetch RSC payload for")) return true;
  // The deliverable preview-config lookup is an opportunistic fetch (no
  // config has been set for this seeded deliverable) that legitimately
  // 404s and is handled gracefully by the annotation composer — reproduces
  // identically against the pre-existing, unmodified mention-annotation-
  // smoke.spec.ts, so it's unrelated to this shell change.
  if (msg.location().url.includes("/preview-config")) return true;
  return false;
}

function trackConsoleErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error" && !isKnownPreExistingNoise(msg)) errors.push(msg.text());
  });
  return errors;
}

async function loginAgency(page: Page) {
  await page.goto("/auth/agency-login");
  await page.locator("#agency-email").fill(AGENCY_OWNER_EMAIL as string);
  await page.locator("#agency-password").fill(PASSWORD);
  await page.getByRole("button", { name: "Ajans Paneline Giriş Yap" }).click();
  await page.waitForURL((url) => url.pathname.startsWith("/dashboard"), { timeout: 15_000 });
  await dismissOnboardingIfVisible(page);
}

async function loginBrand(page: Page) {
  await page.goto("/brand/login");
  await page.locator("#brand-email").fill(BRAND_EMAIL as string);
  await page.locator("#brand-password").fill(PASSWORD);
  await page.getByRole("button", { name: "Marka Portalına Giriş Yap" }).click();
  await page.waitForURL((url) => url.pathname.startsWith("/brand/dashboard"), { timeout: 15_000 });
  await dismissOnboardingIfVisible(page);
}

async function assertNoHorizontalOverflow(page: Page) {
  const overflow = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
  }));
  expect(overflow.scrollWidth).toBeLessThanOrEqual(overflow.clientWidth + 1);
}

// Declared first and run first (this file is single-worker / not fully
// parallel, so tests execute in declaration order): visiting
// /dashboard/briefs/[id] elsewhere in this file marks the seeded owner's
// "preview_center" onboarding step as seen server-side via
// useOnboardingPageSeen, which would make the welcome modal's own
// precondition (`!data.current_step`) false for every test after that —
// so the welcome-modal check must run before any other test touches this
// shared fixture account.
test.describe("Onboarding + mention smoke (shell regression)", () => {
  test.skip(!AGENCY_READY, "E2E_OWNER_EMAIL / E2E_BRIEF_ID not set — run e2e_seed_mention_onboarding_agency.py seed first");
  test.use({ viewport: MOBILE_VIEWPORT });

  test("onboarding welcome modal still renders after the shell change", async ({ page }) => {
    const consoleErrors = trackConsoleErrors(page);
    await page.goto("/auth/agency-login");
    await page.locator("#agency-email").fill(AGENCY_OWNER_EMAIL as string);
    await page.locator("#agency-password").fill(PASSWORD);
    await page.getByRole("button", { name: "Ajans Paneline Giriş Yap" }).click();
    await page.waitForURL((url) => url.pathname.startsWith("/dashboard"), { timeout: 15_000 });

    const later = page.getByRole("button", { name: "Daha Sonra" });
    await expect(later).toBeVisible({ timeout: 10_000 });
    await assertNoHorizontalOverflow(page);
    await later.click();

    expect(consoleErrors).toEqual([]);
  });

  test("@mention popover still opens and stays within the viewport in the annotation composer", async ({ page }) => {
    const consoleErrors = trackConsoleErrors(page);
    await loginAgency(page);
    await page.goto(`/dashboard/briefs/${AGENCY_BRIEF_ID}`);
    // dismissOnboardingIfVisible (inside loginAgency) is a single immediate
    // check with no wait — the welcome modal's own progress fetch can still
    // be in flight at that point and pop up only after this second
    // navigation and intercept the "Teslimler" click, so give it a bounded
    // window to appear and dismiss it here too.
    const later = page.getByRole("button", { name: "Daha Sonra" });
    const laterAppeared = await later
      .waitFor({ state: "visible", timeout: 3_000 })
      .then(() => true)
      .catch(() => false);
    if (laterAppeared) await later.click();
    await page.getByRole("button", { name: "Teslimler" }).first().click();

    const img = page.locator("img[alt='Deliverable']").first();
    await img.waitFor({ state: "visible", timeout: 15_000 });
    await page.waitForFunction(() => {
      const el = document.querySelector<HTMLImageElement>("img[alt='Deliverable']");
      return !!el && el.complete && el.naturalWidth > 0;
    }, { timeout: 20_000 });

    await page.getByRole("button", { name: "Revizyon Noktası Belirle" }).click();
    const canvas = img.locator("..");
    await canvas.scrollIntoViewIfNeeded();
    const box = await canvas.boundingBox();
    if (!box) throw new Error("annotation canvas has no bounding box");
    await canvas.click({ position: { x: box.width / 2, y: box.height / 2 } });

    const composer = page.getByPlaceholder("Bu noktadaki revizyon talebini yazın…");
    await expect(composer).toBeVisible();
    await composer.fill("@");

    const popover = page.getByRole("listbox", { name: "Bahsedilecek kişiler" });
    await expect(popover).toBeVisible({ timeout: 5_000 });
    const popoverBox = await popover.boundingBox();
    const viewport = page.viewportSize();
    if (popoverBox && viewport) {
      expect(popoverBox.x).toBeGreaterThanOrEqual(0);
      expect(popoverBox.x + popoverBox.width).toBeLessThanOrEqual(viewport.width);
    }

    await page.keyboard.press("Escape");
    expect(consoleErrors).toEqual([]);
  });
});

test.describe("Agency mobile navigation", () => {
  test.skip(!AGENCY_READY, "E2E_OWNER_EMAIL / E2E_BRIEF_ID not set — run e2e_seed_mention_onboarding_agency.py seed first");
  test.use({ viewport: MOBILE_VIEWPORT });

  test("hamburger opens a focus-trapped, scroll-locked drawer with active route, then closes on nav", async ({ page }) => {
    const consoleErrors = trackConsoleErrors(page);
    await loginAgency(page);
    await assertNoHorizontalOverflow(page);

    const hamburger = page.getByRole("button", { name: "Menüyü aç" });
    await expect(hamburger).toBeVisible();

    await hamburger.click();
    const drawer = page.locator("#mobile-nav-drawer");
    await expect(drawer).toBeVisible();

    // Focus trap: focus should land inside the drawer (its own close button).
    await expect(page.getByRole("button", { name: "Menüyü kapat" })).toBeFocused();

    // Body scroll lock.
    const bodyOverflow = await page.evaluate(() => getComputedStyle(document.body).overflow);
    expect(bodyOverflow).toBe("hidden");

    // Active route indicator on "Genel Bakış".
    await expect(drawer.getByRole("link", { name: /Genel Bakış/ })).toHaveAttribute("aria-current", "page");

    // Navigate to Briefler — drawer should close automatically.
    await drawer.getByRole("link", { name: "Brief'ler", exact: false }).click();
    await page.waitForURL((url) => url.pathname === "/dashboard/briefs");
    await expect(drawer).toBeHidden();

    expect(consoleErrors).toEqual([]);
  });

  test("browser back closes the drawer without navigating away", async ({ page }) => {
    const consoleErrors = trackConsoleErrors(page);
    await loginAgency(page);

    await page.getByRole("button", { name: "Menüyü aç" }).click();
    const drawer = page.locator("#mobile-nav-drawer");
    await expect(drawer).toBeVisible();

    await page.goBack();
    await expect(drawer).toBeHidden();
    expect(new URL(page.url()).pathname).toBe("/dashboard");

    expect(consoleErrors).toEqual([]);
  });

  test("notification bell and active timer are reachable from the mobile header", async ({ page }) => {
    const consoleErrors = trackConsoleErrors(page);
    await loginAgency(page);

    await page.getByRole("button", { name: "Bildirimler" }).click();
    await expect(page.getByRole("dialog", { name: "Bildirimler" })).toBeVisible();
    await page.keyboard.press("Escape").catch(() => undefined);
    await page.mouse.click(5, 5);

    const timerButton = page.getByRole("button", { name: "Zaman Takibi" });
    await expect(timerButton).toBeVisible();
    await timerButton.click();
    await expect(page.getByRole("dialog", { name: "Zaman Takibi" })).toBeVisible();

    expect(consoleErrors).toEqual([]);
  });

  test("profile and logout are reachable from the drawer footer", async ({ page }) => {
    await loginAgency(page);
    await page.getByRole("button", { name: "Menüyü aç" }).click();
    const drawer = page.locator("#mobile-nav-drawer");

    await expect(drawer.getByRole("link", { name: /Profil/i })).toBeVisible();
    await expect(drawer.getByRole("button", { name: "Çıkış yap" })).toBeVisible();
  });

  test("bottom navigation shows the agency's 4 routes plus Daha Fazla, with active state", async ({ page }) => {
    await loginAgency(page);
    const bottomNav = page.getByRole("navigation", { name: "Alt gezinme" });
    for (const label of ["Ana Sayfa", "Briefler", "Takvim", "Bildirimler", "Daha Fazla"]) {
      await expect(
        bottomNav.getByRole("link", { name: label, exact: true }).or(bottomNav.getByRole("button", { name: label, exact: true }))
      ).toBeVisible();
    }
    await expect(bottomNav.getByRole("link", { name: "Ana Sayfa", exact: true })).toHaveAttribute("aria-current", "page");
  });
});

test.describe("Brand mobile navigation", () => {
  test.skip(!BRAND_READY, "E2E_BRAND_EMAIL not set — run e2e_seed_brand_dashboard.py seed first");
  test.use({ viewport: MOBILE_VIEWPORT });

  test("brand portal shows its own nav labels, distinct from the agency shell", async ({ page }) => {
    const consoleErrors = trackConsoleErrors(page);
    await loginBrand(page);
    await assertNoHorizontalOverflow(page);

    const bottomNav = page.getByRole("navigation", { name: "Alt gezinme" });
    for (const label of ["Ana Sayfa", "Briefler", "Onaylar", "Bildirimler", "Daha Fazla"]) {
      await expect(
        bottomNav.getByRole("link", { name: label, exact: true }).or(bottomNav.getByRole("button", { name: label, exact: true }))
      ).toBeVisible();
    }

    await page.getByRole("button", { name: "Menüyü aç" }).click();
    const drawer = page.locator("#mobile-nav-drawer");
    await expect(drawer).toBeVisible();
    await expect(drawer.getByText("Marka Portalı")).toBeVisible();
    // Agency-only nav items must not leak into the brand drawer.
    await expect(drawer.getByRole("link", { name: /Kapasite/ })).toHaveCount(0);

    expect(consoleErrors).toEqual([]);
  });
});

test.describe("Desktop regression", () => {
  test.skip(!AGENCY_READY, "E2E_OWNER_EMAIL / E2E_BRIEF_ID not set — run e2e_seed_mention_onboarding_agency.py seed first");
  test.use({ viewport: DESKTOP_VIEWPORT });

  test("mobile chrome is hidden and the desktop sidebar renders as before", async ({ page }) => {
    const consoleErrors = trackConsoleErrors(page);
    await loginAgency(page);

    await expect(page.getByRole("button", { name: "Menüyü aç" })).toBeHidden();
    await expect(page.getByRole("navigation", { name: "Alt gezinme" })).toBeHidden();
    await expect(page.getByText("Flobrief").first()).toBeVisible(); // desktop sidebar logo row

    expect(consoleErrors).toEqual([]);
  });
});
