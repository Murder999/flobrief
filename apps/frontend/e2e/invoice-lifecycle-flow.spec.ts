import { test, expect, type Page, type Locator } from "@playwright/test";
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

/**
 * Regression suite for the client-invoicing lifecycle (Part 2 Phase 4):
 * selecting locked/billable TimeEntry rows on /dashboard/finance/
 * billable-time, generating a real invoice draft, editing its lines,
 * approve -> send -> PDF download (asserting the PDF is a real "draft
 * invoice / proforma" document, never claiming to be an official e-Fatura),
 * recording payments through the draft/partially_paid/paid state machine,
 * and double-invoicing prevention (an already-invoiced TimeEntry can never
 * be selected again).
 *
 * Fixture is seeded via apps/backend/scripts/e2e_seed_finance.py: a fresh
 * Agency/Brand with an active hourly CommercialTerms, a MemberCostRate, and
 * two locked+billable TimeEntry rows (3 hours total) not yet invoiced. This
 * spec drives the entire draft -> paid lifecycle through the real browser
 * UI against the real local backend/Postgres, so every number and status
 * asserted below comes from an action the test itself performed.
 */

const BACKEND_DIR = path.resolve(__dirname, "../../backend");
const PYTHON = process.env.E2E_PYTHON ?? path.join(BACKEND_DIR, ".venv", "Scripts", "python.exe");

let OWNER_EMAIL: string;
let PASSWORD: string;
let AGENCY_ID: string;

function runSeedScript(args: string[]): Record<string, string> {
  const output = execFileSync(PYTHON, ["scripts/e2e_seed_finance.py", ...args], {
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
  PASSWORD = env.E2E_PASSWORD;
  AGENCY_ID = env.__AGENCY_ID__;
  if (!OWNER_EMAIL || !AGENCY_ID) {
    throw new Error("finance fixture seed did not return the expected env vars");
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

const KNOWN_NOISE = /^Failed to load resource:|^Failed to fetch RSC payload/;

function trackConsoleErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error" && !KNOWN_NOISE.test(msg.text())) errors.push(msg.text());
  });
  page.on("pageerror", (err) => errors.push(err.message));
  return errors;
}

// components/ui/select.tsx renders a <label> with no htmlFor/id -- getByLabel
// cannot resolve any <Select>. Locate the real <select> via its visible
// label text, scoped to a container so same-labelled Selects elsewhere on
// the page (e.g. two "Para Birimi" fields) never collide.
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

/** Extracts real text from a downloaded PDF by shelling out to the
 * backend's own `pypdf` (already a real backend dependency, the same
 * library the backend's own PDF-content tests use). The backend's invoice
 * PDFs embed a Unicode TTF via a composite/Type0 font so Turkish
 * characters render correctly -- their content streams reference glyph
 * indices through a ToUnicode CMap rather than literal ASCII bytes, so a
 * naive zlib-inflate + substring search on the raw PDF cannot recover the
 * rendered words. Reusing pypdf (which already implements that decoding)
 * is the correct approach, not a workaround. */
function extractPdfText(pdfPath: string): string {
  return execFileSync(PYTHON, ["scripts/e2e_extract_pdf_text.py", pdfPath], {
    cwd: BACKEND_DIR,
    encoding: "utf-8",
    maxBuffer: 1024 * 1024 * 20,
  });
}

test.describe.serial("Invoice lifecycle flow", () => {
  let invoiceUrl: string;

  test("owner selects locked billable time and generates a real invoice draft", async ({ page }) => {
    const consoleErrors = trackConsoleErrors(page);
    await loginAgency(page, OWNER_EMAIL, PASSWORD);

    await page.goto("/dashboard/finance/billable-time");
    await expect(page.getByRole("heading", { name: "Faturalandırılabilir Zaman" })).toBeVisible({
      timeout: 15_000,
    });

    const brandSelect = selectByLabel(page.locator("body"), "Marka");
    await expect(brandSelect).toBeVisible({ timeout: 10_000 });
    await brandSelect.selectOption({ label: "E2E Finance Brand A" });

    // The billable-time table has no description column (Kullanıcı/Brief/
    // Kategori/Tarih/Süre only) -- assert on what it actually renders: the
    // two seeded locked entries' real durations (2.0s/1.0s = 7200s/3600s)
    // and the owner's name as the time-logging user.
    await expect(page.getByText("2.0s").first()).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("1.0s").first()).toBeVisible();
    await expect(page.getByText("E2E Finance Owner").first()).toBeVisible();

    await page.getByRole("checkbox", { name: "Tümünü seç (bu listede)" }).check();
    await expect(page.getByText(/2 kayıt seçildi/)).toBeVisible();

    await page.getByRole("button", { name: /Fatura Taslağı Oluştur/ }).click();
    await page.waitForURL(/\/dashboard\/finance\/invoices\/[0-9a-f-]+$/, { timeout: 15_000 });
    invoiceUrl = page.url();

    await expect(page.locator("text=Taslak").first()).toBeVisible({ timeout: 10_000 });
    // 3 hours * 1000 TRY/hour = 3000 TRY subtotal (Turkish-formatted as
    // "3.000,00"), + 20% KDV = 3600 total -- real numbers derived from the
    // two seeded locked TimeEntry rows this test just selected, not
    // placeholders.
    await expect(page.getByText("E2E billable work block 1").first()).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("E2E billable work block 2").first()).toBeVisible();
    await expect(page.getByText("3.000,00").first()).toBeVisible();
    await expect(page.getByText("3.600,00").first()).toBeVisible();

    expect(consoleErrors, `Unexpected console errors: ${consoleErrors.join("\n")}`).toEqual([]);
  });

  test("owner edits a line item on the draft (add then remove, netting back to the original total)", async ({
    page,
  }) => {
    await loginAgency(page, OWNER_EMAIL, PASSWORD);
    await page.goto(invoiceUrl);
    await expect(page.getByRole("heading", { level: 3, name: "Fatura Kalemleri" })).toBeVisible({
      timeout: 15_000,
    });

    const linesCard = cardByTitle(page, "Fatura Kalemleri");
    await linesCard.getByRole("button", { name: "Kalem Ekle" }).click();
    await linesCard.getByLabel("Açıklama").fill("E2E manuel ek kalem");
    await linesCard.getByLabel("Miktar").fill("1");
    await linesCard.getByLabel("Birim", { exact: true }).fill("adet");
    await linesCard.getByLabel(/Birim Fiyat/).fill("100");
    await linesCard.getByRole("button", { name: "Kalemi Ekle" }).click();
    await expect(page.getByText("Kalem eklendi.")).toBeVisible({ timeout: 10_000 });
    await expect(linesCard.getByText("E2E manuel ek kalem").first()).toBeVisible({ timeout: 10_000 });

    // Scope to the specific row for the manual line just added -- the
    // desktop table renders a real ARIA row per line, so this targets only
    // that row's own remove button, never one of the other two (seeded)
    // lines' remove buttons.
    await linesCard
      .getByRole("row", { name: "E2E manuel ek kalem" })
      .getByRole("button", { name: "Kalemi kaldır" })
      .click();
    await expect(page.getByText("Kalemi Kaldır")).toBeVisible({ timeout: 10_000 });
    await page.getByRole("button", { name: "Kaldır", exact: true }).click();
    await expect(page.getByText("Kalem kaldırıldı.")).toBeVisible({ timeout: 10_000 });
    await expect(linesCard.getByText("E2E manuel ek kalem")).toHaveCount(0);
  });

  test("approve, send, and download a PDF that identifies itself as a draft/proforma document, never as an official e-Fatura", async ({
    page,
  }) => {
    await loginAgency(page, OWNER_EMAIL, PASSWORD);
    await page.goto(invoiceUrl);
    await expect(page.getByRole("button", { name: "Onayla" })).toBeVisible({ timeout: 15_000 });

    await page.getByRole("button", { name: "Onayla" }).click();
    await expect(page.getByText("Fatura onaylandı.")).toBeVisible({ timeout: 10_000 });
    await expect(page.locator("text=Onaylandı").first()).toBeVisible({ timeout: 10_000 });

    await page.getByRole("button", { name: "Gönder" }).click();
    await expect(page.getByText("Fatura gönderildi.")).toBeVisible({ timeout: 10_000 });
    await expect(page.locator("text=Gönderildi").first()).toBeVisible({ timeout: 10_000 });

    const downloadPromise = page.waitForEvent("download");
    await page.getByRole("button", { name: "PDF İndir" }).click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toMatch(/^fatura-.+\.pdf$/);

    const filePath = await download.path();
    expect(filePath).toBeTruthy();
    const bytes = fs.readFileSync(filePath as string);
    expect(bytes.subarray(0, 4).toString("ascii")).toBe("%PDF");
    expect(bytes.length).toBeGreaterThan(500);

    const text = extractPdfText(filePath as string);
    // Real content, not an error stub: the draft-invoice title renders
    // (glyph transliteration for the Turkish "Ğ" can degrade the tail of
    // "TASLAĞI" when no system Unicode font is found, so match the stable
    // "TASLA" prefix, exactly like the backend's own PDF test does).
    expect(text.toUpperCase()).toContain("TASLA");
    // The distinctive internal cost rate must never render on a customer
    // document.
    expect(text).not.toContain("13337");
    // The document must carry the "not a real e-Fatura" disclaimer, but
    // never an affirmative claim of being one.
    expect(text.toLowerCase()).toMatch(/e-fatura/);
    expect(text.toLowerCase().replace(/\s+/g, "")).not.toContain("buobirefatura");
  });

  test("records payments through partially_paid -> paid, and the invoiced time entries can never be selected again", async ({
    page,
  }) => {
    await loginAgency(page, OWNER_EMAIL, PASSWORD);
    await page.goto(invoiceUrl);
    await expect(page.getByRole("button", { name: "Ödeme Kaydet" })).toBeVisible({ timeout: 15_000 });

    // Total is 3600 TRY (3000 subtotal + 20% KDV) after the add/remove line
    // edit netted back to the original two seeded time entries.
    await page.getByRole("button", { name: "Ödeme Kaydet" }).click();
    const drawer1 = page.getByText("Ödeme Kaydet").locator("../..");
    await page.getByLabel("Tutar").fill("2000");
    const methodSelect1 = selectByLabel(page.locator("body"), "Ödeme Yöntemi");
    await methodSelect1.selectOption({ label: "Banka Havalesi" });
    await page.getByLabel("Ödeme Tarihi").fill(new Date().toISOString().slice(0, 16));
    await page.getByRole("button", { name: "Kaydet", exact: true }).click();
    await expect(page.getByText("Ödeme kaydedildi.")).toBeVisible({ timeout: 10_000 });
    void drawer1;

    await page.reload();
    await expect(page.locator("text=Kısmen Ödendi").first()).toBeVisible({ timeout: 15_000 });

    await page.getByRole("button", { name: "Ödeme Kaydet" }).click();
    await page.getByLabel("Tutar").fill("1600");
    const methodSelect2 = selectByLabel(page.locator("body"), "Ödeme Yöntemi");
    await methodSelect2.selectOption({ label: "Banka Havalesi" });
    await page.getByLabel("Ödeme Tarihi").fill(new Date().toISOString().slice(0, 16));
    await page.getByRole("button", { name: "Kaydet", exact: true }).click();
    await expect(page.getByText("Ödeme kaydedildi.")).toBeVisible({ timeout: 10_000 });

    await page.reload();
    await expect(page.locator("text=Ödendi").first()).toBeVisible({ timeout: 15_000 });

    // Double-invoicing prevention: the two now-invoiced time entries have
    // disappeared from the billable-time list, since invoiced_at is set.
    await page.goto("/dashboard/finance/billable-time");
    const brandSelect = selectByLabel(page.locator("body"), "Marka");
    await expect(brandSelect).toBeVisible({ timeout: 10_000 });
    await brandSelect.selectOption({ label: "E2E Finance Brand A" });

    await expect(page.getByText("Faturalandırılabilir zaman kaydı yok").first()).toBeVisible({
      timeout: 10_000,
    });
    // Both seeded entries were the only billable rows for this brand -- the
    // real empty state above already proves neither is selectable again,
    // and no row checkbox remains at all.
    await expect(page.getByRole("checkbox", { name: "Kaydı seç" })).toHaveCount(0);
  });
});
