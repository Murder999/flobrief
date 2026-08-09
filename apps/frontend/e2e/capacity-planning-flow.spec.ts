import { test, expect, type Page, type Locator } from "@playwright/test";
import { execFileSync } from "node:child_process";
import path from "node:path";

/**
 * Regression suite for the capacity/resource-planning module (Part 2 Phase
 * 1-2): the team capacity grid replacing the old dead-code workload page,
 * WorkSchedule editing, TimeOff request+approve reducing real net capacity
 * (with the "İzinli" reason label, never a bare misleading 0%), the
 * unassigned-work report, manual WorkAllocation creation (the real "assign"
 * mechanism this module ships) with a genuine over-capacity warning, and
 * server-enforced (not just UI-hidden) RBAC for a Designer role.
 *
 * Fixture is seeded via apps/backend/scripts/e2e_seed_capacity.py -- a
 * fresh, disposable Agency/Brand with an owner + a designer, each with a
 * real WorkSchedule (480 min/day, every weekday, so the math is
 * deterministic regardless of which real day the suite runs on) and one
 * Brief with an estimate but zero assignees (a real "unassigned work" item
 * derived at read time, not a seeded flag). No TimeOff/WorkAllocation rows
 * are pre-seeded -- every number asserted below comes from an action this
 * spec performs through the real browser UI.
 */

const BACKEND_DIR = path.resolve(__dirname, "../../backend");
const PYTHON = process.env.E2E_PYTHON ?? path.join(BACKEND_DIR, ".venv", "Scripts", "python.exe");

let OWNER_EMAIL: string;
let DESIGNER_EMAIL: string;
let PASSWORD: string;
let OWNER_ID: string;
let DESIGNER_ID: string;
let BRIEF_ID: string;
let AGENCY_ID: string;

function runSeedScript(args: string[]): Record<string, string> {
  const output = execFileSync(PYTHON, ["scripts/e2e_seed_capacity.py", ...args], {
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
  DESIGNER_EMAIL = env.E2E_DESIGNER_EMAIL;
  PASSWORD = env.E2E_PASSWORD;
  OWNER_ID = env.E2E_OWNER_ID;
  DESIGNER_ID = env.E2E_DESIGNER_ID;
  BRIEF_ID = env.E2E_BRIEF_ID;
  AGENCY_ID = env.__AGENCY_ID__;
  if (!OWNER_EMAIL || !DESIGNER_ID || !BRIEF_ID) {
    throw new Error("capacity fixture seed did not return the expected env vars");
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

// Same known-noise filter used across the other e2e specs.
const KNOWN_NOISE = /^Failed to load resource:|^Failed to fetch RSC payload/;

function trackConsoleErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error" && !KNOWN_NOISE.test(msg.text())) errors.push(msg.text());
  });
  page.on("pageerror", (err) => errors.push(err.message));
  return errors;
}

// components/ui/select.tsx renders a <label> with NO htmlFor/id -- getByLabel
// cannot resolve any <Select> in this codebase. This locates the real
// <select> via its visible label text, scoped to a container Locator so it
// doesn't collide with a same-labelled Select elsewhere on the page.
function selectByLabel(scope: Locator, labelText: string): Locator {
  return scope.locator(
    `xpath=.//label[normalize-space(text())="${labelText}"]/parent::div//select`
  );
}

function cardByTitle(page: Page, title: string): Locator {
  return page
    .locator("div.rounded-xl")
    .filter({ has: page.getByRole("heading", { name: title, exact: true }) })
    .first();
}

function todayISO(): string {
  const d = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

test.describe.serial("Capacity planning flow", () => {
  test("team grid shows real seeded WorkSchedule data; designer's team-scoped access is a real 403", async ({
    page,
  }) => {
    const consoleErrors = trackConsoleErrors(page);
    await loginAgency(page, OWNER_EMAIL, PASSWORD);

    await page.goto("/dashboard/capacity");
    await expect(page.getByRole("heading", { name: "Ekip Kapasitesi" })).toBeVisible({ timeout: 15_000 });

    // Weekly scale (default) x 7 uniform 480-min days seeded for each member
    // = 3360 min = "56.0s" net capacity -- a real number derived from the
    // seeded WorkSchedule rows, not a placeholder.
    await expect(page.getByText("56.0s").first()).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("E2E Capacity Owner").first()).toBeVisible();
    await expect(page.getByText("E2E Capacity Designer").first()).toBeVisible();

    expect(consoleErrors, `Unexpected console errors: ${consoleErrors.join("\n")}`).toEqual([]);

    // Designer has no CAPACITY_VIEW_TEAM: hitting the team page directly is
    // a real server-enforced gate, not just a hidden nav item.
    await loginAgency(page, DESIGNER_EMAIL, PASSWORD);
    await page.goto("/dashboard/capacity");
    await expect(page.getByText("Bu sayfayı görüntüleme yetkiniz yok")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText("Ekip kapasitesini görmek için yetkili bir rol gereklidir.")).toBeVisible();

    // The designer cannot read a teammate's capacity by direct URL either --
    // no data leaks even as an error state.
    await page.goto(`/dashboard/capacity/${OWNER_ID}`);
    // The frontend surfaces the raw ApiError message (literally "HTTP 403")
    // in the error box -- a real, non-fabricated refusal either way. What
    // matters is that no capacity data ever renders for it.
    await expect(page.getByText(/HTTP 403|yetkiniz yok|yüklenemedi/i)).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText("Net Kapasite")).toHaveCount(0);

    // But the designer's own schedule page works, read-only (no manage perm).
    await page.goto("/dashboard/capacity/schedule");
    await expect(page.getByRole("heading", { name: "Kapasite Ayarları" })).toBeVisible({ timeout: 15_000 });
    await expect(
      page.getByText("Programı düzenleme yetkiniz yok — yalnızca görüntülüyorsunuz.")
    ).toBeVisible();
  });

  test("owner edits a work schedule, requests and approves time off, and net capacity reflects it with the İzinli reason", async ({
    page,
  }) => {
    await loginAgency(page, OWNER_EMAIL, PASSWORD);
    await page.goto("/dashboard/capacity/schedule");
    await expect(page.getByRole("heading", { name: "Kapasite Ayarları" })).toBeVisible({ timeout: 15_000 });

    // Edit Monday's capacity for self (owner has CAPACITY_MANAGE_SCHEDULE).
    const mondayCard = page.locator("span", { hasText: "Pazartesi" }).locator("../..");
    const mondayInput = mondayCard.locator('input[type="number"]');
    await expect(mondayInput).toBeVisible();
    await mondayInput.fill("300");
    await page.getByRole("button", { name: "Kaydet" }).click();
    await expect(page.getByText("Çalışma programı kaydedildi")).toBeVisible({ timeout: 10_000 });

    await page.reload();
    await expect(page.getByRole("heading", { name: "Kapasite Ayarları" })).toBeVisible({ timeout: 15_000 });
    await expect(mondayInput).toHaveValue("300");

    // Before requesting time off: today shows the full seeded 480 min (8.0s)
    // on the daily-scale detail view.
    await page.goto(`/dashboard/capacity/${OWNER_ID}`);
    await page.getByRole("button", { name: "Günlük" }).click();
    await expect(page.getByText("8.0s").first()).toBeVisible({ timeout: 10_000 });

    // Request and approve an all-day leave covering today.
    await page.goto("/dashboard/capacity/schedule");
    const today = todayISO();
    const timeOffCard = cardByTitle(page, "İzinler");
    await timeOffCard.getByLabel("Başlangıç").fill(today);
    await timeOffCard.getByLabel("Bitiş").fill(today);
    await page.getByRole("button", { name: "Talep Oluştur" }).click();
    await expect(page.getByText("İzin talebi oluşturuldu")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("Bekliyor")).toBeVisible();

    await page.locator('button[title="Onayla"]').click();
    await expect(page.getByText("İzin onaylandı")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("Onaylandı", { exact: true })).toBeVisible();

    // Net capacity for today is now correctly zeroed with a real reason
    // ("İzinli"), never a bare misleading "0".
    await page.goto(`/dashboard/capacity/${OWNER_ID}`);
    await page.getByRole("button", { name: "Günlük" }).click();
    await expect(page.getByText("İzinli")).toBeVisible({ timeout: 10_000 });
  });

  test("owner sees the unassigned brief, assigns it to the designer via a manual allocation, and a genuine over-capacity warning fires", async ({
    page,
  }) => {
    await loginAgency(page, OWNER_EMAIL, PASSWORD);

    await page.goto("/dashboard/capacity/unassigned");
    await expect(page.getByRole("heading", { name: "Atanmamış İşler" })).toBeVisible({ timeout: 15_000 });
    await expect(page.getByRole("link", { name: "E2E Unassigned Capacity Brief" })).toBeVisible({
      timeout: 10_000,
    });

    // Assign it: create a manual WorkAllocation for the designer against
    // this brief, deliberately larger than the designer's 480-min/day net
    // capacity so the over-capacity warning is a real, earned signal.
    await page.goto("/dashboard/capacity/schedule");
    const teamMemberSelect = selectByLabel(page.locator("body"), "Ekip Üyesi");
    await expect(teamMemberSelect).toBeVisible({ timeout: 10_000 });
    await teamMemberSelect.selectOption({ label: "E2E Capacity Designer" });

    const allocationCard = page
      .locator("div.rounded-xl")
      .filter({ has: page.getByRole("heading", { name: "Manuel Atamalar" }) })
      .first();
    await expect(allocationCard).toBeVisible({ timeout: 10_000 });

    const briefSelect = selectByLabel(allocationCard, "Brief (opsiyonel)");
    await briefSelect.selectOption({ label: "E2E Unassigned Capacity Brief" });

    const today = todayISO();
    await allocationCard.getByLabel("Başlangıç").fill(today);
    await allocationCard.getByLabel("Bitiş").fill(today);
    await allocationCard.getByLabel("Dakika").fill("600");
    await allocationCard.getByRole("button", { name: "Ekle" }).click();

    await expect(page.getByText("Atama oluşturuldu — kapasite aşımı olabilir")).toBeVisible({
      timeout: 10_000,
    });

    // The assignment is now real, visible data on the designer's own
    // capacity detail page: the brief appears under "Brief Bazlı Atamalar"
    // with the correct 10.0s (600 min) allocation.
    await page.goto(`/dashboard/capacity/${DESIGNER_ID}`);
    await page.getByRole("button", { name: "Günlük" }).click();
    await expect(page.getByRole("link", { name: "E2E Unassigned Capacity Brief" })).toBeVisible({
      timeout: 10_000,
    });
    await expect(page.getByText("10.0s").first()).toBeVisible();
  });

  test("mobile viewport has no horizontal overflow", async ({ page }) => {
    await loginAgency(page, OWNER_EMAIL, PASSWORD);
    await page.goto("/dashboard/capacity");
    await expect(page.getByRole("heading", { name: "Ekip Kapasitesi" })).toBeVisible({ timeout: 15_000 });

    await page.setViewportSize({ width: 390, height: 844 });
    await page.waitForTimeout(300);
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - window.innerWidth
    );
    expect(overflow).toBeLessThanOrEqual(1);
  });
});
