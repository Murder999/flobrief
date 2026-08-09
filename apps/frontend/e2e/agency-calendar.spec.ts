import { test, expect, type Page } from "@playwright/test";
import { execFileSync } from "node:child_process";
import path from "node:path";

import { dismissOnboardingIfVisible } from "./helpers/onboarding";

/**
 * Regression suite for the agency operations calendar
 * (apps/frontend/app/dashboard/calendar/page.tsx): the merged agenda feed
 * (real CalendarItem rows + Brief milestones + Deliverable lifecycle
 * events), month/week/list view parity, filter correctness across mixed
 * status vocabularies, manual CRUD (including the all-day/timezone
 * round-trip), brief click-through, brand-portal isolation of
 * agency-internal records, and the mobile list-view fallback.
 *
 * Fixtures are the repo's existing idempotent demo seeds — no bespoke
 * ad-hoc fixture script — run via `beforeAll` so the suite is self-priming
 * against any local dev database.
 */

const BACKEND_DIR = path.resolve(__dirname, "../../backend");
const PYTHON = process.env.E2E_PYTHON ?? path.join(BACKEND_DIR, ".venv", "Scripts", "python.exe");

const AGENCY_EMAIL = "efe@360stradigi.com";
const AGENCY_PASSWORD = "159951.efe.";
const BRAND_EMAIL = "info@ulusal.com";
const BRAND_PASSWORD = "159951.efe.";

const DEMO_AGENCY_EMAIL = "owner@demo.flobrief.com";
const DEMO_AGENCY_PASSWORD = "Demo1234!";

test.beforeAll(() => {
  execFileSync(PYTHON, ["scripts/seed_ulusal_demo.py"], { cwd: BACKEND_DIR, encoding: "utf-8" });
  execFileSync(PYTHON, ["scripts/seed_demo.py"], { cwd: BACKEND_DIR, encoding: "utf-8" });
});

async function loginAgency(page: Page, email: string, password: string) {
  await page.goto("/auth/agency-login");
  await page.locator("#agency-email").fill(email);
  await page.locator("#agency-password").fill(password);
  await page.getByRole("button", { name: "Ajans Paneline Giriş Yap" }).click();
  await page.waitForURL((url) => url.pathname.startsWith("/dashboard"), { timeout: 15_000 });
  await dismissOnboardingIfVisible(page);
}

// Root cause of the historical flake in "shows the empty state only for a
// genuinely empty filter combination": that test asserts this agency has
// *zero* agency-internal (brand-less) manual CalendarItems. That's only
// true by accident of history — there's no per-run isolation, and the two
// tests below that create a manual internal item ("creates, edits, and
// deletes a manual record" / the brand-portal-isolation test) both delete
// it as their own last step. Any interrupted run (a crashed browser, a
// failed assertion between create and delete, a manual QA session against
// this same seeded account) leaves that item in the DB permanently, and
// every subsequent run of this test fails forever after — not because of
// a product bug, but because the fixture never guarantees the precondition
// it depends on. Purge defensively via the API before asserting, so the
// test creates the "genuinely empty" state itself instead of assuming it.
async function purgeOrphanAgencyInternalItems(page: Page, email: string, password: string) {
  const loginRes = await page.request.post("/api/v1/auth/login", {
    data: { email, password },
  });
  const { access_token: token } = await loginRes.json();
  const workspaces = await page.request.get("/api/v1/workspaces", {
    headers: { Authorization: `Bearer ${token}` },
  });
  const { agencies } = await workspaces.json();
  const agencyId: string | undefined = agencies?.[0]?.id;
  if (!agencyId) return;

  const agenda = await page.request.get(
    "/api/v1/calendar/agenda?brand_id=internal&from=2000-01-01&to=2100-01-01",
    { headers: { Authorization: `Bearer ${token}`, "X-Agency-ID": agencyId } }
  );
  const entries: { source_type: string; calendar_item_id: string | null }[] = await agenda.json();
  for (const entry of entries) {
    if (entry.source_type === "manual" && entry.calendar_item_id) {
      await page.request.delete(`/api/v1/calendar/items/${entry.calendar_item_id}`, {
        headers: { Authorization: `Bearer ${token}`, "X-Agency-ID": agencyId },
      });
    }
  }
}

async function loginBrand(page: Page, email: string, password: string) {
  await page.goto("/brand/login");
  await page.locator("#brand-email").fill(email);
  await page.locator("#brand-password").fill(password);
  await page.getByRole("button", { name: "Marka Portalına Giriş Yap" }).click();
  await page.waitForURL(
    (url) => url.pathname.startsWith("/brand") && url.pathname !== "/brand/login",
    { timeout: 15_000 }
  );
  await dismissOnboardingIfVisible(page);
}

// Two categories of pre-existing, app-wide runtime noise, neither specific
// to the calendar and neither indicating a functional problem:
//  - AuthProvider calls refreshSession() on every non-/platform page mount
//    (context/auth-context.tsx), which 401s whenever there's no session yet
//    (e.g. the pre-login page itself), surfaced by the browser as a generic
//    "Failed to load resource" entry.
//  - Next.js App Router's own background link-prefetcher (every visible
//    sidebar <Link>) races with fast client-side navigation and falls back
//    to a full browser navigation by design — "Failed to fetch RSC payload
//    ... Falling back to browser navigation" is that fallback's own log,
//    not a broken navigation (all subsequent assertions on real rendered
//    content still pass).
// Real application errors (console.error calls, React duplicate-key
// warnings, uncaught exceptions) are never suppressed by this filter.
const KNOWN_NOISE = /^Failed to load resource:|^Failed to fetch RSC payload/;

function trackConsoleErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error" && !KNOWN_NOISE.test(msg.text())) errors.push(msg.text());
  });
  page.on("pageerror", (err) => errors.push(err.message));
  return errors;
}

const WEEKDAY_HEADING = /2026 (Pazartesi|Salı|Çarşamba|Perşembe|Cuma|Cumartesi|Pazar)/;

test.describe("Agency operations calendar", () => {
  test("shows real brief milestones, deliverable and revision events across month/week/list without console errors", async ({
    page,
  }) => {
    const consoleErrors = trackConsoleErrors(page);
    await loginAgency(page, AGENCY_EMAIL, AGENCY_PASSWORD);
    await page.goto("/dashboard/calendar");
    await expect(page.getByRole("heading", { name: "İçerik ve Operasyon Takvimi" })).toBeVisible();

    // Real data, not placeholders: brief milestones, a deliverable
    // submission, and a revision request are all visible in month view.
    await expect(page.getByText("Brief Başlangıcı").first()).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText("Teslim Gönderildi").first()).toBeVisible();
    // "Revizyon İstendi" is also a <option> label in the status filter, so
    // getByText's DOM-order-first match would be that (permanently hidden)
    // option — scope to calendar-entry buttons instead.
    await expect(
      page.getByRole("button", { name: /Revizyon İstendi/ }).first()
    ).toBeVisible();

    // Switch view modes — records must not disappear mid-switch.
    await page.getByRole("button", { name: "Hafta", exact: true }).click();
    await expect(page.getByText("Brief Başlangıcı").first()).toBeVisible();
    await page.getByRole("button", { name: "Liste", exact: true }).click();
    await expect(page.getByText("Brief Başlangıcı").first()).toBeVisible();
    // List view groups entries under a Turkish date heading.
    await expect(page.getByText(WEEKDAY_HEADING).first()).toBeVisible();

    expect(consoleErrors, `Unexpected console errors:\n${consoleErrors.join("\n")}`).toEqual([]);
  });

  test("status filter matches the displayed status bucket across brief/deliverable/manual sources", async ({
    page,
  }) => {
    await loginAgency(page, AGENCY_EMAIL, AGENCY_PASSWORD);
    await page.goto("/dashboard/calendar");
    await expect(page.getByRole("heading", { name: "İçerik ve Operasyon Takvimi" })).toBeVisible();

    // Brief-sourced entries carry raw statuses like "in_review" /
    // "ready_for_review", not the literal "waiting_approval" CalendarItem
    // enum — the filter must still match them because both render in the
    // same "Onay Bekliyor" bucket.
    await page.locator("select").nth(3).selectOption({ label: "Onay Bekliyor" });
    await expect(page.getByText("Brief Başlangıcı").first()).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText("Bu dönemde planlanmış kayıt bulunmuyor")).toHaveCount(0);
  });

  test("shows the empty state only for a genuinely empty filter combination, and clears cleanly", async ({
    page,
  }) => {
    await purgeOrphanAgencyInternalItems(page, AGENCY_EMAIL, AGENCY_PASSWORD);
    await loginAgency(page, AGENCY_EMAIL, AGENCY_PASSWORD);
    await page.goto("/dashboard/calendar");

    // This agency has no agency-internal (brand-less) manual entries.
    await page.locator("select").nth(0).selectOption({ label: "Ajans İçi" });
    await expect(page.getByText("Bu dönemde planlanmış kayıt bulunmuyor")).toBeVisible({
      timeout: 15_000,
    });

    await page.getByRole("button", { name: "Filtreleri Temizle" }).click();
    await expect(page.getByText("Bu dönemde planlanmış kayıt bulunmuyor")).toHaveCount(0);
    await expect(page.getByText("Brief Başlangıcı").first()).toBeVisible();
  });

  test("clicking a brief milestone navigates client-side to the correct brief", async ({ page }) => {
    await loginAgency(page, AGENCY_EMAIL, AGENCY_PASSWORD);
    await page.goto("/dashboard/calendar");
    await page
      .getByRole("button", { name: /Faktoring Nedir\? — Brief Başlangıcı/ })
      .first()
      .click();
    await page.waitForURL(/\/dashboard\/briefs\/[0-9a-f-]+$/, { timeout: 15_000 });
    await expect(page.getByText("Faktoring Nedir?").first()).toBeVisible();
  });

  test("creates, edits, and deletes a manual record; all-day date round-trips without a timezone shift", async ({
    page,
  }) => {
    await loginAgency(page, AGENCY_EMAIL, AGENCY_PASSWORD);
    await page.goto("/dashboard/calendar");
    await page.getByRole("button", { name: "Yeni Kayıt" }).click();

    await page.locator("#cal-item-title").fill("E2E Ajans İçi Görev");
    await page.locator("#cal-item-description").fill("Playwright ile oluşturuldu");
    await expect(page.locator("#cal-item-brand")).toHaveValue(""); // defaults to Ajans İçi
    await page.locator("#cal-item-priority").selectOption({ label: "Yüksek" });
    await page.locator("#cal-item-all-day").check();
    await page.locator("#cal-item-publish-at").fill("2026-07-31");
    await page.getByRole("button", { name: "Oluştur" }).click();
    await expect(page.getByText("E2E Ajans İçi Görev")).toBeVisible({ timeout: 15_000 });

    // Reopen and confirm the all-day date is exactly what was entered — this
    // is the exact round-trip that used to shift by the local UTC offset.
    await page.getByRole("button", { name: /E2E Ajans İçi Görev/ }).click();
    await expect(page.locator("#cal-item-all-day")).toBeChecked();
    await expect(page.locator("#cal-item-publish-at")).toHaveValue("2026-07-31");

    await page.getByRole("button", { name: "Sil" }).click();
    await expect(page.getByText("E2E Ajans İçi Görev")).toHaveCount(0);
  });
});

test.describe("Multi-brand agency (Demo Agency)", () => {
  test("multiple brands appear together and the brand filter narrows results", async ({ page }) => {
    await loginAgency(page, DEMO_AGENCY_EMAIL, DEMO_AGENCY_PASSWORD);
    await page.goto("/dashboard/calendar");
    // Month view doesn't render the brand name inside the chip (only as a
    // tooltip); list view shows it as visible row text, and also sidesteps
    // the brand filter's own <option value="...">TechNova</option>.
    await page.getByRole("button", { name: "Liste", exact: true }).click();
    await expect(page.getByRole("button", { name: /TechNova/ }).first()).toBeVisible({
      timeout: 15_000,
    });

    await page.locator("select").nth(0).selectOption({ label: "TechNova" });
    await expect(page.getByText(/^2 kayıt$/)).toBeVisible({ timeout: 15_000 });
  });
});

test.describe("Brand portal isolation", () => {
  test("an agency-internal record is never exposed on the brand portal calendar", async ({ page }) => {
    await loginAgency(page, AGENCY_EMAIL, AGENCY_PASSWORD);
    await page.goto("/dashboard/calendar");
    await page.getByRole("button", { name: "Yeni Kayıt" }).click();
    await page.locator("#cal-item-title").fill("E2E Gizli Ajans Görevi");
    await page.getByRole("button", { name: "Oluştur" }).click();
    // No date set, so it only surfaces in list view's "Tarihi Belirsiz" bucket.
    await page.getByRole("button", { name: "Liste", exact: true }).click();
    await expect(page.getByText("E2E Gizli Ajans Görevi")).toBeVisible({ timeout: 15_000 });

    await loginBrand(page, BRAND_EMAIL, BRAND_PASSWORD);
    await page.goto("/brand/calendar");
    await expect(page.getByText("E2E Gizli Ajans Görevi")).toHaveCount(0);

    await loginAgency(page, AGENCY_EMAIL, AGENCY_PASSWORD);
    await page.goto("/dashboard/calendar");
    await page.getByRole("button", { name: "Liste", exact: true }).click();
    await page.getByRole("button", { name: /E2E Gizli Ajans Görevi/ }).click();
    await page.getByRole("button", { name: "Sil" }).click();
    await expect(page.getByText("E2E Gizli Ajans Görevi")).toHaveCount(0);
  });
});

test.describe("Mobile responsiveness", () => {
  test("falls back to list view under 768px width with no horizontal overflow", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await loginAgency(page, AGENCY_EMAIL, AGENCY_PASSWORD);
    await page.goto("/dashboard/calendar");

    // List view's date-grouped heading is the fallback's signature — the
    // month grid never renders this text.
    await expect(page.getByText(WEEKDAY_HEADING).first()).toBeVisible({ timeout: 15_000 });

    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth
    );
    expect(overflow).toBeLessThanOrEqual(1);
  });
});
