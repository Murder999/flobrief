import { test, expect, type Page } from "@playwright/test";
import { execFileSync } from "node:child_process";
import path from "node:path";
import { dismissOnboardingIfVisible } from "./helpers/onboarding";

/**
 * Critical flow: brand user clicks a point on a submitted deliverable image,
 * leaves a revision note, agency replies and resolves it, brand reopens it.
 *
 * Self-seeds its fixture fresh in beforeAll/afterAll (same execFileSync +
 * parsed-env pattern as onboarding-flow.spec.ts / mention-flow.spec.ts) via
 * the tracked apps/backend/scripts/e2e_seed_annotation_flow.py — replaces
 * the previous ad-hoc, gitignored `_tmp_annotation_e2e_seed.py` dependency
 * that made this spec always skip on a fresh clone.
 */

const BACKEND_DIR = path.resolve(__dirname, "../../backend");
const PYTHON = process.env.E2E_PYTHON ?? path.join(BACKEND_DIR, ".venv", "Scripts", "python.exe");

function runSeedScript(script: string, args: string[]): Record<string, string> {
  const output = execFileSync(PYTHON, [`scripts/${script}`, ...args], {
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

let AGENCY_EMAIL: string;
let BRAND_EMAIL: string;
let PASSWORD: string;
let BRIEF_ID: string;

test.beforeAll(() => {
  const seeded = runSeedScript("e2e_seed_annotation_flow.py", ["seed"]);
  AGENCY_EMAIL = seeded.E2E_AGENCY_EMAIL;
  BRAND_EMAIL = seeded.E2E_BRAND_EMAIL;
  PASSWORD = seeded.E2E_PASSWORD;
  BRIEF_ID = seeded.E2E_BRIEF_ID;
  if (!AGENCY_EMAIL || !BRAND_EMAIL || !PASSWORD || !BRIEF_ID) {
    throw new Error("annotation-flow fixture seed did not return the expected env vars");
  }
});

test.afterAll(() => {
  runSeedScript("e2e_seed_annotation_flow.py", ["cleanup"]);
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

/**
 * Dev-mode-only quirk: React StrictMode double-invokes the refresh-session
 * effect on a hard reload, which can race against refresh-token rotation and
 * occasionally bounce an authenticated user back to the login screen. Retry
 * the navigation once rather than failing the whole flow on that flake.
 * (Not observed against a production build — this is a `next dev` safety net.)
 */
async function gotoAuthenticated(page: Page, url: string, loginPathPattern: RegExp) {
  await page.goto(url);
  if (loginPathPattern.test(new URL(page.url()).pathname)) {
    await page.waitForTimeout(500);
    await page.goto(url);
  }
}

test("brand pins a revision, agency resolves it, brand reopens it", async ({ page }) => {
  // ── 1. Brand logs in and opens the brief ────────────────────────────────
  await loginBrand(page);
  await gotoAuthenticated(page, `/brand/briefs/${BRIEF_ID}`, /\/brand\/login$/);
  // The deliverable workspace has no accordion — the latest deliverable's
  // asset is visible immediately, no expand step needed.
  await expect(page.getByText("E2E Görsel")).toBeVisible({ timeout: 15_000 });

  // No open revisions yet.
  await expect(page.getByText(/açık revizyon noktası/)).toHaveCount(0);

  // ── 2. Enter annotation mode and click on the image ─────────────────────
  await page.getByRole("button", { name: "Revizyon Noktası Belirle" }).click();
  const img = page.locator("img[alt='Deliverable']");
  await img.waitFor({ state: "visible" });
  // Wait for the blob-loaded image to actually decode before clicking —
  // AnnotationCanvas ignores clicks until it can compute the rendered rect.
  await page.waitForFunction(() => {
    const el = document.querySelector<HTMLImageElement>("img[alt='Deliverable']");
    return !!el && el.complete && el.naturalWidth > 0;
  }, { timeout: 20_000 });
  const canvas = img.locator("..");
  // Scene height is clamp(520px, 62vh, 760px) — scroll into view before clicking so
  // the click lands on the image rather than below an unscrolled viewport's fold.
  await canvas.scrollIntoViewIfNeeded();
  const box = await canvas.boundingBox();
  if (!box) throw new Error("annotation canvas has no bounding box");
  await canvas.click({ position: { x: box.width / 2, y: box.height / 2 } });

  // ── 3. Composer opens; write the revision note and save ────────────────
  await expect(page.getByPlaceholder("Bu noktadaki revizyon talebini yazın…")).toBeVisible();
  await page.getByPlaceholder("Bu noktadaki revizyon talebini yazın…").fill("Logoyu büyütür müsünüz?");
  await page.getByRole("button", { name: "Kaydet" }).click();

  // ── 4. Marker (#1) and sidebar entry both appear. The just-saved annotation's
  // detail popover also stays open showing the same text, so there are now two
  // matches (popover + sidebar row) — that's the intended anchored-popover UX.
  await expect(page.getByRole("button", { name: /Açık revizyon #1/ })).toBeVisible({ timeout: 10_000 });
  await expect(page.getByText("Logoyu büyütür müsünüz?").first()).toBeVisible();

  // Resize the viewport — marker must recompute against the rendered image
  // rect, not disappear or fall into letterbox space.
  await page.setViewportSize({ width: 900, height: 800 });
  await expect(page.getByRole("button", { name: /Açık revizyon #1/ })).toBeVisible();
  await page.setViewportSize({ width: 1280, height: 900 });

  // ── 5. Agency logs in, sees the annotation, replies, resolves it ───────
  await loginAgency(page);
  await gotoAuthenticated(page, `/dashboard/briefs/${BRIEF_ID}`, /\/auth\/(login|agency-login)$/);
  // "Teslimler" also appears as an inline link inside the "Genel" tab body
  // ("Yorumlara Eklenen Görseller" section), so the old broad regex matched
  // two elements and its .catch() silently swallowed the resulting strict-mode
  // violation, leaving the page on "Genel" with no annotation ever visible.
  await page.getByRole("button", { name: "Teslimler" }).first().click();
  await expect(page.getByText("Logoyu büyütür müsünüz?").first()).toBeVisible({ timeout: 15_000 });
  await page.getByText("Logoyu büyütür müsünüz?").first().click();

  const replyInput = page.getByPlaceholder("Yanıtla…");
  await replyInput.fill("Tamam, büyütüyorum.");
  await replyInput.press("Enter");
  await expect(page.getByText("Tamam, büyütüyorum.")).toBeVisible({ timeout: 10_000 });
  await page.getByRole("button", { name: "Çözüldü Yap" }).click();
  await expect(page.getByText("Çözüldü").first()).toBeVisible({ timeout: 10_000 });

  // ── 6. Brand sees resolved status and reopens it ────────────────────────
  await loginBrand(page);
  await gotoAuthenticated(page, `/brand/briefs/${BRIEF_ID}`, /\/brand\/login$/);
  await page.getByText("Logoyu büyütür müsünüz?").first().click();
  await expect(page.getByRole("button", { name: "Yeniden Aç" })).toBeVisible({ timeout: 10_000 });
  await page.getByRole("button", { name: "Yeniden Aç" }).click();
  await expect(page.getByText(/açık revizyon noktası/)).toBeVisible({ timeout: 10_000 });
});
