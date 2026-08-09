import { test, expect, type Page } from "@playwright/test";
import { execFileSync } from "node:child_process";
import path from "node:path";

import { dismissOnboardingIfVisible } from "./helpers/onboarding";

/**
 * Regression suite for the redesigned brand-portal brief detail page
 * (apps/frontend/app/brand/briefs/[id]/page.tsx): no-accordion deliverable
 * workspace, version strip switching, the "Revizyon Noktası Belirle" flow,
 * lightbox behavior, download, the Yorumlar/Aktivite tab panel, attachment
 * dedup, and responsive layout.
 *
 * Fixture is seeded via apps/backend/scripts/e2e_seed_brief_workspace.py
 * (real deliverables API, two submitted deliverables + one plain brief
 * reference asset) so this spec never touches production data. That script
 * is tracked in git (unlike the throwaway scripts/_tmp_*.py debug scripts)
 * and refuses to run against anything but a local, non-production database.
 */

const PASSWORD = "E2eTest1234!";
const BACKEND_DIR = path.resolve(__dirname, "../../backend");
const PYTHON = process.env.E2E_PYTHON ?? path.join(BACKEND_DIR, ".venv", "Scripts", "python.exe");

let BRAND_EMAIL: string;
let BRIEF_ID: string;
let AGENCY_ID: string;

function runSeedScript(args: string[]): Record<string, string> {
  const output = execFileSync(PYTHON, ["scripts/e2e_seed_brief_workspace.py", ...args], {
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
  BRAND_EMAIL = env.E2E_BRAND_EMAIL;
  BRIEF_ID = env.E2E_BRIEF_ID;
  AGENCY_ID = env.__AGENCY_ID__;
  if (!BRAND_EMAIL || !BRIEF_ID) {
    throw new Error("brief-workspace fixture seed did not return the expected env vars");
  }
});

test.afterAll(() => {
  if (AGENCY_ID) runSeedScript(["cleanup", AGENCY_ID]);
});

async function loginBrand(page: Page) {
  await page.goto("/brand/login");
  await page.waitForLoadState("networkidle");
  await page.locator("#brand-email").fill(BRAND_EMAIL);
  await page.locator("#brand-password").fill(PASSWORD);
  await page.getByRole("button", { name: "Marka Portalına Giriş Yap" }).click();
  await page.waitForURL((url) => url.pathname.startsWith("/brand") && url.pathname !== "/brand/login", {
    timeout: 15_000,
  });
}

async function gotoAuthenticated(page: Page, url: string, loginPathPattern: RegExp) {
  await page.goto(url);
  if (loginPathPattern.test(new URL(page.url()).pathname)) {
    await page.waitForTimeout(500);
    await page.goto(url);
  }
}

async function gotoBrief(page: Page) {
  await loginBrand(page);
  await gotoAuthenticated(page, `/brand/briefs/${BRIEF_ID}`, /\/brand\/login$/);
  await dismissOnboardingIfVisible(page);
  // (1) No accordion — the latest deliverable's filename is visible immediately,
  // with no expand click required.
  await expect(page.getByText("e2e-workspace-v2.png")).toBeVisible({ timeout: 15_000 });
}

test("deliverable workspace: latest version shown, no accordion, thumbnail switches main preview", async ({ page }) => {
  await gotoBrief(page);

  // (2) The most recently submitted deliverable (v2) is the one shown big.
  await expect(page.getByText("e2e-workspace-v2.png")).toBeVisible();

  // (3) Selecting the older version's thumbnail swaps the main preview —
  // no accordion row expands, the toolbar filename just changes.
  await page.getByTitle(/E2E Workspace Görsel v1/).click();
  await expect(page.getByText("e2e-workspace-v1.png")).toBeVisible({ timeout: 10_000 });
  await expect(page.getByText("e2e-workspace-v2.png")).toHaveCount(0);

  // Switch back to v2 for the rest of the suite's assumptions.
  await page.getByTitle(/E2E Workspace Görsel v2/).click();
  await expect(page.getByText("e2e-workspace-v2.png")).toBeVisible({ timeout: 10_000 });
});

test("revision-point button is prominent, opens annotation mode, and Büyüt never creates a marker", async ({ page }) => {
  await gotoBrief(page);

  const revisionButton = page.getByRole("button", { name: "Revizyon Noktası Belirle" });
  // (4) The action is a clearly visible, real button (not a silent link).
  await expect(revisionButton).toBeVisible();

  // (7) Büyüt opens the lightbox and must never toggle annotation mode / add a marker.
  const markersBefore = await page.getByRole("button", { name: /Açık revizyon/ }).count();
  await page.getByTitle("Büyüt").click();
  const dialog = page.locator('[role="dialog"][aria-modal="true"]').last();
  await expect(dialog).toBeVisible();
  // (8) Lightbox always has a visible close affordance.
  await expect(page.getByTitle("Kapat")).toBeVisible();
  await expect(page.getByRole("button", { name: /Açık revizyon/ })).toHaveCount(markersBefore);
  await expect(revisionButton).toBeVisible(); // still says "Belirle", not "Kapat" — mode wasn't toggled

  // (9) Escape closes the lightbox.
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();

  // (5) The button itself does open annotation mode, with the on-canvas helper hint.
  await revisionButton.click();
  await expect(page.getByText("Revize edilmesini istediğiniz noktaya tıklayın.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Revizyon Modunu Kapat" })).toBeVisible();

  // (6) Clicking the image while in annotation mode opens the composer.
  const img = page.locator("img[alt='Deliverable']");
  await img.waitFor({ state: "visible" });
  await page.waitForFunction(() => {
    const el = document.querySelector<HTMLImageElement>("img[alt='Deliverable']");
    return !!el && el.complete && el.naturalWidth > 0;
  }, { timeout: 20_000 });
  const canvas = img.locator("..");
  // The scene is deliberately taller than a default viewport (clamp(520px, 62vh, 760px)),
  // so scroll it into view before clicking — a raw page.mouse.click at an unscrolled
  // coordinate would land below the fold and silently miss the image.
  await canvas.scrollIntoViewIfNeeded();
  const box = await canvas.boundingBox();
  if (!box) throw new Error("annotation canvas has no bounding box");
  await canvas.click({ position: { x: box.width / 2, y: box.height / 2 } });
  await expect(page.getByPlaceholder("Bu noktadaki revizyon talebini yazın…")).toBeVisible();

  // Leave no residue — cancel the composer and exit annotation mode.
  await page.getByRole("button", { name: "Vazgeç" }).click();
  await page.getByRole("button", { name: "Revizyon Modunu Kapat" }).click();
});

test("download button hits the real asset endpoint", async ({ page }) => {
  await gotoBrief(page);

  const downloadRequests: string[] = [];
  page.on("request", (req) => {
    if (/\/api\/v1\/assets\/[^/]+\/download$/.test(req.url())) downloadRequests.push(req.url());
  });

  // (10)
  await page.getByTitle("İndir").click();
  await page.waitForTimeout(500);
  expect(downloadRequests.length).toBeGreaterThan(0);
  expect(downloadRequests[0]).toMatch(/\/api\/v1\/assets\/[0-9a-f-]+\/download$/);
});

test("communication panel: Yorumlar/Aktivite tabs both work", async ({ page }) => {
  await gotoBrief(page);

  // (11)
  await expect(page.getByPlaceholder("Yorumunuzu yazın...")).toBeVisible();
  await page.getByRole("tab", { name: "Aktivite" }).click();
  await expect(page.getByPlaceholder("Yorumunuzu yazın...")).toBeHidden();
  await page.getByRole("tab", { name: /Yorumlar/ }).click();
  await expect(page.getByPlaceholder("Yorumunuzu yazın...")).toBeVisible();
});

test("brief attachments never duplicate or leak deliverable assets", async ({ page }) => {
  await gotoBrief(page);

  await expect(page.getByText("Brief Dosyaları ve Referansları")).toBeVisible();

  // (12)/(13) The plain reference asset shows exactly once on the page (it
  // only ever renders inside the attachments section); the two deliverable
  // assets — which render as raw, unlabeled <img> in the workspace, never as
  // a MediaGallery thumbnail with this alt text — never leak in there.
  // Uploaded assets get a UUID suffix on the server (see normalize_filename
  // in storage_service.py), so MediaPreview's alt text is never the exact
  // original filename — match by prefix instead.
  await expect(page.locator('img[alt^="e2e-workspace-ref"]')).toHaveCount(1, { timeout: 10_000 });
  expect(await page.locator('img[alt^="e2e-workspace-v1"]').count()).toBe(0);
  expect(await page.locator('img[alt^="e2e-workspace-v2"]').count()).toBe(0);
});

test("desktop layout uses the width; mobile has no horizontal overflow", async ({ page }) => {
  // (14) At a wide desktop viewport, the main workspace column is not
  // squeezed into a narrow strip with a huge empty right gutter.
  await page.setViewportSize({ width: 1440, height: 900 });
  await gotoBrief(page);
  const workspaceCard = page.getByTestId("deliverable-workspace");
  const box = await workspaceCard.boundingBox();
  expect(box).not.toBeNull();
  if (box) expect(box.width).toBeGreaterThan(650);

  // (15) At a mobile viewport, nothing forces horizontal scrolling.
  await page.setViewportSize({ width: 390, height: 844 });
  await page.waitForTimeout(300);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(1);
});
