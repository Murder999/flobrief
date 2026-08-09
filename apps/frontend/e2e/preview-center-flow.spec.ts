import { test, expect, type Page } from "@playwright/test";
import { execFileSync } from "node:child_process";
import path from "node:path";
import { dismissOnboardingIfVisible } from "./helpers/onboarding";

/**
 * Critical flow for the Social Media Preview Center (Module A):
 * agency uploads a deliverable (pre-seeded), configures a platform preview
 * (platform/format/caption, with autosave that never fires one request per
 * keystroke), reorders a carousel, switches platform, submits the
 * deliverable, then the brand logs in, opens the same preview, places an
 * annotation, and confirms it stays bound to the correct asset across a
 * raw/platform view-mode switch.
 *
 * Fixture is seeded via apps/backend/scripts/e2e_seed_preview_center.py (real
 * deliverables + assets API, one draft deliverable with two uploaded images)
 * so this spec never touches production data.
 */

const PASSWORD = "E2eTest1234!";
const BACKEND_DIR = path.resolve(__dirname, "../../backend");
const PYTHON = process.env.E2E_PYTHON ?? path.join(BACKEND_DIR, ".venv", "Scripts", "python.exe");

let AGENCY_EMAIL: string;
let BRAND_EMAIL: string;
let BRIEF_ID: string;
let AGENCY_ID: string;
let INDEPENDENT_A_ID: string;
let INDEPENDENT_B_ID: string;
let OLD_VERSION_ID: string;
let NEW_VERSION_ID: string;

function runSeedScript(args: string[]): Record<string, string> {
  const output = execFileSync(PYTHON, ["scripts/e2e_seed_preview_center.py", ...args], {
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
  AGENCY_EMAIL = env.E2E_AGENCY_EMAIL;
  BRAND_EMAIL = env.E2E_BRAND_EMAIL;
  BRIEF_ID = env.E2E_BRIEF_ID;
  AGENCY_ID = env.__AGENCY_ID__;
  INDEPENDENT_A_ID = env.E2E_INDEPENDENT_A_ID;
  INDEPENDENT_B_ID = env.E2E_INDEPENDENT_B_ID;
  OLD_VERSION_ID = env.E2E_OLD_VERSION_ID;
  NEW_VERSION_ID = env.E2E_NEW_VERSION_ID;
  if (!AGENCY_EMAIL || !BRAND_EMAIL || !BRIEF_ID || !INDEPENDENT_A_ID || !OLD_VERSION_ID) {
    throw new Error("preview-center fixture seed did not return the expected env vars");
  }
});

test.afterAll(() => {
  if (AGENCY_ID) runSeedScript(["cleanup", AGENCY_ID]);
});

async function loginAgency(page: Page) {
  await page.goto("/auth/agency-login");
  await page.locator("#agency-email").fill(AGENCY_EMAIL);
  await page.locator("#agency-password").fill(PASSWORD);
  await page.getByRole("button", { name: "Ajans Paneline Giriş Yap" }).click();
  await page.waitForURL((url) => url.pathname.startsWith("/dashboard"), { timeout: 15_000 });
  await dismissOnboardingIfVisible(page);
}

async function loginBrand(page: Page) {
  await page.goto("/brand/login");
  await page.locator("#brand-email").fill(BRAND_EMAIL);
  await page.locator("#brand-password").fill(PASSWORD);
  await page.getByRole("button", { name: "Marka Portalına Giriş Yap" }).click();
  await page.waitForURL((url) => url.pathname.startsWith("/brand") && url.pathname !== "/brand/login", {
    timeout: 15_000,
  });
  await dismissOnboardingIfVisible(page);
}

async function gotoAuthenticated(page: Page, url: string, loginPathPattern: RegExp) {
  await page.goto(url);
  if (loginPathPattern.test(new URL(page.url()).pathname)) {
    await page.waitForTimeout(500);
    await page.goto(url);
  }
}

test("agency configures platform preview; brand annotates it; binding survives reorder + view switch", async ({ page }) => {
  // ── 1. Agency opens the brief's Teslimler tab; the seeded draft deliverable auto-selects ──
  await loginAgency(page);
  await gotoAuthenticated(
    page,
    `/dashboard/briefs/${BRIEF_ID}?tab=uretim`,
    /\/auth\/(login|agency-login)$/,
  );
  await expect(page.getByText("E2E Preview Deliverable").first()).toBeVisible({ timeout: 15_000 });

  // ── 2. Switch to the Platform Önizlemesi tab — visible immediately since the
  // deliverable is still draft (canEdit), even before any config exists. ────
  await page.getByRole("tab", { name: "Platform Önizlemesi" }).click();
  await expect(page.getByLabel("Platform seçimi")).toBeVisible({ timeout: 10_000 });

  // ── 3. Type a caption via real keystrokes; must never fire one PUT per
  // keystroke — only after the debounce window elapses. ──────────────────
  const configPutRequests: string[] = [];
  page.on("request", (req) => {
    if (req.method() === "PUT" && /\/preview-config$/.test(req.url())) {
      configPutRequests.push(req.url());
    }
  });

  const captionInput = page.locator("#preview-caption");
  await captionInput.click();
  await captionInput.pressSequentially("Yeni koleksiyonumuzu kaçırmayın!", { delay: 30 });
  // Typing itself must not have fired any PUT yet — the debounce window (1.5s) hasn't elapsed.
  expect(configPutRequests.length).toBe(0);

  // Wait past the debounce window for the single autosave to fire.
  await expect.poll(() => configPutRequests.length, { timeout: 5_000 }).toBeGreaterThan(0);
  const countAfterAutosave = configPutRequests.length;
  expect(countAfterAutosave).toBe(1);

  // ── 4. Switch format to a carousel shape — the carousel editor appears using
  // the deliverable's two real uploaded assets as slides. ─────────────────
  await page.getByLabel("Önizleme formatı").selectOption("feed_carousel");
  await expect(page.getByText(/Karüsel Sırası/)).toBeVisible({ timeout: 10_000 });
  await expect(page.getByText(/2 slayt/)).toBeVisible();

  // ── 5. Reorder: move the first slide down — a discrete action that saves
  // immediately (not debounced), unlike the caption field. ────────────────
  const slotPutRequests: string[] = [];
  page.on("request", (req) => {
    if (req.method() === "PUT" && /\/preview-slots$/.test(req.url())) {
      slotPutRequests.push(req.url());
    }
  });
  await page.getByRole("button", { name: "1. slaytı aşağı taşı" }).click();
  await expect.poll(() => slotPutRequests.length, { timeout: 5_000 }).toBeGreaterThan(0);

  // ── 6. Force an explicit save of platform/format/caption, then confirm the
  // live preview reflects it without a page reload. ───────────────────────
  await page.getByRole("button", { name: "Şimdi Kaydet" }).click();
  await expect(page.getByText("Yeni koleksiyonumuzu kaçırmayın!").first()).toBeVisible({ timeout: 10_000 });

  // ── 7. Switch platform to Facebook — the shell swaps chrome entirely once
  // saved (platform/format changes route through the same draft state as
  // the caption, so an explicit save makes this deterministic here). ──────
  await page.getByRole("button", { name: "Facebook", exact: true }).click();
  await page.getByRole("button", { name: "Şimdi Kaydet" }).click();
  await expect(page.getByText("Beğen").first()).toBeVisible({ timeout: 10_000 });

  // ── 8. Submit the deliverable so the brand can see it. ──────────────────
  await page.getByRole("button", { name: "Onaya Gönder" }).click();
  await expect(page.getByRole("button", { name: "Onaya Gönder" })).toHaveCount(0, { timeout: 10_000 });

  // ── 9. Brand logs in, opens the same preview, places an annotation ──────
  await loginBrand(page);
  await gotoAuthenticated(page, `/brand/briefs/${BRIEF_ID}`, /\/brand\/login$/);
  await expect(page.getByText("E2E Preview Deliverable").first()).toBeVisible({ timeout: 15_000 });

  await page.getByRole("tab", { name: "Platform Önizlemesi" }).click();
  await expect(page.getByText("Beğen").first()).toBeVisible({ timeout: 10_000 }); // still Facebook chrome

  await page.getByRole("button", { name: "Revizyon Noktası Belirle" }).click();
  const img = page.locator("img[alt='Deliverable']");
  await img.waitFor({ state: "visible" });
  await page.waitForFunction(() => {
    const el = document.querySelector<HTMLImageElement>("img[alt='Deliverable']");
    return !!el && el.complete && el.naturalWidth > 0;
  }, { timeout: 20_000 });
  const canvas = img.locator("..");
  await canvas.scrollIntoViewIfNeeded();
  const box = await canvas.boundingBox();
  if (!box) throw new Error("annotation canvas has no bounding box");
  await canvas.click({ position: { x: box.width / 2, y: box.height / 2 } });

  await expect(page.getByPlaceholder("Bu noktadaki revizyon talebini yazın…")).toBeVisible();
  await page.getByPlaceholder("Bu noktadaki revizyon talebini yazın…").fill("Bu slaytı biraz daha canlı yapalım.");
  await page.getByRole("button", { name: "Kaydet" }).click();
  await expect(page.getByRole("button", { name: /Açık revizyon #1/ })).toBeVisible({ timeout: 10_000 });

  // ── 10. Switch view mode away and back — the annotation must remain bound
  // to the correct asset/slide, not disappear or reattach elsewhere. ──────
  await page.getByRole("tab", { name: "Ham Dosya" }).click();
  await page.getByRole("tab", { name: "Platform Önizlemesi" }).click();
  await expect(page.getByRole("button", { name: /Açık revizyon #1/ })).toBeVisible({ timeout: 10_000 });
  await expect(page.getByText("Bu slaytı biraz daha canlı yapalım.").first()).toBeVisible();
});

test.describe("Deliverable version-chain fix (is_latest_version)", () => {
  // Regression coverage for the bug where DeliverableWorkspace.tsx treated
  // every deliverable on a brief as one shared version timeline — only the
  // most-recently-created deliverable in the WHOLE brief was "latest",
  // wrongly read-onlying independent, still-active siblings. The backend
  // now computes is_latest_version per title-chain
  // (app/services/deliverable_versioning.py); this exercises the brand
  // portal UI that consumes it.

  async function selectVersionStripThumb(page: Page, deliverableId: string) {
    await page.getByTestId(`version-strip-thumb-${deliverableId}`).click();
    // Selecting a deliverable remounts DeliverablePreviewPane (keyed by id),
    // resetting viewMode back to "raw" — must re-enter Platform Önizlemesi.
    await page.getByRole("tab", { name: "Platform Önizlemesi" }).click();
  }

  test("two independent deliverables both stay fully annotatable on the brand portal", async ({ page }) => {
    await loginBrand(page);
    await gotoAuthenticated(page, `/brand/briefs/${BRIEF_ID}`, /\/brand\/login$/);
    // The default-selected deliverable is whichever was submitted most
    // recently across the WHOLE brief (by design — see DeliverableWorkspace's
    // `sorted`), which by this point in the suite is "E2E Preview
    // Deliverable" from the first test. Only that one's title renders as
    // text up front; the others are reachable via their version-strip
    // thumbnail (unique data-testid), which is what this regression
    // actually needs to exercise.
    await expect(page.getByTestId("deliverable-workspace")).toBeVisible({ timeout: 15_000 });

    for (const id of [INDEPENDENT_A_ID, INDEPENDENT_B_ID]) {
      await selectVersionStripThumb(page, id);
      await expect(page.getByRole("button", { name: "Revizyon Noktası Belirle" })).toBeVisible({
        timeout: 10_000,
      });
    }
  });

  test("older row in a same-title chain is read-only; newer row stays annotatable", async ({ page }) => {
    await loginBrand(page);
    await gotoAuthenticated(page, `/brand/briefs/${BRIEF_ID}`, /\/brand\/login$/);
    await expect(page.getByTestId("deliverable-workspace")).toBeVisible({ timeout: 15_000 });

    await selectVersionStripThumb(page, OLD_VERSION_ID);
    await expect(page.getByRole("button", { name: "Revizyon Noktası Belirle" })).toHaveCount(0);

    await selectVersionStripThumb(page, NEW_VERSION_ID);
    await expect(page.getByRole("button", { name: "Revizyon Noktası Belirle" })).toBeVisible({
      timeout: 10_000,
    });

    // The independent deliverables from the previous test are unaffected by
    // this same-title chain existing elsewhere on the same brief.
    await selectVersionStripThumb(page, INDEPENDENT_A_ID);
    await expect(page.getByRole("button", { name: "Revizyon Noktası Belirle" })).toBeVisible({
      timeout: 10_000,
    });
  });

  test("agency portal still lists both rows of the same-title chain independently (no restriction, matches prior behavior)", async ({
    page,
  }) => {
    await loginAgency(page);
    await gotoAuthenticated(
      page,
      `/dashboard/briefs/${BRIEF_ID}?tab=uretim`,
      /\/auth\/(login|agency-login)$/,
    );
    // The title also appears a second time each in the "Üretim Özeti"
    // sidebar summary — real UI, not the thing under test. What matters is
    // that both rows of the chain are present as independently selectable
    // deliverable cards in the left list (agency never restricts either).
    const leftListCards = page.locator("button", { hasText: "E2E Version Chain Görseli" });
    await expect(leftListCards.first()).toBeVisible({ timeout: 15_000 });
    await expect(leftListCards).toHaveCount(2);
    for (let i = 0; i < 2; i++) {
      await leftListCards.nth(i).click();
      await expect(page.getByText("E2E Version Chain Görseli").first()).toBeVisible();
    }
  });
});
