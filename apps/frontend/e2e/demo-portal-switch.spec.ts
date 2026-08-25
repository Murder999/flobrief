import { expect, test, type Page } from "@playwright/test";

const viewports = [
  { width: 1366, height: 768 },
  { width: 1440, height: 900 },
  { width: 1920, height: 1080 },
] as const;

async function startDemo(page: Page) {
  const apiBase = process.env.E2E_API_BASE_URL ?? "http://localhost:8000";
  const nonce = crypto.randomUUID().replaceAll("-", "").slice(0, 16);
  const testIp = `2001:db8:${nonce.slice(0, 4)}:${nonce.slice(4, 8)}:${nonce.slice(8, 12)}:${nonce.slice(12)}::1`;
  const response = await page.request.post(`${apiBase}/api/v1/demo/sandboxes`, {
    data: { turnstile_token: null },
    headers: { "X-Forwarded-For": testIp },
  });

  expect(response.status(), await response.text()).toBe(201);
  await page.goto("/dashboard?demo=1");
}

async function dismissDemoOnboarding(page: Page) {
  const laterButton = page.getByRole("button", { name: /Daha Sonra|Later/ });
  const appeared = await laterButton
    .waitFor({ state: "visible", timeout: 3_000 })
    .then(() => true)
    .catch(() => false);
  if (appeared) await laterButton.click();
}

async function expectPortal(page: Page, portal: "agency" | "brand") {
  const route = portal === "agency" ? "/dashboard" : "/brand/dashboard";
  const activeLabel = portal === "agency" ? /Ajans Portalı|Agency Portal/ : /Marka Portalı|Brand Portal/;
  const inactiveLabel = portal === "agency" ? /Marka Portalı|Brand Portal/ : /Ajans Portalı|Agency Portal/;

  await page.waitForURL((url) => url.pathname === route, { timeout: 30_000 });
  await expect(page).not.toHaveURL(/\/(?:auth|brand)\/login/);
  const switcher = page.getByTestId("demo-portal-switcher");
  await expect(switcher).toHaveCount(1);
  await expect(switcher).toBeVisible();
  await expect(switcher.getByRole("button", { name: activeLabel }), page.url()).toHaveAttribute("aria-pressed", "true");
  await expect(switcher.getByRole("button", { name: inactiveLabel })).toHaveAttribute("aria-pressed", "false");
  await dismissDemoOnboarding(page);
}

async function switchPortal(page: Page, target: "agency" | "brand") {
  const label = target === "agency" ? /Ajans Portalı|Agency Portal/ : /Marka Portalı|Brand Portal/;
  const switcher = page.getByTestId("demo-portal-switcher");
  await page.route("**/api/v1/demo/switch-portal", async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 250));
    await route.continue();
  }, { times: 1 });
  await switcher.getByRole("button", { name: label }).click();
  await expect(switcher).toHaveAttribute("aria-busy", "true");
  await expectPortal(page, target);
}

async function expectFloatingDockAtDesktopViewports(page: Page) {
  for (const viewport of viewports) {
    await page.setViewportSize(viewport);
    const sidebar = page.getByTestId("app-sidebar");
    const switcher = page.getByTestId("demo-portal-switcher");
    const dock = page.getByTestId("demo-portal-switcher-dock");
    const navigation = page.getByTestId("sidebar-navigation");
    const utilities = page.getByTestId("sidebar-utilities");
    const [sidebarBox, dockBox, navigationBox, utilitiesBox] = await Promise.all([
      sidebar.boundingBox(),
      dock.boundingBox(),
      navigation.boundingBox(),
      utilities.boundingBox(),
    ]);

    expect(sidebarBox).not.toBeNull();
    expect(dockBox).not.toBeNull();
    expect(navigationBox).not.toBeNull();
    expect(utilitiesBox).not.toBeNull();
    expect(Math.round(sidebarBox!.height)).toBe(viewport.height);
    expect(navigationBox!.y + navigationBox!.height).toBeLessThanOrEqual(utilitiesBox!.y + 1);
    expect(Math.round(viewport.width - dockBox!.x - dockBox!.width)).toBe(24);
    expect(Math.round(viewport.height - dockBox!.y - dockBox!.height)).toBe(24);
    expect(await switcher.evaluate((element) => getComputedStyle(element).position)).toBe("fixed");
    await expect(sidebar.getByTestId("demo-portal-switcher")).toHaveCount(0);
    await expect(utilities.getByTestId("demo-portal-switcher")).toHaveCount(0);
    await expect(switcher.getByRole("button", { name: /Ajans Portalı|Agency Portal/ })).toBeVisible();
    await expect(switcher.getByRole("button", { name: /Marka Portalı|Brand Portal/ })).toBeVisible();

    const beforeScroll = await dock.boundingBox();
    await navigation.evaluate((element) => element.scrollTo({ top: element.scrollHeight }));
    expect(await dock.boundingBox()).toEqual(beforeScroll);
  }
}

async function expectFloatingDockOnMobile(page: Page) {
  const viewport = { width: 390, height: 844 };
  await page.setViewportSize(viewport);

  const switcher = page.getByTestId("demo-portal-switcher");
  const dock = page.getByTestId("demo-portal-switcher-dock");
  const bottomNavigation = page.getByTestId("mobile-bottom-navigation");
  await expect(page.getByTestId("app-sidebar")).toBeHidden();
  await expect(bottomNavigation).toBeVisible();
  await expect(switcher).toHaveCount(1);

  const [dockBox, bottomNavigationBox] = await Promise.all([
    dock.boundingBox(),
    bottomNavigation.boundingBox(),
  ]);
  expect(dockBox).not.toBeNull();
  expect(bottomNavigationBox).not.toBeNull();
  expect(dockBox!.width).toBeLessThanOrEqual(viewport.width - 24);
  expect(Math.abs(dockBox!.x + dockBox!.width / 2 - viewport.width / 2)).toBeLessThanOrEqual(1);
  expect(bottomNavigationBox!.y - (dockBox!.y + dockBox!.height)).toBeGreaterThanOrEqual(11);

  await bottomNavigation.locator("button").click();
  const drawer = page.getByRole("dialog");
  await expect(drawer).toBeVisible();
  await expect(drawer.getByTestId("demo-portal-switcher")).toHaveCount(0);
  await page.keyboard.press("Escape");
}

async function expectInlineSwitchError(page: Page, target: "agency" | "brand") {
  const label = target === "agency" ? /Ajans Portalı|Agency Portal/ : /Marka Portalı|Brand Portal/;
  const switcher = page.getByTestId("demo-portal-switcher");
  await page.route("**/api/v1/demo/switch-portal", async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 150));
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        portal: target,
        redirect_to: "/unexpected",
        expires_at: new Date(Date.now() + 60_000).toISOString(),
        access_token: "unused",
        token_type: "bearer",
        expires_in: 60,
      }),
    });
  }, { times: 1 });

  await switcher.getByRole("button", { name: label }).click();
  await expect(switcher).toHaveAttribute("aria-busy", "true");
  await expect(switcher.getByRole("alert")).toBeVisible();
  await expect(switcher).toHaveAttribute("aria-busy", "false");
  await expect(switcher.getByRole("button", { name: label })).toBeEnabled();
}

test.describe("demo portal identity switch", () => {
  test("switches both ways repeatedly without exposing a login route", async ({ page }) => {
    const visitedPaths: string[] = [];
    page.on("framenavigated", (frame) => {
      if (frame === page.mainFrame()) visitedPaths.push(new URL(frame.url()).pathname);
    });

    await startDemo(page);
    await expectPortal(page, "agency");
    await expectFloatingDockAtDesktopViewports(page);
    await expectFloatingDockOnMobile(page);

    await switchPortal(page, "brand");
    await expectFloatingDockAtDesktopViewports(page);
    await expectFloatingDockOnMobile(page);
    await expectInlineSwitchError(page, "agency");
    await switchPortal(page, "agency");
    await switchPortal(page, "brand");

    expect(visitedPaths).not.toContain("/auth/login");
    expect(visitedPaths).not.toContain("/brand/login");
  });
});
