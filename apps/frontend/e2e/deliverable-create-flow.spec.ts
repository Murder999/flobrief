import { test, expect, type Page } from "@playwright/test";
import { execFileSync } from "node:child_process";
import path from "node:path";
import { dismissOnboardingIfVisible } from "./helpers/onboarding";

/**
 * Regression coverage for the "add a second independent deliverable" gap:
 * a brief with at least one existing deliverable had no visible UI action
 * to create a second, independent one — NewDeliverableForm existed but was
 * never mounted (apps/frontend/app/dashboard/briefs/[id]/page.tsx).
 *
 * Fixture is seeded via apps/backend/scripts/e2e_seed_deliverable_create.py
 * (real deliverables API — one existing, submitted, annotatable
 * "Instagram Post" deliverable, plus an OWNER agency member who can create
 * and a VIEWER agency member who cannot), so this spec never touches
 * production data.
 */

const PASSWORD = "E2eTest1234!";
const BACKEND_DIR = path.resolve(__dirname, "../../backend");
const PYTHON = process.env.E2E_PYTHON ?? path.join(BACKEND_DIR, ".venv", "Scripts", "python.exe");

// 1x1 black PNG — enough for the backend's mime/type validation and for the
// UI to treat it as an annotatable image asset.
const TINY_PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=",
  "base64"
);

let OWNER_EMAIL: string;
let VIEWER_EMAIL: string;
let BRAND_EMAIL: string;
let BRIEF_ID: string;
let EXISTING_DELIVERABLE_ID: string;
let AGENCY_ID: string;

function runSeedScript(args: string[]): Record<string, string> {
  const output = execFileSync(PYTHON, ["scripts/e2e_seed_deliverable_create.py", ...args], {
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
  VIEWER_EMAIL = env.E2E_VIEWER_EMAIL;
  BRAND_EMAIL = env.E2E_BRAND_EMAIL;
  BRIEF_ID = env.E2E_BRIEF_ID;
  EXISTING_DELIVERABLE_ID = env.E2E_EXISTING_DELIVERABLE_ID;
  AGENCY_ID = env.__AGENCY_ID__;
  if (!OWNER_EMAIL || !VIEWER_EMAIL || !BRAND_EMAIL || !BRIEF_ID || !EXISTING_DELIVERABLE_ID) {
    throw new Error("deliverable-create fixture seed did not return the expected env vars");
  }
});

test.afterAll(() => {
  if (AGENCY_ID) runSeedScript(["cleanup", AGENCY_ID]);
});

// Same allowlist as agency-calendar.spec.ts — Next.js RSC-prefetch fallback
// noise, never a real application error.
const KNOWN_NOISE = /^Failed to load resource:|^Failed to fetch RSC payload/;

function trackConsoleErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error" && !KNOWN_NOISE.test(msg.text())) errors.push(msg.text());
  });
  page.on("pageerror", (err) => errors.push(err.message));
  return errors;
}

async function loginAgency(page: Page, email: string) {
  await page.goto("/auth/agency-login");
  await page.locator("#agency-email").fill(email);
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

test("owner adds a second independent deliverable via the mounted form; both stay listed, previewable, and annotatable", async ({
  page,
}) => {
  const consoleErrors = trackConsoleErrors(page);

  // (1) The existing deliverable is visible, and so is the "Yeni Teslim
  // Ekle" action — the exact affordance that was missing.
  await loginAgency(page, OWNER_EMAIL);
  await gotoAuthenticated(
    page,
    `/dashboard/briefs/${BRIEF_ID}?tab=uretim`,
    /\/auth\/(login|agency-login)$/
  );
  await expect(page.getByText("Instagram Post").first()).toBeVisible({ timeout: 15_000 });
  const addButton = page.getByRole("button", { name: "Yeni Teslim Ekle" });
  await expect(addButton).toBeVisible();

  // No modal until the button is clicked.
  await expect(page.getByRole("heading", { name: "Yeni Teslim Ekle" })).toHaveCount(0);
  await addButton.click();
  await expect(page.getByRole("heading", { name: "Yeni Teslim Ekle" })).toBeVisible();

  // (2) Fill and submit the mounted NewDeliverableForm inside the modal —
  // a second, independent deliverable (distinct title, not a new version
  // of "Instagram Post").
  const form = page.locator("form", { hasText: "Yeni Deliverable" });
  await form.getByPlaceholder("Başlık (örn: Instagram Carousel Görseli)").fill("LinkedIn Tasarımı");
  await form.locator("select").selectOption("image");
  await form.getByPlaceholder("Kısa açıklama (opsiyonel)").fill("LinkedIn kare görsel");

  const createResponsePromise = page.waitForResponse(
    (resp) => resp.request().method() === "POST" && /\/deliverables$/.test(resp.url())
  );
  await form.getByRole("button", { name: "Oluştur" }).click();
  const createResponse = await createResponsePromise;
  expect(createResponse.status()).toBe(201);
  const newDeliverableId = (await createResponse.json()).id as string;
  expect(newDeliverableId).toBeTruthy();

  // Modal closes on success, no page reload needed — the new deliverable is
  // immediately selected and visible.
  await expect(page.getByRole("heading", { name: "Yeni Teslim Ekle" })).toHaveCount(0);
  await expect(page.getByText("LinkedIn Tasarımı").first()).toBeVisible();

  // (3) Both deliverables are listed side by side; the older one was not
  // demoted to a read-only prior version by the new sibling.
  await expect(page.locator("button", { hasText: "Instagram Post" }).first()).toBeVisible();
  await expect(page.locator("button", { hasText: "LinkedIn Tasarımı" }).first()).toBeVisible();

  // Upload a real image asset to the new (still-draft) deliverable, then
  // submit it — normal continuation of the creation flow, exercised via the
  // real UI, no page reload at any point.
  await page.locator('input[type="file"]').first().setInputFiles({
    name: "e2e-linkedin.png",
    mimeType: "image/png",
    buffer: TINY_PNG,
  });
  await expect(page.getByRole("button", { name: "Onaya Gönder" })).toBeVisible({ timeout: 10_000 });
  await page.getByRole("button", { name: "Onaya Gönder" }).click();
  await expect(page.getByRole("button", { name: "Onaya Gönder" })).toHaveCount(0, { timeout: 10_000 });

  // (4) Brand portal: both the pre-existing and the newly created
  // deliverable stay independently annotatable.
  await loginBrand(page);
  await gotoAuthenticated(page, `/brand/briefs/${BRIEF_ID}`, /\/brand\/login$/);
  await expect(page.getByTestId("deliverable-workspace")).toBeVisible({ timeout: 15_000 });

  for (const id of [EXISTING_DELIVERABLE_ID, newDeliverableId]) {
    await page.getByTestId(`version-strip-thumb-${id}`).click();
    await expect(page.getByRole("button", { name: "Revizyon Noktası Belirle" })).toBeVisible({
      timeout: 10_000,
    });
  }

  // (7) No console errors anywhere across the whole flow.
  expect(consoleErrors, `Unexpected console errors:\n${consoleErrors.join("\n")}`).toEqual([]);
});

test("viewer cannot create a deliverable: no button shown for the unauthorized role", async ({
  page,
}) => {
  // (5) Frontend hides the action for an unauthorized role. The access
  // token lives only in React state (never localStorage — see
  // context/auth-context.tsx), so a direct same-session API call isn't
  // straightforward from here; the corresponding backend-side proof (the
  // button's absence isn't the only thing stopping a VIEWER — POST
  // /briefs/{id}/deliverables itself 403s for that role) is covered by
  // test_viewer_cannot_create_deliverable in
  // apps/backend/app/tests/test_deliverables.py.
  await loginAgency(page, VIEWER_EMAIL);
  await gotoAuthenticated(
    page,
    `/dashboard/briefs/${BRIEF_ID}?tab=uretim`,
    /\/auth\/(login|agency-login)$/
  );
  await expect(page.getByText("Instagram Post").first()).toBeVisible({ timeout: 15_000 });
  await expect(page.getByRole("button", { name: "Yeni Teslim Ekle" })).toHaveCount(0);
});

test("brand portal never exposes a deliverable-creation action", async ({ page }) => {
  // (6)
  await loginBrand(page);
  await gotoAuthenticated(page, `/brand/briefs/${BRIEF_ID}`, /\/brand\/login$/);
  await expect(page.getByTestId("deliverable-workspace")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByRole("button", { name: "Yeni Teslim Ekle" })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Yeni Teslim Ekle" })).toHaveCount(0);
});
