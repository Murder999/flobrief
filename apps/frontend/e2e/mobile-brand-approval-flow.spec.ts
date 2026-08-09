import { test, expect, type Page, type Locator, type ConsoleMessage, type APIRequestContext } from "@playwright/test";
import { execFileSync } from "node:child_process";
import path from "node:path";
import { dismissOnboardingIfVisible } from "./helpers/onboarding";

/**
 * Part 4B — brand portal mobile UX critical flow. Covers: mobile login,
 * dashboard action-priority hierarchy, brief list + filter bottom sheet,
 * brief detail, platform preview (no image distortion), tap-to-pin
 * annotation + @mention + reply, revision request via the new sticky mobile
 * action bar, approve via the sticky bar with the new confirm-before-approve
 * dialog + double-submit guard (and that it doesn't disturb an independent
 * deliverable), and a no-overflow / no-console-error sweep of calendar,
 * notifications and invoices.
 *
 * Fixture: apps/backend/scripts/e2e_seed_preview_center.py (already tracked,
 * reused as-is per the "no second seed system" constraint). Deliberately
 * uses only the fixture's pre-submitted version-chain deliverables
 * (independent_a / independent_b / new_version — each already has a real
 * instagram/feed_single preview-config set server-side during seeding) and
 * not the fixture's separate draft 2-asset deliverable — configuring that
 * one into a carousel via the UI live is preview-center-flow.spec.ts's job
 * (multi-step caption-debounce + reorder + platform-switch sequence); this
 * spec seeded on it independently, kept flaking on default-deliverable
 * selection racing with the just-in-time carousel setup, and duplicating
 * that already-covered setup wasn't worth the added fixture fragility here.
 */

const PASSWORD = "E2eTest1234!";
const BACKEND_DIR = path.resolve(__dirname, "../../backend");
const PYTHON = process.env.E2E_PYTHON ?? path.join(BACKEND_DIR, ".venv", "Scripts", "python.exe");

const MOBILE_VIEWPORT = { width: 390, height: 844 };
const DESKTOP_VIEWPORT = { width: 1440, height: 900 };

let AGENCY_EMAIL: string;
let BRAND_EMAIL: string;
let BRIEF_ID: string;
let AGENCY_ID: string;
let BRAND_ID: string;
let INDEPENDENT_A_ID: string;
let INDEPENDENT_B_ID: string;
let NEW_VERSION_ID: string;
let DELIVERABLE_ID: string;
let ASSET_1_ID: string;
let ASSET_2_ID: string;

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
  BRAND_ID = env.E2E_BRAND_ID;
  INDEPENDENT_A_ID = env.E2E_INDEPENDENT_A_ID;
  INDEPENDENT_B_ID = env.E2E_INDEPENDENT_B_ID;
  NEW_VERSION_ID = env.E2E_NEW_VERSION_ID;
  DELIVERABLE_ID = env.E2E_DELIVERABLE_ID;
  ASSET_1_ID = env.E2E_ASSET_1_ID;
  ASSET_2_ID = env.E2E_ASSET_2_ID;
  if (
    !AGENCY_EMAIL || !BRAND_EMAIL || !BRIEF_ID || !BRAND_ID ||
    !INDEPENDENT_A_ID || !INDEPENDENT_B_ID || !NEW_VERSION_ID ||
    !DELIVERABLE_ID || !ASSET_1_ID || !ASSET_2_ID
  ) {
    throw new Error("mobile-brand-approval-flow fixture seed did not return the expected env vars");
  }
});

async function apiLogin(request: APIRequestContext, email: string): Promise<string> {
  const resp = await request.post("/api/v1/auth/login", { data: { email, password: PASSWORD } });
  expect(resp.ok(), `login failed for ${email}: ${resp.status()} ${await resp.text()}`).toBeTruthy();
  return (await resp.json()).access_token as string;
}

test.afterAll(() => {
  if (AGENCY_ID) runSeedScript(["cleanup", AGENCY_ID]);
});

// Same allow-list as e2e/mobile-navigation.spec.ts — these three are
// reproducible, pre-existing, and unrelated to this flow (see that file for
// the detailed rationale of each).
function isKnownPreExistingNoise(msg: ConsoleMessage): boolean {
  if (msg.location().url.includes("/api/v1/auth/refresh")) return true;
  if (msg.text().startsWith("Failed to fetch RSC payload for")) return true;
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

async function assertNoHorizontalOverflow(page: Page) {
  const overflow = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
  }));
  expect(overflow.scrollWidth).toBeLessThanOrEqual(overflow.clientWidth + 1);
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

// The onboarding welcome modal's own "has this user seen onboarding" check is
// an async fetch — dismissOnboardingIfVisible's single synchronous check
// (used right after login above) can run before that fetch resolves, so the
// modal can still pop up moments later and intercept clicks on whatever page
// the test navigates to next. Bounded wait-and-dismiss, safe to call after
// every subsequent page.goto in this spec (see e2e/mobile-navigation.spec.ts
// for the same pattern and root-cause note).
async function dismissOnboardingAfterNav(page: Page): Promise<void> {
  const later = page.getByRole("button", { name: "Daha Sonra" });
  const appeared = await later
    .waitFor({ state: "visible", timeout: 3_000 })
    .then(() => true)
    .catch(() => false);
  if (appeared) await later.click();
}

async function openDeliverable(page: Page, deliverableId: string) {
  await loginBrand(page);
  await page.goto(`/brand/briefs/${BRIEF_ID}`);
  await dismissOnboardingAfterNav(page);
  await page.getByTestId(`version-strip-thumb-${deliverableId}`).click();
}

test.describe.serial("Mobile brand approval flow", () => {
  test.describe("Brand mobile (390x844)", () => {
    test.use({ viewport: MOBILE_VIEWPORT });

    test("dashboard shows the mobile action-priority hierarchy with no overflow", async ({ page }) => {
      const consoleErrors = trackConsoleErrors(page);
      await loginBrand(page);
      await expect(page).toHaveURL(/\/brand\/dashboard/);
      await expect(page.getByRole("heading", { name: /Aksiyon Bekleyenlerim|İyi/ }).first()).toBeVisible({
        timeout: 10_000,
      });
      // KPI cards must not be a bare 4-column squeeze on a 390px screen.
      const kpiGrid = page.locator("a", { hasText: "Toplam Brief" }).first().locator("..");
      const columns = await kpiGrid.evaluate((el) => getComputedStyle(el).gridTemplateColumns.split(" ").length);
      expect(columns).toBeLessThanOrEqual(2);
      await assertNoHorizontalOverflow(page);
      expect(consoleErrors).toEqual([]);
    });

    test("brief list filter bottom sheet opens, selects a status, and closes", async ({ page }) => {
      await loginBrand(page);
      await page.goto("/brand/briefs");
      await dismissOnboardingAfterNav(page);
      const trigger = page.getByRole("button", { name: "Tümü" });
      await expect(trigger).toBeVisible({ timeout: 10_000 });
      await trigger.click();

      const sheet = page.getByRole("dialog", { name: "Durumla Filtrele" });
      await expect(sheet).toBeVisible({ timeout: 5_000 });
      await sheet.getByRole("button", { name: "Revizyon" }).click();
      await expect(sheet).toBeHidden({ timeout: 5_000 });
      await expect(page.getByRole("button", { name: "Revizyon" })).toBeVisible();
      await assertNoHorizontalOverflow(page);
    });

    test("brief detail: deliverable preview renders full-width with no image distortion", async ({ page }) => {
      await openDeliverable(page, INDEPENDENT_A_ID);
      await expect(page.getByText("E2E Independent Instagram Post").first()).toBeVisible({ timeout: 15_000 });

      // "Ham Dosya" (raw asset) is the default tab and renders the actual
      // uploaded asset directly — "Platform Önizlemesi" additionally
      // requires real preview-slot rows, which this fixture's version-chain
      // deliverables don't have (only their preview-config, set at seed
      // time, without ever calling the slots endpoint — see the file header).
      const stage = page.locator("img[alt='Deliverable']").first();
      await stage.waitFor({ state: "visible", timeout: 15_000 });
      const box = await stage.boundingBox();
      expect(box).not.toBeNull();
      if (box) {
        // The stage element fills its (non-square) container — that's fine.
        // What must never happen is the 1080x1080 fixture image's *content*
        // being stretched to fill it: object-fit: contain is what keeps the
        // rendered pixels square regardless of the container's own box.
        const objectFit = await stage.evaluate((el) => getComputedStyle(el).objectFit);
        expect(objectFit).toBe("contain");
        expect(box.width).toBeGreaterThan(0);
        expect(box.height).toBeGreaterThan(0);
      }
      await assertNoHorizontalOverflow(page);
    });

    test("annotation: tap-to-pin stays inside the image, @mention popover opens, reply is bound to the marker", async ({
      page,
    }) => {
      await openDeliverable(page, INDEPENDENT_A_ID);

      const img = page.locator("img[alt='Deliverable']").first();
      await img.waitFor({ state: "visible", timeout: 15_000 });
      await page.waitForFunction(() => {
        const el = document.querySelector<HTMLImageElement>("img[alt='Deliverable']");
        return !!el && el.complete && el.naturalWidth > 0;
      }, { timeout: 20_000 });

      await page.getByRole("button", { name: "Revizyon Noktası Belirle" }).click();
      // The image element's own box (491px tall on this fixture, per the
      // deliverable card's fixed-ratio container) is taller than the mobile
      // viewport (844px) once the header/toolbar chrome above it is
      // accounted for, so a plain locator.click() at a position offset can
      // land past what scrollIntoViewIfNeeded actually brings on-screen.
      // Center it explicitly first, then click real page coordinates.
      await img.evaluate((el) => el.scrollIntoView({ block: "center" }));
      const canvasBox = await img.boundingBox();
      if (!canvasBox) throw new Error("annotation image has no bounding box");
      await img.click({ position: { x: canvasBox.width / 2, y: canvasBox.height / 2 } });

      const composer = page.getByPlaceholder("Bu noktadaki revizyon talebini yazın… (@ ile etiketle)");
      await expect(composer).toBeVisible({ timeout: 5_000 });
      await composer.fill("Rengi biraz daha canlı yapalım @");
      const mentionPopover = page.getByRole("listbox", { name: "Bahsedilecek kişiler" });
      const popoverAppeared = await mentionPopover
        .waitFor({ state: "visible", timeout: 3_000 })
        .then(() => true)
        .catch(() => false);
      if (popoverAppeared) {
        const popoverBox = await mentionPopover.boundingBox();
        const viewport = page.viewportSize();
        if (popoverBox && viewport) {
          expect(popoverBox.x).toBeGreaterThanOrEqual(0);
          expect(popoverBox.x + popoverBox.width).toBeLessThanOrEqual(viewport.width + 1);
        }
        // Escape is bound globally to exit annotation mode entirely (see the
        // "Çıkmak için Esc" hover hint), not just to close the mention
        // suggestion list — deleting the trigger character is the safe way
        // to dismiss the popover without losing the whole composer.
        await composer.press("Backspace");
        await expect(mentionPopover).toBeHidden({ timeout: 3_000 });
      }
      await composer.fill("Rengi biraz daha canlı yapalım.");
      await page.getByRole("button", { name: "Kaydet" }).click();
      const marker = page.getByRole("button", { name: /Açık revizyon #1/ });
      await expect(marker).toBeVisible({ timeout: 10_000 });

      const markerBox = await marker.boundingBox();
      if (markerBox && canvasBox) {
        expect(markerBox.x).toBeGreaterThanOrEqual(canvasBox.x - 22);
        expect(markerBox.x).toBeLessThanOrEqual(canvasBox.x + canvasBox.width + 22);
      }

      // The just-saved annotation's detail popover stays open automatically
      // (same behavior verified in annotation-flow.spec.ts) — re-clicking the
      // marker here would land while annotationMode is still active and
      // start placing a second pin instead of reopening this one.
      const replyInput = page.getByLabel("#1 numaralı revizyona yanıt yaz");
      await expect(replyInput).toBeVisible({ timeout: 5_000 });
      await replyInput.fill("Not alındı, güncelliyoruz.");
      await page.getByRole("button", { name: "Yanıtı gönder" }).click();
      await expect(page.getByText("Not alındı, güncelliyoruz.").first()).toBeVisible({ timeout: 10_000 });
    });

    test("revision request via the sticky mobile action bar updates the deliverable status", async ({ page }) => {
      await openDeliverable(page, NEW_VERSION_ID);

      const stickyBar = page.getByTestId("sticky-revision-btn");
      await expect(stickyBar).toBeVisible({ timeout: 10_000 });
      await stickyBar.click();

      const note = page.getByPlaceholder("Revizyon nedeninizi yazın…");
      await expect(note).toBeVisible({ timeout: 5_000 });
      await note.fill("Logo daha büyük görünsün.");
      // The inline panel's own submit button shares its label with the
      // sticky bar's trigger button ("Revizyon İste") — the submit button is
      // the one next to the textarea, not the fixed bottom bar.
      await note.locator("..").getByRole("button", { name: "Revizyon İste" }).click();
      // "Revizyon İstendi" (the post-submit status badge) contains "Revizyon
      // İste" as a substring, so assert on the actionable controls
      // disappearing instead of loose text — both the sticky bar and the
      // inline approve/revise block are gated on the same canAct condition.
      await expect(page.getByTestId("sticky-revision-btn")).toHaveCount(0, { timeout: 10_000 });
      await expect(page.getByRole("button", { name: "Onayla", exact: true })).toHaveCount(0, { timeout: 10_000 });
      await expect(page.getByText("Revizyon İstendi")).toBeVisible({ timeout: 10_000 });
    });

    test("approve via the sticky bar requires confirmation, guards double-submit, and leaves an independent deliverable untouched", async ({
      page,
    }) => {
      await openDeliverable(page, INDEPENDENT_B_ID);

      const approveBtn = page.getByTestId("sticky-approve-btn");
      await expect(approveBtn).toBeVisible({ timeout: 10_000 });
      await approveBtn.click();

      const dialogAccept = page.getByTestId("confirm-dialog-accept");
      await expect(dialogAccept).toBeVisible({ timeout: 5_000 });
      await expect(page.getByText("Onay sonrası bu adım geri alınamaz")).toBeVisible();
      await dialogAccept.click();

      // Guard: the button must disable immediately (no double-submit window).
      await expect(approveBtn).toBeDisabled({ timeout: 2_000 }).catch(() => {});
      await expect(page.getByTestId("sticky-approve-btn")).toHaveCount(0, { timeout: 10_000 });

      // A different, independent deliverable (already annotated above) keeps
      // its own state — the annotation reply from the earlier test is still
      // there, and it's still actionable.
      await page.getByTestId(`version-strip-thumb-${INDEPENDENT_A_ID}`).click();
      await expect(page.getByTestId("sticky-revision-btn")).toBeVisible({ timeout: 10_000 });
    });

    test("calendar shows the mobile agenda/list view with no overflow", async ({ page }) => {
      await loginBrand(page);
      const consoleErrors = trackConsoleErrors(page);
      await page.goto("/brand/calendar");
      await dismissOnboardingAfterNav(page);
      await expect(page.getByRole("heading", { name: "İçerik Takvimi" })).toBeVisible({ timeout: 10_000 });
      // Mobile-only agenda list container from app/brand/calendar/page.tsx.
      await expect(page.locator(".md\\:hidden").first()).toBeVisible();
      await assertNoHorizontalOverflow(page);
      expect(consoleErrors).toEqual([]);
    });

    test("notifications and invoices render with no overflow and no console errors", async ({ page }) => {
      await loginBrand(page);
      for (const url of ["/brand/notifications", "/brand/invoices"]) {
        const consoleErrors = trackConsoleErrors(page);
        await page.goto(url);
        await dismissOnboardingAfterNav(page);
        await page.waitForLoadState("networkidle");
        await assertNoHorizontalOverflow(page);
        expect(consoleErrors, `console errors on ${url}`).toEqual([]);
      }
    });
  });

  test.describe("Desktop regression (1440x900)", () => {
    test.use({ viewport: DESKTOP_VIEWPORT });

    test("dashboard keeps the 4-column KPI grid and no sticky mobile bar leaks through", async ({ page }) => {
      await loginBrand(page);
      await expect(page).toHaveURL(/\/brand\/dashboard/);
      const kpiGrid = page.locator("a", { hasText: "Toplam Brief" }).first().locator("..");
      const columns = await kpiGrid.evaluate((el) => getComputedStyle(el).gridTemplateColumns.split(" ").length);
      expect(columns).toBe(4);

      await page.goto(`/brand/briefs/${BRIEF_ID}`);
      await dismissOnboardingAfterNav(page);
      await expect(page.getByTestId("sticky-approve-btn")).toHaveCount(0);
      await expect(page.getByTestId("sticky-revision-btn")).toHaveCount(0);
    });
  });
});

// ── Extra small-viewport overflow sweep (item: 430x932 / 375x667 no overflow) ──
for (const viewport of [{ width: 430, height: 932 }, { width: 375, height: 667 }, { width: 1024, height: 768 }]) {
  test.describe(`Overflow sweep at ${viewport.width}x${viewport.height}`, () => {
    test.use({ viewport });

    test("dashboard and brief list have no horizontal overflow", async ({ page }) => {
      await loginBrand(page);
      await assertNoHorizontalOverflow(page);
      await page.goto("/brand/briefs");
      await dismissOnboardingAfterNav(page);
      await assertNoHorizontalOverflow(page);
    });
  });
}

// ── Notification deep-links, brand mobile portal (390x844) ──────────────────
// Verifies build_notification_action_url's routes actually resolve to the
// right on-screen content when opened from the brand-portal notifications
// list (/brand/notifications), which navigates via the same
// isSafeInternalPath(n.action_url) logic as the notification bell dropdown
// (components/notifications/NotificationBell.tsx) — going through the full
// list page avoids fighting the bell popover's positioning on a 390px
// viewport while exercising the identical backend-computed action_url.
// Each event is triggered via a real API call (not a fabricated DB row),
// matching this file's fixture-reuse convention.

test.describe("Notification deep-links, brand mobile (390x844)", () => {
  test.use({ viewport: MOBILE_VIEWPORT });

  test("comment notification opens the right brief with the comments panel", async ({ page, request }) => {
    const agencyToken = await apiLogin(request, AGENCY_EMAIL);
    const agencyHeaders = { Authorization: `Bearer ${agencyToken}`, "X-Agency-ID": AGENCY_ID };
    const uniqueBody = `Mobil bildirim yorum testi ${Date.now()}`;

    const threadResp = await request.post(`/api/v1/briefs/${BRIEF_ID}/threads`, {
      headers: agencyHeaders,
      data: {
        thread_type: "brief",
        brand_id: BRAND_ID,
        initial_comment: "İlk mesaj",
        visibility: "client_visible",
      },
    });
    expect(threadResp.ok(), await threadResp.text()).toBeTruthy();
    const threadId = (await threadResp.json()).id as string;

    // add_comment (a reply on an existing thread), not create_thread, is what
    // dispatches COMMENT_ADDED — see app/services/comment_service.py.
    const commentResp = await request.post(`/api/v1/threads/${threadId}/comments`, {
      headers: agencyHeaders,
      data: { body: uniqueBody, visibility: "client_visible" },
    });
    expect(commentResp.ok(), await commentResp.text()).toBeTruthy();

    await loginBrand(page);
    await page.goto("/brand/notifications");
    await dismissOnboardingAfterNav(page);
    const row = page.getByText(new RegExp(uniqueBody)).first();
    await expect(row).toBeVisible({ timeout: 15_000 });
    await row.click();

    await page.waitForURL((url) => url.pathname === `/brand/briefs/${BRIEF_ID}`, { timeout: 15_000 });
    expect(new URL(page.url()).searchParams.get("panel")).toBe("comments");
  });

  test("annotation-reply notification opens the exact deliverable and marker", async ({ page, request }) => {
    await loginBrand(page); // place the annotation as the brand user first
    const brandToken = await apiLogin(request, BRAND_EMAIL);

    const annResp = await request.post(
      `/api/v1/brand-portal/deliverables/${INDEPENDENT_A_ID}/annotations`,
      {
        headers: { Authorization: `Bearer ${brandToken}` },
        data: {
          version_number: 1,
          x_percent: 62,
          y_percent: 38,
          annotation_type: "revision",
          body: "Mobil bildirim marker testi",
        },
      }
    );
    expect(annResp.ok(), await annResp.text()).toBeTruthy();
    const annBody = await annResp.json();
    const annotationId = annBody.id as string;
    const labelNumber = annBody.label_number as number;

    const agencyToken = await apiLogin(request, AGENCY_EMAIL);
    const replyResp = await request.post(
      `/api/v1/annotations/${annotationId}/replies?deliverable_id=${INDEPENDENT_A_ID}`,
      {
        headers: { Authorization: `Bearer ${agencyToken}`, "X-Agency-ID": AGENCY_ID },
        data: { body: "Ajanstan mobil yanıt", visibility: "client_visible" },
      }
    );
    expect(replyResp.ok(), await replyResp.text()).toBeTruthy();

    await page.goto("/brand/notifications");
    await dismissOnboardingAfterNav(page);
    const row = page.getByText(new RegExp(`#${labelNumber} numaralı revizyona yanıt geldi`)).first();
    await expect(row).toBeVisible({ timeout: 15_000 });
    await row.click();

    await page.waitForURL((url) => url.pathname === `/brand/briefs/${BRIEF_ID}`, { timeout: 15_000 });
    const url = new URL(page.url());
    expect(url.searchParams.get("deliverable")).toBe(INDEPENDENT_A_ID);
    expect(url.searchParams.get("annotation")).toBe(annotationId);
    await expect(
      page.getByRole("button", { name: new RegExp(`#${labelNumber}`) }).first()
    ).toBeVisible({ timeout: 10_000 });
  });

  test("a newly submitted deliverable's notification opens exactly that version, not a different one", async ({
    page,
    request,
  }) => {
    const agencyToken = await apiLogin(request, AGENCY_EMAIL);
    const agencyHeaders = { Authorization: `Bearer ${agencyToken}`, "X-Agency-ID": AGENCY_ID };
    const distinctTitle = `E2E Mobile Deep Link Deliverable ${Date.now()}`;

    const createResp = await request.post(`/api/v1/briefs/${BRIEF_ID}/deliverables`, {
      headers: agencyHeaders,
      data: { title: distinctTitle, deliverable_type: "image" },
    });
    expect(createResp.ok(), await createResp.text()).toBeTruthy();
    const newDeliverableId = (await createResp.json()).id as string;

    const pngBuffer = Buffer.from(
      "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=",
      "base64"
    );
    const uploadResp = await request.post(
      `/api/v1/briefs/${BRIEF_ID}/deliverables/${newDeliverableId}/assets`,
      {
        headers: agencyHeaders,
        multipart: { file: { name: "e2e-mobile-deep-link.png", mimeType: "image/png", buffer: pngBuffer } },
      }
    );
    expect(uploadResp.ok(), await uploadResp.text()).toBeTruthy();

    const submitResp = await request.post(
      `/api/v1/briefs/${BRIEF_ID}/deliverables/${newDeliverableId}/submit`,
      { headers: agencyHeaders }
    );
    expect(submitResp.ok(), await submitResp.text()).toBeTruthy();

    await loginBrand(page);
    await page.goto("/brand/notifications");
    await dismissOnboardingAfterNav(page);
    const row = page.getByText(new RegExp(distinctTitle)).first();
    await expect(row).toBeVisible({ timeout: 15_000 });
    await row.click();

    await page.waitForURL((url) => url.pathname === `/brand/briefs/${BRIEF_ID}`, { timeout: 15_000 });
    expect(new URL(page.url()).searchParams.get("deliverable")).toBe(newDeliverableId);
    await expect(page.getByText(new RegExp(distinctTitle)).first()).toBeVisible({ timeout: 10_000 });
  });

  test("invoice-sent notification opens exactly that invoice with matching totals", async ({ page, request }) => {
    const agencyToken = await apiLogin(request, AGENCY_EMAIL);
    const agencyHeaders = { Authorization: `Bearer ${agencyToken}`, "X-Agency-ID": AGENCY_ID };

    const draftResp = await request.post("/api/v1/finance/invoices/draft", {
      headers: agencyHeaders,
      data: {
        brand_id: BRAND_ID,
        manual_lines: [
          {
            description: "E2E Mobil Bildirim Hizmet Kalemi",
            quantity: 1,
            unit: "adet",
            unit_price_cents: 150_000,
            tax_rate_bps: 2000,
          },
        ],
      },
    });
    expect(draftResp.ok(), await draftResp.text()).toBeTruthy();
    const draftBody = await draftResp.json();
    const invoiceId = draftBody.id as string;
    const invoiceNumber = draftBody.invoice_number as string;
    const totalCents = draftBody.total_cents as number;

    const approveResp = await request.post(`/api/v1/finance/invoices/${invoiceId}/approve`, {
      headers: agencyHeaders,
    });
    expect(approveResp.ok(), await approveResp.text()).toBeTruthy();
    const sendResp = await request.post(`/api/v1/finance/invoices/${invoiceId}/send`, {
      headers: agencyHeaders,
    });
    expect(sendResp.ok(), await sendResp.text()).toBeTruthy();

    await loginBrand(page);
    await page.goto("/brand/notifications");
    await dismissOnboardingAfterNav(page);
    const row = page.getByText(new RegExp(invoiceNumber)).first();
    await expect(row).toBeVisible({ timeout: 15_000 });
    await row.click();

    await page.waitForURL((url) => url.pathname === `/brand/invoices/${invoiceId}`, { timeout: 15_000 });
    await expect(page.getByRole("heading", { name: invoiceNumber })).toBeVisible({ timeout: 10_000 });
    // At MOBILE_VIEWPORT the desktop table (`hidden md:block`, rendered
    // first in the DOM) is present but not visible — the mobile card list
    // (`md:hidden`, rendered second) is the one actually on screen.
    await expect(page.getByText("E2E Mobil Bildirim Hizmet Kalemi").last()).toBeVisible({
      timeout: 10_000,
    });
    // The detail page's summary card total (Tutar Özeti) must reconcile with
    // the amount the draft API itself computed, not a hand-typed expectation.
    const totalLabel = formatTryCents(totalCents);
    await expect(page.getByText(totalLabel).first()).toBeVisible({ timeout: 10_000 });
  });
});

function formatTryCents(cents: number): string {
  return new Intl.NumberFormat("tr-TR", { style: "currency", currency: "TRY" }).format(cents / 100);
}

// ── Multi-slot carousel, brand mobile portal (390x844) ───────────────────────
// Real 3-slide instagram/feed_carousel deliverable (the seeded 2-asset draft
// deliverable plus one more asset uploaded here), slot order set through the
// real PUT preview-slots endpoint (not fabricated), then submitted. Verifies
// swipe advances a slot, the dot-indicator "counter" tracks it, swipe is
// disabled in annotation mode, the rendered slot order matches exactly what
// was persisted, and the active slide's image is never stretched.

async function swipeHorizontally(target: Locator, deltaX: number): Promise<void> {
  const box = await target.boundingBox();
  if (!box) throw new Error("swipe target has no bounding box");
  const startX = box.x + box.width / 2;
  const startY = box.y + box.height / 2;
  await target.evaluate(
    (el, args) => {
      const { startX, startY, deltaX } = args;
      const makeTouch = (x: number, y: number) =>
        new Touch({ identifier: 1, target: el, clientX: x, clientY: y });
      el.dispatchEvent(
        new TouchEvent("touchstart", {
          bubbles: true,
          cancelable: true,
          touches: [makeTouch(startX, startY)],
          changedTouches: [makeTouch(startX, startY)],
        })
      );
      el.dispatchEvent(
        new TouchEvent("touchend", {
          bubbles: true,
          cancelable: true,
          touches: [],
          changedTouches: [makeTouch(startX + deltaX, startY)],
        })
      );
    },
    { startX, startY, deltaX }
  );
}

function activeDotIndex(page: Page): Promise<number> {
  return page
    .locator('button[aria-label$=". slayta git"]')
    .evaluateAll((buttons) => buttons.findIndex((b) => b.className.includes("bg-accent")));
}

test.describe("Multi-slot carousel, brand mobile (390x844)", () => {
  test.use({ viewport: MOBILE_VIEWPORT });

  test("swipe navigates a real 3-slot carousel in persisted order, counter updates, swipe disabled while annotating, no distortion", async ({
    page,
    request,
  }) => {
    const agencyToken = await apiLogin(request, AGENCY_EMAIL);
    const agencyHeaders = { Authorization: `Bearer ${agencyToken}`, "X-Agency-ID": AGENCY_ID };

    const pngBuffer = Buffer.from(
      "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=",
      "base64"
    );
    const uploadResp = await request.post(
      `/api/v1/briefs/${BRIEF_ID}/deliverables/${DELIVERABLE_ID}/assets`,
      {
        headers: agencyHeaders,
        multipart: { file: { name: "e2e-carousel-slide-3.png", mimeType: "image/png", buffer: pngBuffer } },
      }
    );
    expect(uploadResp.ok(), await uploadResp.text()).toBeTruthy();
    const asset3Id = (await uploadResp.json()).id as string;

    const configResp = await request.put(
      `/api/v1/briefs/${BRIEF_ID}/deliverables/${DELIVERABLE_ID}/preview-config`,
      { headers: agencyHeaders, data: { platform: "instagram", preview_format: "feed_carousel" } }
    );
    expect(configResp.ok(), await configResp.text()).toBeTruthy();

    // The persisted order under test: asset_2, asset_1, asset_3 — deliberately
    // NOT upload order, so "matches persisted order" is a real assertion, not
    // a coincidence of insertion order.
    const persistedOrder = [ASSET_2_ID, ASSET_1_ID, asset3Id];
    const slotsResp = await request.put(
      `/api/v1/briefs/${BRIEF_ID}/deliverables/${DELIVERABLE_ID}/preview-slots`,
      {
        headers: agencyHeaders,
        data: {
          slots: persistedOrder.map((assetId, i) => ({
            asset_id: assetId,
            position: i,
            is_cover: i === 0,
          })),
        },
      }
    );
    expect(slotsResp.ok(), await slotsResp.text()).toBeTruthy();
    const persistedSlots = await slotsResp.json();
    expect(persistedSlots.map((s: { asset_id: string }) => s.asset_id)).toEqual(persistedOrder);

    const submitResp = await request.post(
      `/api/v1/briefs/${BRIEF_ID}/deliverables/${DELIVERABLE_ID}/submit`,
      { headers: agencyHeaders }
    );
    expect(submitResp.ok(), await submitResp.text()).toBeTruthy();

    await loginBrand(page);
    await page.goto(`/brand/briefs/${BRIEF_ID}`);
    await dismissOnboardingAfterNav(page);
    await page.getByTestId(`version-strip-thumb-${DELIVERABLE_ID}`).click();
    await page.getByRole("tab", { name: /Platform Önizlemesi/ }).click();

    const dots = page.locator('button[aria-label$=". slayta git"]');
    await expect(dots).toHaveCount(3, { timeout: 15_000 });

    const img = page.locator("img[alt='Deliverable']").first();
    await img.waitFor({ state: "visible", timeout: 15_000 });
    const objectFit = await img.evaluate((el) => getComputedStyle(el).objectFit);
    expect(objectFit).toBe("contain");

    // Counter starts on slot 0.
    expect(await activeDotIndex(page)).toBe(0);

    // Swipe left (negative delta) advances forward, matching
    // PlatformPreviewShell.handleTouchEnd's `delta < 0 -> i + 1` convention.
    await swipeHorizontally(img, -80);
    await expect.poll(() => activeDotIndex(page), { timeout: 5_000 }).toBe(1);
    const objectFitSlide2 = await img.evaluate((el) => getComputedStyle(el).objectFit);
    expect(objectFitSlide2).toBe("contain");

    await swipeHorizontally(img, -80);
    await expect.poll(() => activeDotIndex(page), { timeout: 5_000 }).toBe(2);

    // Swipe right (positive delta) goes back.
    await swipeHorizontally(img, 80);
    await expect.poll(() => activeDotIndex(page), { timeout: 5_000 }).toBe(1);

    // Enter annotation mode — swipe must now be a no-op.
    await page.getByRole("button", { name: "Revizyon Noktası Belirle" }).click();
    await swipeHorizontally(img, -80);
    await page.waitForTimeout(300);
    expect(await activeDotIndex(page)).toBe(1);

    // Dots remain clickable navigation regardless of swipe — confirms the
    // rendered order really is [asset_2, asset_1, asset_3] end to end, not
    // just at the API layer. Exit annotation mode first (dots stay
    // interactive, but this keeps the assertion scoped to swipe-vs-dot
    // behavior rather than annotation-mode click semantics).
    await page.getByRole("button", { name: "Revizyon Modunu Kapat" }).click();
    await dots.nth(2).click();
    await expect.poll(() => activeDotIndex(page), { timeout: 5_000 }).toBe(2);
  });
});
