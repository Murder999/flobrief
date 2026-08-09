import { test, expect, type Page } from "@playwright/test";
import { execFileSync } from "node:child_process";
import path from "node:path";

/**
 * Onboarding wizard coverage: welcome modal, role-scoped step lists (owner
 * 13 / member 7 / brand 8), real DOM spotlight highlighting (including the
 * view-kind-step spotlight regression fixed in OnboardingWizard.tsx), the
 * no-target fallback + "Sayfayı Aç" recovery path, CTA navigation, real-action
 * step completion, view-step completion via direct navigation, session-scoped
 * dismissal, the floating launcher, reload persistence, and a server-side
 * IDOR check.
 *
 * Isolation model (fixed a real test-ordering bug — see final report):
 * every `describe` block below seeds its OWN dedicated agency/brand fixture
 * via a unique `--run=<id>` suffix (apps/backend/scripts/
 * e2e_seed_mention_onboarding_{agency,brand}.py), instead of one file-level
 * `beforeAll` fixture shared by all 9 describe blocks and ~16 tests. The old
 * design silently depended on Playwright's single-worker file-declaration
 * order: e.g. the "Dismiss, relaunch, and persistence" describe's "fresh
 * browser context does not force-reopen the welcome modal" test asserted
 * against `current_step` having been persisted server-side, but the step it
 * clicked (`agency_profile`) is an *action*-kind step — clicking its CTA
 * never calls `POST .../step/{key}/seen`, so it never actually sets
 * `current_step` (see OnboardingService.mark_step_seen, only called for
 * view-kind steps). The assertion only ever passed because an EARLIER
 * describe block in the same file ("View-step completion via direct
 * navigation") had already visited /dashboard/briefs for the very same
 * shared AGY_OWNER_EMAIL fixture, which marks a *view*-kind step
 * (`preview_center`) seen and does persist `current_step` — an implicit
 * cross-describe dependency that breaks under `--grep`, sharding, or any
 * reordering. Two describe blocks below now seed a completely fresh,
 * dedicated owner ("onb-dismiss-1"/"onb-dismiss-3") and the "engaged" test
 * deterministically clicks a real *view*-kind step's CTA itself
 * (`brand_portal_preview` / "Markaları Gör") as its own precondition, instead
 * of relying on residue from an unrelated test.
 *
 * Every other describe block seeds its fixture already-dismissed (or, for
 * "Spotlight highlighting"/"Spotlight fallback"/"Step CTA navigation"/
 * "Action-step completion"/"Viewport spot-checks", one fresh-but-independent
 * fixture per test/describe) so the welcome modal never races the floating
 * launcher button — no test needs to click both the launcher AND "Turu
 * Başlat" defensively anymore. Only "Welcome modal and role-scoped step
 * counts" and "Dismiss, relaunch, and persistence" legitimately need
 * fresh/undismissed state, since they test the welcome modal's own behavior.
 */

const PASSWORD = "E2eTest1234!";
const BACKEND_DIR = path.resolve(__dirname, "../../backend");
const PYTHON = process.env.E2E_PYTHON ?? path.join(BACKEND_DIR, ".venv", "Scripts", "python.exe");

function runSeedScript(script: string, args: string[]): Record<string, string> {
  const output = execFileSync(PYTHON, [`scripts/${script}`, ...args], {
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

interface AgencyFixture {
  agencyId: string;
  ownerEmail: string;
  designerEmail: string;
}

type SeedMode = "fresh" | "dismissed";

/** Seeds one isolated agency (+ owner + designer) under the given run id.
 * "fresh" seeds real, never-dismissed OnboardingProgress rows (for specs
 * that assert on the welcome modal's own first-run behavior); "dismissed"
 * (the default) dismisses both via the real dismiss endpoint so the welcome
 * modal never auto-shows and races the floating launcher. Always call
 * `cleanupAgencyFixture(runId)` afterwards (afterAll or try/finally). */
function seedAgencyFixture(runId: string, mode: SeedMode = "dismissed"): AgencyFixture {
  const args = ["seed", `--run=${runId}`, ...(mode === "fresh" ? ["no-dismiss"] : [])];
  const env = runSeedScript("e2e_seed_mention_onboarding_agency.py", args);
  if (!env.E2E_AGENCY_ID || !env.E2E_OWNER_EMAIL || !env.E2E_DESIGNER_EMAIL) {
    throw new Error(`agency onboarding fixture seed (run=${runId}) did not return the expected env vars`);
  }
  return { agencyId: env.E2E_AGENCY_ID, ownerEmail: env.E2E_OWNER_EMAIL, designerEmail: env.E2E_DESIGNER_EMAIL };
}

function cleanupAgencyFixture(runId: string): void {
  runSeedScript("e2e_seed_mention_onboarding_agency.py", ["cleanup", `--run=${runId}`]);
}

interface BrandFixture {
  brandOwnerEmail: string;
}

function seedBrandFixture(runId: string, mode: SeedMode = "dismissed"): BrandFixture {
  const args = ["seed", `--run=${runId}`, ...(mode === "fresh" ? ["no-dismiss"] : [])];
  const env = runSeedScript("e2e_seed_mention_onboarding_brand.py", args);
  if (!env.E2E_BRAND_OWNER_EMAIL) {
    throw new Error(`brand onboarding fixture seed (run=${runId}) did not return the expected env vars`);
  }
  return { brandOwnerEmail: env.E2E_BRAND_OWNER_EMAIL };
}

function cleanupBrandFixture(runId: string): void {
  runSeedScript("e2e_seed_mention_onboarding_brand.py", ["cleanup", `--run=${runId}`]);
}

async function loginAgency(page: Page, email: string) {
  await page.goto("/auth/agency-login");
  await page.locator("#agency-email").fill(email);
  await page.locator("#agency-password").fill(PASSWORD);
  await page.getByRole("button", { name: "Ajans Paneline Giriş Yap" }).click();
  await page.waitForURL((url) => url.pathname.startsWith("/dashboard"), { timeout: 15_000 });
}

async function loginBrand(page: Page, email: string) {
  await page.goto("/brand/login");
  await page.locator("#brand-email").fill(email);
  await page.locator("#brand-password").fill(PASSWORD);
  await page.getByRole("button", { name: "Marka Portalına Giriş Yap" }).click();
  await page.waitForURL((url) => url.pathname.startsWith("/brand") && url.pathname !== "/brand/login", {
    timeout: 15_000,
  });
}

const welcomeModalHeading = (page: Page) => page.getByRole("heading", { name: /hoş geldiniz/ });
const panel = (page: Page) => page.locator("div.animate-in.slide-in-from-right");
const highlightBox = (page: Page) => page.locator("div.fixed.rounded-xl.border-2");

/** Opens the wizard panel via the always-present floating launcher button
 * (never via "Turu Başlat", which only exists while the welcome modal is
 * showing) — deterministic for fixtures seeded "dismissed" via
 * seedAgencyFixture, since the launcher's onClick opens the panel directly
 * whether or not the tour was ever dismissed. */
async function openPanelViaLauncher(page: Page) {
  await page.getByRole("button", { name: "Kurulum rehberini aç" }).click();
}

// ── Welcome modal + role-scoped step lists ───────────────────────────────────

test.describe("Welcome modal and role-scoped step counts", () => {
  const AGENCY_RUN = "onb-welcome-agy";
  const BRAND_RUN = "onb-welcome-brd";
  let agency: AgencyFixture;
  let brand: BrandFixture;

  test.beforeAll(() => {
    agency = seedAgencyFixture(AGENCY_RUN, "fresh");
    brand = seedBrandFixture(BRAND_RUN, "fresh");
  });

  test.afterAll(() => {
    cleanupAgencyFixture(AGENCY_RUN);
    cleanupBrandFixture(BRAND_RUN);
  });

  test("fresh agency owner login shows the welcome modal; the panel lists exactly the 13 owner steps", async ({ page }) => {
    await loginAgency(page, agency.ownerEmail);
    await page.goto("/dashboard");
    await expect(welcomeModalHeading(page)).toBeVisible({ timeout: 10_000 });
    await page.getByRole("button", { name: "Turu Başlat" }).click();

    const rows = panel(page).locator("p.text-xs.font-medium");
    await expect(rows).toHaveCount(13, { timeout: 10_000 });
    await expect(panel(page)).toContainText("Ajans profilini tamamla"); // owner-only
    await expect(panel(page)).not.toContainText("Rolünü ve çalışma alanını tanı"); // member-only
    await expect(panel(page)).not.toContainText("Takvim ve faturaları gör"); // brand-only
  });

  test("fresh agency member (designer) login shows the welcome modal; the panel lists exactly the 7 member steps", async ({ page }) => {
    await loginAgency(page, agency.designerEmail);
    await page.goto("/dashboard");
    await expect(welcomeModalHeading(page)).toBeVisible({ timeout: 10_000 });
    await page.getByRole("button", { name: "Turu Başlat" }).click();

    const rows = panel(page).locator("p.text-xs.font-medium");
    await expect(rows).toHaveCount(7, { timeout: 10_000 });
    await expect(panel(page)).toContainText("Rolünü ve çalışma alanını tanı");
    await expect(panel(page)).not.toContainText("Ajans profilini tamamla");
    await expect(panel(page)).not.toContainText("Takvim ve faturaları gör");
  });

  test("fresh brand user login shows the brand welcome modal; the panel lists exactly the 8 brand steps", async ({ page }) => {
    await loginBrand(page, brand.brandOwnerEmail);
    await page.goto("/brand/dashboard");
    await expect(page.getByRole("heading", { name: "Marka portalına hoş geldiniz" })).toBeVisible({
      timeout: 10_000,
    });
    await page.getByRole("button", { name: "Turu Başlat" }).click();

    const rows = panel(page).locator("p.text-xs.font-medium");
    await expect(rows).toHaveCount(8, { timeout: 10_000 });
    await expect(panel(page)).toContainText("Marka portalını tanı");
    await expect(panel(page)).not.toContainText("Ajans profilini tamamla");
  });
});

// ── Spotlight: real DOM highlight, including the view-step regression ───────

test.describe("Spotlight highlighting", () => {
  test("an action-kind step's CTA highlights its real sidebar nav target", async ({ page }) => {
    const runId = "onb-spot-action";
    const fx = seedAgencyFixture(runId);
    try {
      await loginAgency(page, fx.ownerEmail);
      await page.goto("/dashboard");
      await openPanelViaLauncher(page);

      // This fixture (e2e_seed_mention_onboarding_agency.py) always seeds a
      // real brand/brief/deliverable/mention alongside the owner, so
      // agency_profile/first_brand/invite_team/first_brief/first_deliverable/
      // comment_mention_annotation are already complete from creation
      // (OnboardingService's real-data checks) — time_tracking is the first
      // genuinely incomplete action-kind step for this owner, at fixed
      // position 4 of the 7 incomplete steps (welcome, preview_center,
      // brand_portal_preview precede it; capacity/notification_preferences/
      // summary follow), so "ADIM 4/7" below is this fixture's fixed shape,
      // not a bespoke guess.
      await panel(page).getByText("Zaman Takibi", { exact: true }).click(); // time_tracking
      await page.waitForURL((url) => url.pathname === "/dashboard/time/my", { timeout: 10_000 });

      const target = page.locator('[data-onboarding-target="/dashboard/time"]');
      await expect(target).toBeVisible({ timeout: 10_000 });
      const box = await highlightBox(page).boundingBox();
      const targetBox = await target.boundingBox();
      expect(box).not.toBeNull();
      expect(targetBox).not.toBeNull();
      if (box && targetBox) {
        // The highlight is the target's rect + HIGHLIGHT_PADDING(6) on each side.
        expect(Math.abs(box.x - (targetBox.x - 6))).toBeLessThan(4);
        expect(Math.abs(box.width - (targetBox.width + 12))).toBeLessThan(4);
      }
      await expect(page.getByText("ADIM 4/7")).toBeVisible();
      await expect(page.getByText("Zaman takibini aç")).toBeVisible();
    } finally {
      cleanupAgencyFixture(runId);
    }
  });

  test("a view-kind step's CTA also highlights its target (regression: previously never rendered — fixed upstream in OnboardingWizard.tsx, see report)", async ({ page }) => {
    const runId = "onb-spot-view";
    const fx = seedAgencyFixture(runId);
    try {
      await loginAgency(page, fx.ownerEmail);
      await page.goto("/dashboard");
      await openPanelViaLauncher(page);

      await panel(page).getByText("Markaları Gör", { exact: true }).click(); // brand_portal_preview (kind: view)
      await page.waitForURL((url) => url.pathname === "/dashboard/brands", { timeout: 10_000 });

      await expect(highlightBox(page)).toBeVisible({ timeout: 10_000 });
      await expect(page.getByText("Marka portalını önizle")).toBeVisible();
      const target = page.locator('[data-onboarding-target="/dashboard/brands"]');
      await expect(target).toBeVisible();

      // "İleri" must still advance to the next step instead of silently
      // vanishing (the pre-fix symptom the orchestrator observed).
      await page.getByRole("button", { name: "İleri" }).click();
      await expect(highlightBox(page).or(page.getByText("şu an ekranda değil"))).toBeVisible({ timeout: 5_000 });
    } finally {
      cleanupAgencyFixture(runId);
    }
  });
});

// ── Spotlight: target-not-found fallback ─────────────────────────────────────

test.describe("Spotlight fallback when the target can't be resolved", () => {
  test("obscuring the real nav target forces the 'not on screen' fallback, and its 'Sayfayı Aç' button still navigates correctly", async ({ page }) => {
    const runId = "onb-fallback";
    const fx = seedAgencyFixture(runId);
    try {
      // The product has no natural case where a step's own sidebar target is
      // absent while its route is reachable (every AGENCY_OWNER_STEPS target
      // is a non-ownerOnly nav item, always rendered for the owner) — so this
      // deterministically forces the not-found branch by making
      // document.querySelectorAll return an empty list for exactly this one
      // selector — SpotlightOverlay.tsx's findVisibleTarget() calls
      // querySelectorAll (not querySelector) to skip CSS-hidden duplicates
      // (desktop sidebar vs. mobile drawer sharing the same
      // data-onboarding-target), so that's the call that must be patched.
      // Documented per the task's instruction to construct a realistic
      // trigger or say what was done.
      await loginAgency(page, fx.ownerEmail);
      await page.goto("/dashboard");
      await page.evaluate(() => {
        const selector = '[data-onboarding-target="/dashboard/brands"]';
        const orig = document.querySelectorAll.bind(document);
        document.querySelectorAll = ((s: string) =>
          s === selector ? document.createDocumentFragment().querySelectorAll(s) : orig(s)) as typeof document.querySelectorAll;
      });

      await openPanelViaLauncher(page);
      // first_brand is already complete in this fixture (it always seeds one
      // real Brand), so its CTA row wouldn't render — brand_portal_preview
      // shares the identical "/dashboard/brands" target and is genuinely
      // incomplete, so it exercises the same not-found branch.
      await panel(page).getByText("Markaları Gör", { exact: true }).click(); // brand_portal_preview, target /dashboard/brands
      await page.waitForURL((url) => url.pathname === "/dashboard/brands", { timeout: 10_000 });

      await expect(page.getByText("Bu adımın hedefi şu an ekranda değil.")).toBeVisible({ timeout: 5_000 });
      const openPageBtn = page.getByRole("button", { name: "Sayfayı Aç" });
      await expect(openPageBtn).toBeVisible();
      await openPageBtn.click();
      await page.waitForURL((url) => url.pathname === "/dashboard/brands", { timeout: 10_000 });
    } finally {
      cleanupAgencyFixture(runId);
    }
  });
});

// ── Step CTA navigation ───────────────────────────────────────────────────────

test.describe("Step CTA navigation", () => {
  test("clicking a step's CTA navigates to that step's real route", async ({ page }) => {
    const runId = "onb-navigation";
    const fx = seedAgencyFixture(runId);
    try {
      await loginAgency(page, fx.ownerEmail);
      await page.goto("/dashboard");
      await openPanelViaLauncher(page);

      // first_brief/invite_team are already complete in this fixture (it
      // always seeds one real Brief and 3 real AgencyMembers) — time_tracking
      // and capacity are genuinely incomplete action-kind steps with distinct
      // real routes, exercising the same "CTA navigates to its real route"
      // behavior.
      await panel(page).getByText("Zaman Takibi", { exact: true }).click(); // time_tracking
      await page.waitForURL((url) => url.pathname === "/dashboard/time/my", { timeout: 10_000 });

      await page.goto("/dashboard");
      await openPanelViaLauncher(page);
      await panel(page).getByText("Kapasite Ayarla", { exact: true }).click(); // capacity
      await page.waitForURL((url) => url.pathname === "/dashboard/capacity/schedule", { timeout: 10_000 });
    } finally {
      cleanupAgencyFixture(runId);
    }
  });
});

// ── Real action completes an action-kind step ────────────────────────────────

test.describe("Action-step completion via a real UI action", () => {
  test("toggling a real notification preference marks notification_preferences complete on next fetch", async ({ page }) => {
    const runId = "onb-action-step";
    const fx = seedAgencyFixture(runId);
    try {
      await loginAgency(page, fx.ownerEmail);
      await page.goto("/dashboard");
      await openPanelViaLauncher(page);
      await expect(panel(page)).toContainText("Bildirim tercihlerini düzenle");
      // Not yet completed: its CTA row is still visible.
      const stepRow = panel(page).locator("div", { has: page.getByText("Bildirim tercihlerini düzenle") }).first();
      await expect(stepRow.getByRole("button", { name: "Bildirimler" })).toBeVisible();
      await page.locator("body").click({ position: { x: 5, y: 5 } }); // close panel overlay

      await page.goto("/dashboard/settings/notifications");
      const toggle = page.getByRole("switch").first();
      await expect(toggle).toBeVisible({ timeout: 10_000 });
      const before = await toggle.getAttribute("aria-checked");
      await toggle.click();
      await expect(toggle).not.toHaveAttribute("aria-checked", before ?? "", { timeout: 10_000 });

      await page.goto("/dashboard"); // hard client nav to force a fresh progress fetch
      await openPanelViaLauncher(page);
      const completedTitle = panel(page).getByText("Bildirim tercihlerini düzenle");
      await expect(completedTitle).toHaveClass(/line-through/, { timeout: 10_000 });
    } finally {
      cleanupAgencyFixture(runId);
    }
  });
});

// ── View-step completion via direct navigation (no wizard) ──────────────────

test.describe("View-step completion via direct navigation", () => {
  const RUN_ID = "onb-view-step";
  let fx: AgencyFixture;

  test.beforeAll(() => {
    fx = seedAgencyFixture(RUN_ID);
  });

  test.afterAll(() => {
    cleanupAgencyFixture(RUN_ID);
  });

  test("navigating directly to /dashboard/briefs and /dashboard/brands completes preview_center and brand_portal_preview without opening the wizard", async ({ page }) => {
    await loginAgency(page, fx.ownerEmail);
    await page.goto("/dashboard/briefs");
    await page.waitForLoadState("networkidle");
    await page.goto("/dashboard/brands");
    await page.waitForLoadState("networkidle");

    await page.goto("/dashboard");
    await openPanelViaLauncher(page);
    await expect(panel(page).getByText("Preview Center'ı gör")).toHaveClass(/line-through/, { timeout: 10_000 });
    await expect(panel(page).getByText("Marka portalını önizle")).toHaveClass(/line-through/, { timeout: 10_000 });
  });

  test("real behavior differs from the assumed doc: /dashboard/time and /dashboard/capacity do NOT complete time_tracking/capacity for the owner (they're action-kind, requiring a real TimeEntry/WorkSchedule row — only preview_center and brand_portal_preview are true view-kind steps for the owner)", async ({ page }) => {
    await loginAgency(page, fx.ownerEmail);
    await page.goto("/dashboard/time");
    await page.waitForLoadState("networkidle");
    await page.goto("/dashboard/capacity");
    await page.waitForLoadState("networkidle");

    await page.goto("/dashboard");
    await openPanelViaLauncher(page);
    await expect(panel(page).getByText("Zaman takibini aç")).not.toHaveClass(/line-through/);
    await expect(panel(page).getByText("Çalışma kapasitesi belirle")).not.toHaveClass(/line-through/);
  });
});

// ── Dismiss / launcher / reload persistence ──────────────────────────────────

test.describe("Dismiss, relaunch, and persistence", () => {
  const RUN_1 = "onb-dismiss-1"; // owner (test 1) + designer (test 2) — independent identities, no shared mutable state
  const RUN_3 = "onb-dismiss-3"; // dedicated fresh owner for test 3, so it never depends on test 1's residue

  let fx1: AgencyFixture;
  let fx3: AgencyFixture;

  test.beforeAll(() => {
    fx1 = seedAgencyFixture(RUN_1, "fresh");
    fx3 = seedAgencyFixture(RUN_3, "fresh");
  });

  test.afterAll(() => {
    cleanupAgencyFixture(RUN_1);
    cleanupAgencyFixture(RUN_3);
  });

  test("'Daha Sonra' closes the wizard and it does not reopen within the same session; the floating launcher reopens the panel manually", async ({ page }) => {
    await loginAgency(page, fx1.ownerEmail);
    await page.goto("/dashboard");
    await expect(welcomeModalHeading(page)).toBeVisible({ timeout: 10_000 });
    await page.getByRole("button", { name: "Daha Sonra" }).click();
    await expect(welcomeModalHeading(page)).not.toBeVisible();

    await page.reload();
    await page.waitForLoadState("networkidle");
    await expect(welcomeModalHeading(page)).not.toBeVisible({ timeout: 3_000 });

    await openPanelViaLauncher(page);
    await expect(panel(page)).toBeVisible({ timeout: 5_000 });
  });

  test("a hard reload preserves progress made through the wizard", async ({ page }) => {
    await loginAgency(page, fx1.designerEmail);
    await page.goto("/dashboard");
    // fx1 is seeded "fresh" (this describe needs undismissed state for test 1
    // above) — the designer's welcome modal auto-shows here too, and its
    // full-screen backdrop (z-[110]) intercepts clicks on the floating
    // launcher underneath, so open the panel via "Turu Başlat" directly
    // instead of racing the launcher.
    await expect(welcomeModalHeading(page)).toBeVisible({ timeout: 10_000 });
    await page.getByRole("button", { name: "Turu Başlat" }).click();
    await panel(page).getByText("Panele Git", { exact: true }).click(); // role_intro (view)
    await page.waitForURL((url) => url.pathname === "/dashboard", { timeout: 10_000 });

    await page.reload();
    await page.waitForLoadState("networkidle");
    await openPanelViaLauncher(page);
    await expect(panel(page).getByText("Rolünü ve çalışma alanını tanı")).toHaveClass(/line-through/, {
      timeout: 10_000,
    });
  });

  test("once the wizard has been engaged (current_step set server-side by a real view-kind step), a brand-new browser context (fresh session) does not force-reopen the welcome modal", async ({
    page,
    browser,
  }) => {
    await loginAgency(page, fx3.ownerEmail);
    await page.goto("/dashboard");
    // Engage the wizard with a real VIEW-kind step: only view-kind steps call
    // POST .../step/{key}/seen (see OnboardingWizard.tsx's handleDoNow),
    // which is what actually persists OnboardingProgress.current_step
    // server-side (OnboardingService.mark_step_seen). Clicking an
    // action-kind step's CTA (e.g. "Ajans Ayarları") never does this, so it
    // would leave current_step null and make the "fresh context doesn't
    // reopen the modal" assertion below flaky/order-dependent — this is the
    // real root cause the previous version of this test masked by
    // accidentally inheriting persisted state from an unrelated describe
    // block earlier in the file. This test now sets its own precondition.
    await expect(welcomeModalHeading(page)).toBeVisible({ timeout: 10_000 });
    await page.getByRole("button", { name: "Turu Başlat" }).click();
    await panel(page).getByText("Markaları Gör", { exact: true }).click(); // brand_portal_preview (view-kind)
    await page.waitForURL((url) => url.pathname === "/dashboard/brands", { timeout: 10_000 });

    const freshContext = await browser.newContext();
    const freshPage = await freshContext.newPage();
    await loginAgency(freshPage, fx3.ownerEmail);
    await freshPage.goto("/dashboard");
    await expect(welcomeModalHeading(freshPage)).not.toBeVisible({ timeout: 5_000 });
    await freshContext.close();
  });
});

// ── Server-side authorization ─────────────────────────────────────────────────

test.describe("OnboardingProgress authorization", () => {
  const RUN_ID = "onb-auth";
  let fx: AgencyFixture;

  test.beforeAll(() => {
    fx = seedAgencyFixture(RUN_ID);
  });

  test.afterAll(() => {
    cleanupAgencyFixture(RUN_ID);
  });

  test("progress is always derived server-side from the caller's own JWT — two different users under the same agency get two different, independently-scoped progress records", async ({ request }) => {
    const ownerLogin = await request.post("/api/v1/auth/login", {
      data: { email: fx.ownerEmail, password: PASSWORD },
    });
    const designerLogin = await request.post("/api/v1/auth/login", {
      data: { email: fx.designerEmail, password: PASSWORD },
    });
    expect(ownerLogin.ok()).toBeTruthy();
    expect(designerLogin.ok()).toBeTruthy();
    const ownerToken = (await ownerLogin.json()).access_token as string;
    const designerToken = (await designerLogin.json()).access_token as string;

    const ownerProgress = await request.get("/api/v1/onboarding/progress", {
      headers: { Authorization: `Bearer ${ownerToken}`, "X-Agency-ID": fx.agencyId },
    });
    const designerProgress = await request.get("/api/v1/onboarding/progress", {
      headers: { Authorization: `Bearer ${designerToken}`, "X-Agency-ID": fx.agencyId },
    });
    expect(ownerProgress.ok()).toBeTruthy();
    expect(designerProgress.ok()).toBeTruthy();
    const ownerBody = await ownerProgress.json();
    const designerBody = await designerProgress.json();

    // Different identities under the identical agency header must never
    // collapse to the same progress row or the same derived type — there is
    // no id/user-id parameter anywhere in this API surface for a caller to
    // even attempt to request someone else's state with.
    expect(ownerBody.id).not.toBe(designerBody.id);
    expect(ownerBody.onboarding_type).toBe("agency_owner_admin");
    expect(designerBody.onboarding_type).toBe("agency_member");
  });
});

// ── Viewport spot-checks ──────────────────────────────────────────────────────

test.describe("Onboarding spotlight across viewports", () => {
  const RUN_ID = "onb-viewport";
  let fx: AgencyFixture;

  test.beforeAll(() => {
    fx = seedAgencyFixture(RUN_ID);
  });

  test.afterAll(() => {
    cleanupAgencyFixture(RUN_ID);
  });

  for (const vp of [
    { name: "tablet 1024x768", width: 1024, height: 768 },
    { name: "mobile 390x844", width: 390, height: 844 },
  ]) {
    test.describe(`Onboarding spotlight @ ${vp.name}`, () => {
      test.use({ viewport: { width: vp.width, height: vp.height } });

      test("spotlight tooltip stays within the viewport and no horizontal page overflow, interaction still works", async ({ page }) => {
        await loginAgency(page, fx.ownerEmail);
        await page.goto("/dashboard");

        const overflow = await page.evaluate(() => document.body.scrollWidth - document.body.clientWidth);
        expect(overflow).toBeLessThanOrEqual(1);

        await openPanelViaLauncher(page);
        // agency_profile is already complete in this fixture (real Agency
        // always has a name) — time_tracking is the first genuinely
        // incomplete action-kind step (position 4 of 7, same fixed shape as
        // the "Spotlight highlighting" describe above).
        await panel(page).getByText("Zaman Takibi", { exact: true }).click(); // time_tracking
        await page.waitForURL((url) => url.pathname === "/dashboard/time/my", { timeout: 10_000 });

        const tooltip = page.getByText("ADIM 4/7").locator("../..");
        const box = await tooltip.boundingBox();
        expect(box).not.toBeNull();
        if (box) {
          expect(box.x).toBeGreaterThanOrEqual(0);
          expect(box.x + box.width).toBeLessThanOrEqual(vp.width + 1);
          expect(box.y).toBeGreaterThanOrEqual(0);
          expect(box.y + box.height).toBeLessThanOrEqual(vp.height + 1);
        }

        const overflowAfter = await page.evaluate(() => document.body.scrollWidth - document.body.clientWidth);
        expect(overflowAfter).toBeLessThanOrEqual(1);

        await page.getByRole("button", { name: "İleri" }).click(); // advances to capacity
        await expect(page.getByText("ADIM 5/7").or(page.getByText("şu an ekranda değil"))).toBeVisible({
          timeout: 5_000,
        });
      });
    });
  }
});
