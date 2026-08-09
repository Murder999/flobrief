import { test, expect, type Page, type APIRequestContext } from "@playwright/test";
import { execFileSync } from "node:child_process";
import path from "node:path";

/**
 * @mention feature coverage: agency-side comment + annotation composers,
 * brand-side annotation composer (brand comment threads have no mention
 * support — see BriefCommunicationPanel.tsx, a plain textarea with no
 * MentionTextArea/RichTextEditor wiring, verified by reading the source),
 * candidate-list isolation (viewer exclusion, cross-tenant exclusion,
 * brand assignee-only visibility), notification deep-linking, and two
 * backend regression guards (21-mention cap -> 422, duplicate mention id in
 * one submission -> exactly one notification).
 *
 * Self-seeds both fixtures fresh in beforeAll (same execFileSync + parsed-env
 * pattern as onboarding-flow.spec.ts / preview-center-flow.spec.ts) instead
 * of depending on an external seed step exporting AGY_ / BRD_ prefixed env vars —
 * there was no runner that ever produced those, and IDs are not stable
 * across re-seeds, so per-file self-seeding is the only deterministic
 * option. Both e2e_seed_mention_onboarding_*.py scripts dismiss the owner /
 * designer / brand-owner's onboarding via the real dismiss endpoint during
 * seeding, so this spec never races OnboardingWizard's welcome-modal overlay
 * (onboarding-flow.spec.ts is the one spec responsible for testing that
 * overlay's own behavior).
 *
 * playwright.config.ts runs with fullyParallel:false / workers:1, so this
 * file's beforeAll/afterAll never overlaps with onboarding-flow.spec.ts's
 * own beforeAll/afterAll against the same fixture emails.
 */

const PASSWORD = "E2eTest1234!";
const BACKEND_DIR = path.resolve(__dirname, "../../backend");
const PYTHON = process.env.E2E_PYTHON ?? path.join(BACKEND_DIR, ".venv", "Scripts", "python.exe");

function runSeedScript(script: string, args: string[]): Record<string, string> {
  const output = execFileSync(PYTHON, [`scripts/${script}`, ...args], {
    cwd: BACKEND_DIR,
    encoding: "utf-8",
    maxBuffer: 1024 * 1024 * 20,
    // Windows' console codepage (e.g. cp1254) doesn't match the UTF-8 this
    // process decodes with, so non-ASCII fixture data (the Turkish designer
    // name) comes back mojibake unless Python is forced to emit UTF-8
    // regardless of system locale.
    env: { ...process.env, PYTHONIOENCODING: "utf-8" },
  });
  const env: Record<string, string> = {};
  for (const line of output.split(/\r?\n/)) {
    const match = line.match(/^([A-Z0-9_]+)=(.*)$/);
    if (match) env[match[1]] = match[2];
  }
  return env;
}

// ── Agency fixture (e2e_seed_mention_onboarding_agency.py) ──────────────────
let AGY_AGENCY_ID: string;
let AGY_BRIEF_ID: string;
let AGY_OWNER_EMAIL: string;
let AGY_DESIGNER_EMAIL: string;
let AGY_DESIGNER_FULL_NAME: string;
let AGY_VIEWER_EMAIL: string;
let AGY_OTHER_TENANT_OWNER_EMAIL: string;
const AGY_DELIVERABLE_1_TITLE = "E2E MO Deliverable One";

// ── Brand fixture (e2e_seed_mention_onboarding_brand.py) ────────────────────
let BRD_AGENCY_ID: string;
let BRD_BRIEF_ID: string;
let BRD_BRAND_OWNER_EMAIL: string;
let BRD_ASSIGNED_DESIGNER_EMAIL: string;
let BRD_UNASSIGNED_DESIGNER_EMAIL: string;
let BRD_SIBLING_BRAND_OWNER_EMAIL: string;
let BRD_OTHER_TENANT_BRAND_USER_EMAIL: string;

test.beforeAll(() => {
  const agy = runSeedScript("e2e_seed_mention_onboarding_agency.py", ["seed"]);
  AGY_AGENCY_ID = agy.E2E_AGENCY_ID;
  AGY_BRIEF_ID = agy.E2E_BRIEF_ID;
  AGY_OWNER_EMAIL = agy.E2E_OWNER_EMAIL;
  AGY_DESIGNER_EMAIL = agy.E2E_DESIGNER_EMAIL;
  AGY_DESIGNER_FULL_NAME = agy.E2E_DESIGNER_FULL_NAME;
  AGY_VIEWER_EMAIL = agy.E2E_VIEWER_EMAIL;
  AGY_OTHER_TENANT_OWNER_EMAIL = agy.E2E_OTHER_TENANT_OWNER_EMAIL;
  if (!AGY_AGENCY_ID || !AGY_BRIEF_ID || !AGY_OWNER_EMAIL) {
    throw new Error("agency mention fixture seed did not return the expected env vars");
  }

  const brd = runSeedScript("e2e_seed_mention_onboarding_brand.py", ["seed"]);
  BRD_AGENCY_ID = brd.E2E_AGENCY_ID;
  BRD_BRIEF_ID = brd.E2E_BRIEF_ID;
  BRD_BRAND_OWNER_EMAIL = brd.E2E_BRAND_OWNER_EMAIL;
  BRD_ASSIGNED_DESIGNER_EMAIL = brd.E2E_ASSIGNED_DESIGNER_EMAIL;
  BRD_UNASSIGNED_DESIGNER_EMAIL = brd.E2E_UNASSIGNED_DESIGNER_EMAIL;
  BRD_SIBLING_BRAND_OWNER_EMAIL = brd.E2E_SIBLING_BRAND_OWNER_EMAIL;
  BRD_OTHER_TENANT_BRAND_USER_EMAIL = brd.E2E_OTHER_TENANT_BRAND_USER_EMAIL;
  if (!BRD_AGENCY_ID || !BRD_BRIEF_ID || !BRD_BRAND_OWNER_EMAIL) {
    throw new Error("brand mention fixture seed did not return the expected env vars");
  }
});

test.afterAll(() => {
  runSeedScript("e2e_seed_mention_onboarding_agency.py", ["cleanup"]);
  runSeedScript("e2e_seed_mention_onboarding_brand.py", ["cleanup"]);
});

const COMMENT_COMPOSER_SELECTOR =
  'div[contenteditable="true"][data-placeholder="Yeni yorum, revize notu veya not ekle…"]';

// Console-noise categories already established as harmless by the existing
// mention-annotation-smoke.spec.ts reference — not broadened here.
function relevantConsoleErrors(errors: string[]): string[] {
  return errors.filter(
    (e) =>
      !e.includes("Failed to fetch RSC payload") &&
      !e.includes("401 (Unauthorized)") &&
      !e.includes("404 (Not Found)")
  );
}

function trackConsoleErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") errors.push(msg.text());
  });
  return errors;
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

/** Direct-API login (no browser) for the backend regression checks. */
async function apiLogin(request: APIRequestContext, email: string): Promise<string> {
  const resp = await request.post("/api/v1/auth/login", {
    data: { email, password: PASSWORD },
  });
  expect(resp.ok(), `login failed for ${email}: ${resp.status()} ${await resp.text()}`).toBeTruthy();
  const body = await resp.json();
  return body.access_token as string;
}

async function openAnnotationComposer(page: Page): Promise<void> {
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
  // A unique-ish offset per test run to dodge markers left by previous runs.
  await canvas.click({ position: { x: box.width / 3, y: box.height / 3 } });
}

// ── Agency-side: comment thread composer ─────────────────────────────────────

test.describe("Agency comment @mention", () => {
  test("popover excludes viewer + cross-tenant users, includes the Turkish-named designer, keyboard selection inserts a chip, saved comment renders the chip, designer is notified with a working deep link", async ({ page }) => {
    const consoleErrors = trackConsoleErrors(page);

    await loginAgency(page, AGY_OWNER_EMAIL);
    await page.goto(`/dashboard/briefs/${AGY_BRIEF_ID}`);

    const composer = page.locator(COMMENT_COMPOSER_SELECTOR);
    await expect(composer).toBeVisible({ timeout: 15_000 });
    await composer.click();
    await page.keyboard.type("Merhaba @Ayşe", { delay: 30 });

    const option = page.getByRole("option", { name: new RegExp(AGY_DESIGNER_FULL_NAME.split(" ")[0]) });
    await expect(option).toBeVisible({ timeout: 5_000 });

    // Negative candidates: the popover's own listbox must never contain a
    // viewer or a user from the other-tenant fixture agency, regardless of
    // what's typed — assert on the full listbox text, not just "the option
    // I expect is missing", to also catch an over-broad candidate query.
    const listbox = page.getByRole("listbox", { name: "Bahsedilecek kişiler" });
    await expect(listbox).toBeVisible();
    await expect(listbox).not.toContainText("E2E Agency Viewer");
    await expect(listbox).not.toContainText("E2E Other Tenant Owner");

    // Keyboard selection (Enter), not a mouse click.
    await page.keyboard.press("Enter");
    await expect(composer).toContainText(`@${AGY_DESIGNER_FULL_NAME}`);

    await page.keyboard.type(" lütfen bakar mısın?", { delay: 20 });
    await page.getByRole("button", { name: "Gönder" }).click();

    await expect(
      page.locator(".mention-chip", { hasText: AGY_DESIGNER_FULL_NAME }).first()
    ).toBeVisible({ timeout: 10_000 });

    const relevant = relevantConsoleErrors(consoleErrors);
    expect(relevant, `console errors: ${relevant.join("\n")}`).toEqual([]);
  });

  test("mentioned designer's notification bell click deep-links to the brief and switches to the Yorumlar tab", async ({ page }) => {
    await loginAgency(page, AGY_DESIGNER_EMAIL);
    // The previous test already created a fresh mention notification for
    // this user against this brief — open the bell and click the newest one.
    await page.goto("/dashboard");
    const bell = page.getByRole("button", { name: "Bildirimler" });
    await bell.click();
    const panel = page.getByRole("dialog", { name: "Bildirimler" });
    await expect(panel).toBeVisible({ timeout: 10_000 });

    const mentionItem = panel.getByText("Bir yorumda etiketlendiniz").first();
    await expect(mentionItem).toBeVisible({ timeout: 10_000 });
    await mentionItem.click();

    await page.waitForURL((url) => url.pathname === `/dashboard/briefs/${AGY_BRIEF_ID}`, { timeout: 15_000 });
    expect(new URL(page.url()).searchParams.get("panel")).toBe("comments");
    // Real, verified behavior, two gaps flagged (neither fixed — both are
    // UX-completeness gaps, not functional bugs, and out of this feature's
    // scope): (1) the backend computes a `comment` query param (see
    // notification_routes.py) but the brief-detail page never reads it
    // (only tab/panel/deliverable/annotation are consumed), so the click
    // lands on the right *section*, not the specific thread/comment; (2)
    // the "yorumlar" activeTab value this deep link switches to has no
    // corresponding button in the visible tab bar (`tabs` only has
    // genel/brief/referanslar/uretim) — it is reachable only via this deep
    // link, landing on a dedicated "İç Yorumlar" panel with no tab
    // highlighted in the bar above it.
    await expect(page.getByRole("heading", { name: "İç Yorumlar" })).toBeVisible({ timeout: 10_000 });
  });
});

// ── Agency-side: annotation composer + reply ──────────────────────────────────

test.describe("Agency annotation @mention", () => {
  test("new annotation composer mentions the designer, reply composer mentions again, chips render, designer gets an annotation-deep-linked notification", async ({ page }) => {
    const consoleErrors = trackConsoleErrors(page);
    await loginAgency(page, AGY_OWNER_EMAIL);
    await page.goto(`/dashboard/briefs/${AGY_BRIEF_ID}`);
    await page.getByRole("button", { name: "Teslimler" }).first().click();
    await page.getByRole("button", { name: new RegExp(AGY_DELIVERABLE_1_TITLE) }).first().click();

    await openAnnotationComposer(page);
    const composer = page.getByPlaceholder("Bu noktadaki revizyon talebini yazın…");
    await expect(composer).toBeVisible();
    await composer.pressSequentially("Merhaba @Ayşe");
    const option = page.getByRole("option", { name: new RegExp(AGY_DESIGNER_FULL_NAME.split(" ")[0]) });
    await expect(option).toBeVisible({ timeout: 5_000 });
    await composer.press("Enter");
    await expect(composer).toHaveValue(`Merhaba @${AGY_DESIGNER_FULL_NAME} `);
    await composer.pressSequentially("bakar mısın?");
    await page.getByRole("button", { name: "Kaydet" }).click();

    const chip = page.locator(".mention-chip", { hasText: AGY_DESIGNER_FULL_NAME }).first();
    await expect(chip).toBeVisible({ timeout: 10_000 });

    // Reply composer on the just-created annotation.
    const replyBox = page.getByPlaceholder("Yanıtla… (@ ile etiketle)").first();
    await expect(replyBox).toBeVisible({ timeout: 10_000 });
    await replyBox.pressSequentially("@Ayşe");
    const replyOption = page.getByRole("option", { name: new RegExp(AGY_DESIGNER_FULL_NAME.split(" ")[0]) });
    await expect(replyOption).toBeVisible({ timeout: 5_000 });
    await replyBox.press("Enter");
    await replyBox.pressSequentially(" bakar mısın");
    await page.getByRole("button", { name: "Yanıtı gönder" }).first().click();

    await expect(page.locator(".mention-chip", { hasText: AGY_DESIGNER_FULL_NAME })).toHaveCount(2, {
      timeout: 10_000,
    });

    const relevant = relevantConsoleErrors(consoleErrors);
    expect(relevant, `console errors: ${relevant.join("\n")}`).toEqual([]);
  });

  test("mentioned-in-annotation notification deep-links to the deliverable and pulses the exact annotation", async ({ page }) => {
    await loginAgency(page, AGY_DESIGNER_EMAIL);
    await page.goto("/dashboard");
    await page.getByRole("button", { name: "Bildirimler" }).click();
    const panel = page.getByRole("dialog", { name: "Bildirimler" });
    await expect(panel).toBeVisible({ timeout: 10_000 });
    const mentionItem = panel.getByText("Bir revizyon notunda etiketlendiniz").first();
    await expect(mentionItem).toBeVisible({ timeout: 10_000 });
    await mentionItem.click();

    await page.waitForURL((url) => url.pathname === `/dashboard/briefs/${AGY_BRIEF_ID}`, { timeout: 15_000 });
    const url = new URL(page.url());
    expect(url.searchParams.get("tab")).toBe("uretim");
    expect(url.searchParams.get("annotation")).toBeTruthy();
    // The deep link opens the exact annotation's detail popover (not just
    // the deliverable) — its reply, containing the mention chip created in
    // the previous test, must be visible without any further navigation.
    await expect(page.locator(".mention-chip", { hasText: AGY_DESIGNER_FULL_NAME }).first()).toBeVisible({
      timeout: 10_000,
    });
  });
});

// ── Brand-side: candidate isolation via the annotation composer ─────────────

test.describe("Brand @mention candidate isolation", () => {
  test("assigned agency designer is visible with 'Ajans Ekibi' context, unassigned designer/sibling-brand/cross-tenant users are never visible, own brand member is visible", async ({ page }) => {
    await loginBrand(page, BRD_BRAND_OWNER_EMAIL);
    await page.goto(`/brand/briefs/${BRD_BRIEF_ID}`);

    await openAnnotationComposer(page);
    const composer = page.getByPlaceholder("Bu noktadaki revizyon talebini yazın…");
    await expect(composer).toBeVisible();
    await composer.pressSequentially("@");

    const listbox = page.getByRole("listbox", { name: "Bahsedilecek kişiler" });
    await expect(listbox).toBeVisible({ timeout: 5_000 });

    await expect(listbox.getByText("E2E Assigned Designer")).toBeVisible({ timeout: 5_000 });
    await expect(listbox.getByText("E2E Assigned Designer").locator("..")).toContainText("Ajans Ekibi");

    await expect(listbox).not.toContainText("E2E Unassigned Designer");
    await expect(listbox).not.toContainText("Sibling Brand Owner");
    await expect(listbox).not.toContainText("Other Tenant Brand User");

    // A brand's own second member (brand_viewer) must be a valid candidate —
    // brand candidates are not role-filtered, unlike agency.
    await expect(listbox).toContainText("E2E Brand Viewer");
  });
});

// ── Backend regression guards (direct API, no realistic 21-person UI flow) ──

test.describe("Mention backend guards", () => {
  test("submitting 21 distinct mention ids is rejected with a 422, not silently truncated", async ({ request }) => {
    const token = await apiLogin(request, AGY_OWNER_EMAIL);
    const ids = Array.from({ length: 21 }, () => crypto.randomUUID());
    const resp = await request.post(`/api/v1/briefs/${AGY_BRIEF_ID}/threads`, {
      headers: { Authorization: `Bearer ${token}`, "X-Agency-ID": AGY_AGENCY_ID as string },
      data: {
        thread_type: "brief",
        initial_comment: "Mass mention regression check",
        visibility: "internal",
        mentioned_user_ids: ids,
      },
    });
    expect(resp.status()).toBe(422);
  });

  test("a duplicate mention id in one submission produces exactly one notification", async ({ request }) => {
    const ownerToken = await apiLogin(request, AGY_OWNER_EMAIL);
    const designerToken = await apiLogin(request, AGY_DESIGNER_EMAIL);

    const meResp = await request.get("/api/v1/auth/me", {
      headers: { Authorization: `Bearer ${designerToken}`, "X-Agency-ID": AGY_AGENCY_ID as string },
    });
    expect(meResp.ok()).toBeTruthy();
    const designerId = (await meResp.json()).id as string;

    const before = await request.get(`/api/v1/notifications?limit=100`, {
      headers: { Authorization: `Bearer ${designerToken}`, "X-Agency-ID": AGY_AGENCY_ID as string },
    });
    const beforeCount = (await before.json()).items.filter(
      (n: { event_type: string }) => n.event_type === "mention.in_comment"
    ).length;

    const createResp = await request.post(`/api/v1/briefs/${AGY_BRIEF_ID}/threads`, {
      headers: { Authorization: `Bearer ${ownerToken}`, "X-Agency-ID": AGY_AGENCY_ID as string },
      data: {
        thread_type: "brief",
        initial_comment: `Duplicate mention regression: @${AGY_DESIGNER_FULL_NAME} @${AGY_DESIGNER_FULL_NAME}`,
        visibility: "internal",
        mentioned_user_ids: [designerId, designerId],
      },
    });
    expect(createResp.ok(), await createResp.text()).toBeTruthy();

    const after = await request.get(`/api/v1/notifications?limit=100`, {
      headers: { Authorization: `Bearer ${designerToken}`, "X-Agency-ID": AGY_AGENCY_ID as string },
    });
    const afterCount = (await after.json()).items.filter(
      (n: { event_type: string }) => n.event_type === "mention.in_comment"
    ).length;

    expect(afterCount - beforeCount).toBe(1);
  });
});

// ── Viewport spot-checks ──────────────────────────────────────────────────────

for (const vp of [
  { name: "tablet 1024x768", width: 1024, height: 768 },
  { name: "mobile 390x844", width: 390, height: 844 },
]) {
  test.describe(`Mention popover @ ${vp.name}`, () => {
    test.use({ viewport: { width: vp.width, height: vp.height } });

    test("popover stays within the viewport, no horizontal page overflow, and selection still works with the long Turkish name", async ({ page }) => {
      await loginAgency(page, AGY_OWNER_EMAIL);
      await page.goto(`/dashboard/briefs/${AGY_BRIEF_ID}`);

      const overflow = await page.evaluate(() => document.body.scrollWidth - document.body.clientWidth);
      expect(overflow).toBeLessThanOrEqual(1);

      const composer = page.locator(COMMENT_COMPOSER_SELECTOR);
      await expect(composer).toBeVisible({ timeout: 15_000 });
      await composer.click();
      await page.keyboard.type("@Ayşe", { delay: 30 });

      const listbox = page.getByRole("listbox", { name: "Bahsedilecek kişiler" });
      await expect(listbox).toBeVisible({ timeout: 5_000 });
      const box = await listbox.boundingBox();
      expect(box).not.toBeNull();
      if (box) {
        expect(box.x).toBeGreaterThanOrEqual(0);
        expect(box.x + box.width).toBeLessThanOrEqual(vp.width + 1);
      }

      const option = page.getByRole("option", { name: new RegExp(AGY_DESIGNER_FULL_NAME.split(" ")[0]) });
      await expect(option).toBeVisible({ timeout: 5_000 });
      await option.click();
      await expect(composer).toContainText(AGY_DESIGNER_FULL_NAME);

      const overflowAfter = await page.evaluate(() => document.body.scrollWidth - document.body.clientWidth);
      expect(overflowAfter).toBeLessThanOrEqual(1);
    });
  });
}
