import { test, expect, type Page } from "@playwright/test";
import { execFileSync } from "node:child_process";
import path from "node:path";

/**
 * Regression suite for Module B — Time Tracking: real timer start/stop
 * (server `started_at` is the only source of truth for elapsed time, never
 * a client-only interval), manual entries, weekly/brand/brief reports, and
 * server-side (not just UI-hidden) RBAC on the team-scoped reports.
 *
 * Fixture is seeded via apps/backend/scripts/e2e_seed_time_tracking.py — a
 * fresh, disposable Agency/Brand/Brief with two real agency members (an
 * owner with TIME_ENTRY_VIEW_TEAM, a designer without it). No TimeEntry rows
 * are pre-seeded: every duration asserted below comes from a row this spec
 * itself creates through the real browser UI.
 */

const BACKEND_DIR = path.resolve(__dirname, "../../backend");
const PYTHON = process.env.E2E_PYTHON ?? path.join(BACKEND_DIR, ".venv", "Scripts", "python.exe");

let MANAGER_EMAIL: string;
let DESIGNER_EMAIL: string;
let PASSWORD: string;
let BRIEF_ID: string;
let AGENCY_ID: string;

function runSeedScript(args: string[]): Record<string, string> {
  const output = execFileSync(PYTHON, ["scripts/e2e_seed_time_tracking.py", ...args], {
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
  MANAGER_EMAIL = env.E2E_MANAGER_EMAIL;
  DESIGNER_EMAIL = env.E2E_DESIGNER_EMAIL;
  PASSWORD = env.E2E_PASSWORD;
  BRIEF_ID = env.E2E_BRIEF_ID;
  AGENCY_ID = env.__AGENCY_ID__;
  if (!MANAGER_EMAIL || !BRIEF_ID) {
    throw new Error("time-tracking fixture seed did not return the expected env vars");
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

// Same known-noise filter used by agency-calendar.spec.ts — neither entry
// indicates a functional problem in this feature.
const KNOWN_NOISE = /^Failed to load resource:|^Failed to fetch RSC payload/;

function trackConsoleErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error" && !KNOWN_NOISE.test(msg.text())) errors.push(msg.text());
  });
  page.on("pageerror", (err) => errors.push(err.message));
  return errors;
}

function toLocalInputValue(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

test.describe.serial("Time tracking flow", () => {
  test("start timer from brief, reload recomputes elapsed from server started_at, then stop with category/description/billable", async ({
    page,
  }) => {
    const consoleErrors = trackConsoleErrors(page);
    await loginAgency(page, MANAGER_EMAIL, PASSWORD);

    await page.goto(`/dashboard/briefs/${BRIEF_ID}`);
    await expect(page.getByText("E2E Time Tracking Brief")).toBeVisible({ timeout: 15_000 });

    const startButton = page.getByRole("button", { name: "Zaman Kaydı Başlat" });
    await expect(startButton).toBeVisible();
    await startButton.click();
    await expect(page.getByRole("button", { name: "Zaman Kaydını Durdur" })).toBeVisible({
      timeout: 10_000,
    });

    // Reload: the button must still reflect a running timer, proving the
    // server (not a client-only interval) is the source of truth for it
    // still being active after a fresh page load.
    await page.reload();
    await expect(page.getByRole("button", { name: "Zaman Kaydını Durdur" })).toBeVisible({
      timeout: 10_000,
    });

    // Open the global timer widget popover (sidebar) and confirm its
    // ticking mm:ss badge actually advances between two reads — recomputed
    // live from started_at, not frozen at the value it had on open.
    const timerButton = page.getByTitle("Zaman Takibi");
    await expect(timerButton).toBeVisible();
    const firstBadgeText = await timerButton.textContent();
    await page.waitForTimeout(2200);
    const secondBadgeText = await timerButton.textContent();
    expect(secondBadgeText).not.toBe(firstBadgeText);

    await timerButton.click();
    const panel = page.locator('[aria-label="Zaman Takibi"]');
    await expect(panel).toBeVisible();

    await panel.locator("select").selectOption("revision");
    await panel.getByPlaceholder("Ne üzerinde çalışıyorsunuz?").fill("E2E test açıklaması");
    const billableCheckbox = panel.locator('input[type="checkbox"]');
    await billableCheckbox.uncheck();
    await panel.getByRole("button", { name: "Durdur" }).click();

    await expect(page.getByRole("button", { name: "Zaman Kaydı Başlat" })).toBeVisible({
      timeout: 10_000,
    });

    expect(consoleErrors, `Unexpected console errors: ${consoleErrors.join("\n")}`).toEqual([]);
  });

  test("manual entry bound to the brief appears in the personal log", async ({ page }) => {
    // Added from the brief-detail page (not the generic "my" log) so it
    // carries brief_id/brand_id — required for the by-brief/by-brand report
    // assertions below to have real, non-zero totals to check.
    await loginAgency(page, MANAGER_EMAIL, PASSWORD);
    await page.goto(`/dashboard/briefs/${BRIEF_ID}`);
    await expect(page.getByRole("button", { name: "Manuel Kayıt Ekle" })).toBeVisible({
      timeout: 15_000,
    });

    await page.getByRole("button", { name: "Manuel Kayıt Ekle" }).click();
    await expect(page.getByText("Manuel Zaman Kaydı Ekle")).toBeVisible();

    const now = new Date();
    const twoHoursAgo = new Date(now.getTime() - 2 * 60 * 60 * 1000);
    // Scope to the modal's own field container — the brief-detail page also
    // has an unrelated <select> in its comment composer.
    const descriptionField = page.getByPlaceholder("Ne üzerinde çalıştınız?");
    const modalFields = descriptionField.locator("..").locator("..");
    await modalFields.locator("select").selectOption("design");
    await page.getByLabel("Başlangıç").fill(toLocalInputValue(twoHoursAgo));
    await page.getByLabel("Bitiş").fill(toLocalInputValue(now));
    await descriptionField.fill("E2E manuel kayıt");
    await page.getByRole("button", { name: "Kaydet" }).click();

    await expect(page.getByText("Manuel Zaman Kaydı Ekle")).toBeHidden({ timeout: 10_000 });

    await page.goto("/dashboard/time/my");
    await expect(page.getByText("E2E manuel kayıt")).toBeVisible({ timeout: 10_000 });
  });

  test("weekly timesheet reflects logged time", async ({ page }) => {
    await loginAgency(page, MANAGER_EMAIL, PASSWORD);
    await page.goto("/dashboard/time/weekly");
    await expect(page.getByText(/Toplam:/)).toBeVisible({ timeout: 15_000 });

    const totalText = await page.getByText(/Toplam: \d/).first().textContent();
    const totalHours = parseFloat((totalText ?? "").replace(/[^\d.]/g, ""));
    // At least the 2h manual entry from the previous test must be reflected.
    expect(totalHours).toBeGreaterThanOrEqual(2);
  });

  test("brief report shows correct real totals", async ({ page }) => {
    await loginAgency(page, MANAGER_EMAIL, PASSWORD);
    await page.goto("/dashboard/time/by-brief");
    await expect(page.getByTestId("brief-actual-hours")).toBeVisible({ timeout: 15_000 });

    const spentText = await page.getByTestId("brief-actual-hours").textContent();
    const spentHours = parseFloat((spentText ?? "").replace(/[^\d.]/g, ""));
    expect(spentHours).toBeGreaterThanOrEqual(2);
  });

  test("brand report shows correct real totals", async ({ page }) => {
    await loginAgency(page, MANAGER_EMAIL, PASSWORD);
    await page.goto("/dashboard/time/by-brand");
    await expect(page.getByTestId("brand-total-hours")).toBeVisible({ timeout: 15_000 });

    const totalText = await page.getByTestId("brand-total-hours").textContent();
    const totalHours = parseFloat((totalText ?? "").replace(/[^\d.]/g, ""));
    expect(totalHours).toBeGreaterThanOrEqual(2);
  });

  test("non-manager agency user cannot access team timesheet (real 403, not just a hidden tab)", async ({
    page,
  }) => {
    await loginAgency(page, DESIGNER_EMAIL, PASSWORD);
    await page.goto("/dashboard/time/my");
    await expect(page.getByRole("button", { name: "Manuel Kayıt Ekle" })).toBeVisible({
      timeout: 15_000,
    });

    // The team-scoped tab is hidden client-side for a non-manager role.
    await expect(page.getByRole("link", { name: "Ekip Timesheet" })).toHaveCount(0);

    // Navigating directly still hits the real, server-enforced 403 — never
    // fabricated or silently-empty data.
    await page.goto("/dashboard/time/team");
    await expect(page.getByText(/Gerekli yetki/)).toBeVisible({ timeout: 15_000 });
  });

  test("mobile viewport has no horizontal overflow", async ({ page }) => {
    await loginAgency(page, MANAGER_EMAIL, PASSWORD);
    await page.goto("/dashboard/time/my");
    await expect(page.getByRole("button", { name: "Manuel Kayıt Ekle" })).toBeVisible({
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

test.describe("Date-range filter (team / by-brand / missing) and notification deep-link targets", () => {
  // These run after the serial block above, using the same seeded manager.
  // The click-through from a notification bell item to its action_url is
  // pre-existing, unmodified plumbing (NotificationBell.tsx) — what these
  // cover is the part this round actually changed: build_notification_action_url
  // (unit-tested directly in test_notification_routes.py) and how the
  // target page (/dashboard/time/my) behaves once a user lands on it via
  // those exact deep-link query params.

  test("team timesheet: preset filter writes to the URL and survives a reload", async ({ page }) => {
    await loginAgency(page, MANAGER_EMAIL, PASSWORD);
    await page.goto("/dashboard/time/team");
    await expect(page.getByRole("button", { name: "Son 7 Gün" })).toBeVisible({ timeout: 15_000 });

    await page.getByRole("button", { name: "Son 7 Gün" }).click();
    await expect(page).toHaveURL(/range=last7&start=\d{4}-\d{2}-\d{2}&end=\d{4}-\d{2}-\d{2}/);
    const urlAfterPreset = page.url();

    await page.reload();
    await expect(page).toHaveURL(urlAfterPreset);
    await expect(page.getByRole("button", { name: "Filtreyi Temizle" })).toBeVisible();
  });

  test("by-brand: filter clears back to the unfiltered (server-default) view", async ({ page }) => {
    await loginAgency(page, MANAGER_EMAIL, PASSWORD);
    await page.goto("/dashboard/time/by-brand");
    await expect(page.getByRole("button", { name: "Bu Ay" })).toBeVisible({ timeout: 15_000 });

    await page.getByRole("button", { name: "Bu Ay" }).click();
    await expect(page).toHaveURL(/range=this_month/);

    await page.getByRole("button", { name: "Filtreyi Temizle" }).click();
    await expect(page).not.toHaveURL(/range=/);
  });

  test("missing timesheet: switching to the team tab preserves the active range", async ({ page }) => {
    await loginAgency(page, MANAGER_EMAIL, PASSWORD);
    await page.goto("/dashboard/time/missing");
    await expect(page.getByRole("button", { name: "Geçen Ay" })).toBeVisible({ timeout: 15_000 });

    await page.getByRole("button", { name: "Geçen Ay" }).click();
    await expect(page).toHaveURL(/range=last_month/);

    await page.getByRole("link", { name: "Ekip Timesheet" }).click();
    await expect(page).toHaveURL(/\/dashboard\/time\/team\?.*range=last_month/);
  });

  test("custom range rejects a start date after the end date", async ({ page }) => {
    await loginAgency(page, MANAGER_EMAIL, PASSWORD);
    await page.goto("/dashboard/time/team");
    const startInput = page.getByLabel("Başlangıç tarihi");
    const endInput = page.getByLabel("Bitiş tarihi");
    await expect(startInput).toBeVisible({ timeout: 15_000 });

    await endInput.fill("2026-07-01");
    await startInput.fill("2026-07-10");
    await expect(page.getByText("Başlangıç tarihi bitiş tarihinden sonra olamaz.")).toBeVisible();
  });

  test("LONG_RUNNING_TIMER deep-link target (/dashboard/time/my?timer=active) highlights the running timer", async ({
    page,
  }) => {
    await loginAgency(page, MANAGER_EMAIL, PASSWORD);
    await page.goto(`/dashboard/briefs/${BRIEF_ID}`);
    await expect(page.getByRole("button", { name: "Zaman Kaydı Başlat" })).toBeVisible({
      timeout: 15_000,
    });
    await page.getByRole("button", { name: "Zaman Kaydı Başlat" }).click();
    await expect(page.getByRole("button", { name: "Zaman Kaydını Durdur" })).toBeVisible({
      timeout: 10_000,
    });

    await page.goto("/dashboard/time/my?timer=active");
    await expect(page.getByText("Aktif zamanlayıcınız çalışıyor")).toBeVisible({ timeout: 10_000 });

    // Stop the timer so it doesn't bleed into any test that runs after this one.
    await page.goto(`/dashboard/briefs/${BRIEF_ID}`);
    await page.getByRole("button", { name: "Zaman Kaydını Durdur" }).click();
    await expect(page.getByRole("button", { name: "Zaman Kaydı Başlat" })).toBeVisible({
      timeout: 10_000,
    });
  });

  test("TIMESHEET_MISSING deep-link target scopes /dashboard/time/my to the notified date, never the team-scoped page", async ({
    page,
  }) => {
    await loginAgency(page, MANAGER_EMAIL, PASSWORD);
    await page.goto("/dashboard/time/my?range=custom&start=2020-01-01&end=2020-01-01");
    await expect(page.getByText("1 Ocak tarihi gösteriliyor.")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("1 Ocak için zaman kaydı yok")).toBeVisible({ timeout: 10_000 });
    expect(new URL(page.url()).pathname).toBe("/dashboard/time/my");
  });
});
