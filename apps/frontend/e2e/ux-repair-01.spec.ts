import { expect, test, type Page } from "@playwright/test";
import { dismissOnboardingIfVisible } from "./helpers/onboarding";

const OWNER_EMAIL = process.env.E2E_OWNER_EMAIL;
const PASSWORD = process.env.E2E_PASSWORD ?? "E2eTest1234!";
const READY = Boolean(OWNER_EMAIL);

async function loginAgency(page: Page) {
  await page.goto("/auth/agency-login");
  await page.locator("#agency-email").fill(OWNER_EMAIL as string);
  await page.locator("#agency-password").fill(PASSWORD);
  await page.getByRole("button", { name: "Ajans Paneline Giriş Yap" }).click();
  await page.waitForURL((url) => url.pathname.startsWith("/dashboard"), { timeout: 15_000 });
  await dismissOnboardingIfVisible(page);
}

async function expectNoHorizontalOverflow(page: Page) {
  const dimensions = await page.evaluate(() => ({
    clientWidth: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth,
  }));
  expect(dimensions.scrollWidth).toBeLessThanOrEqual(dimensions.clientWidth + 1);
}

test.describe("UX Repair 01", () => {
  test.skip(!READY, "E2E_OWNER_EMAIL is required");

  test("sidebar keeps utilities visible at supported desktop viewports", async ({ page }) => {
    await loginAgency(page);

    for (const viewport of [
      { width: 1366, height: 768 },
      { width: 1440, height: 900 },
      { width: 1920, height: 1080 },
    ]) {
      await page.setViewportSize(viewport);
      await page.goto("/dashboard");
      await dismissOnboardingIfVisible(page);

      const sidebar = page.getByTestId("app-sidebar");
      const navigation = page.getByTestId("sidebar-navigation");
      const utilities = page.getByTestId("sidebar-utilities");
      await expect(sidebar).toBeVisible();
      await expect(utilities.getByTitle("Çıkış yap")).toBeVisible();

      const boxes = await Promise.all([sidebar.boundingBox(), navigation.boundingBox(), utilities.boundingBox()]);
      const [sidebarBox, navigationBox, utilitiesBox] = boxes;
      expect(sidebarBox).not.toBeNull();
      expect(navigationBox).not.toBeNull();
      expect(utilitiesBox).not.toBeNull();
      expect(Math.round(sidebarBox!.height)).toBe(viewport.height);
      expect(utilitiesBox!.y + utilitiesBox!.height).toBeLessThanOrEqual(viewport.height + 1);
      expect(navigationBox!.y + navigationBox!.height).toBeLessThanOrEqual(utilitiesBox!.y + 1);
      expect(await navigation.evaluate((element) => getComputedStyle(element).overflowY)).toBe("auto");
      await expectNoHorizontalOverflow(page);
    }

    await expect(page.getByTestId("demo-portal-switcher")).toHaveCount(0);
  });

  test("new brief keeps one CTA, five dates, guarded navigation, and the create payload", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await loginAgency(page);
    await page.goto("/dashboard/briefs/new");

    const createButton = page.getByRole("button", { name: /Brief oluştur|Create brief/i });
    await expect(createButton).toHaveCount(1);
    await expect(page.locator('input[type="date"]')).toHaveCount(5);
    await expect(page.getByText("briefs.center brief created")).toHaveCount(0);
    await expectNoHorizontalOverflow(page);

    await page.locator("#brief-title").fill("UX Repair payload brief");
    await page.locator("#brief-startDate").fill("2026-09-01");
    await page.locator("#brief-draftDate").fill("2026-09-03");
    await page.locator("#brief-feedbackDate").fill("2026-09-05");
    await page.locator("#brief-deadline").fill("2026-09-08");
    await page.locator("#brief-publishDate").fill("2026-09-10");
    await page.getByRole("button", { name: "Instagram", exact: true }).click();
    await page.getByRole("button", { name: "Video", exact: true }).click();

    page.once("dialog", async (dialog) => {
      expect(dialog.type()).toBe("confirm");
      await dialog.dismiss();
    });
    await page.getByRole("link", { name: /Brief'ler|Briefs/, exact: true }).click();
    await expect(page).toHaveURL(/\/dashboard\/briefs\/new/);

    const requestPromise = page.waitForRequest(
      (request) => request.method() === "POST" && /\/api\/v1\/briefs(?:\?|$)/.test(request.url())
    );
    await page.route("**/api/v1/briefs", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ id: "00000000-0000-0000-0000-000000000001" }),
      });
    });
    await createButton.click();
    const createRequest = await requestPromise;
    expect(createRequest.postDataJSON()).toMatchObject({
      title: "UX Repair payload brief",
      start_date: "2026-09-01",
      draft_date: "2026-09-03",
      feedback_date: "2026-09-05",
      deadline: "2026-09-08",
      publish_date: "2026-09-10",
      platforms: ["Instagram"],
      content_types: ["Video"],
    });
  });

  test("settings shell remains present and tracks active routes", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await loginAgency(page);

    const routes = [
      "/dashboard/settings/profile",
      "/dashboard/settings/notifications",
      "/dashboard/settings/agency",
      "/dashboard/settings/branding",
      "/dashboard/settings/members",
      "/dashboard/settings/billing",
    ] as const;

    for (const route of routes) {
      await page.goto(route);
      const settingsNavigation = page.getByRole("navigation", { name: /Ayarlar menüsü|Settings navigation/ });
      await expect(settingsNavigation).toBeVisible();
      await expect(settingsNavigation.locator(`a[href="${route}"]`)).toHaveAttribute(
        "aria-current",
        "page"
      );
    }

    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/dashboard/settings/profile");
    await expect(page.locator("#settings-section")).toBeVisible();
    await expectNoHorizontalOverflow(page);
  });
});
