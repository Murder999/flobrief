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
  await expect(page.getByTestId("app-sidebar")).toBeVisible();
  const switcher = page.getByTestId("demo-portal-switcher");
  await expect(switcher).toBeVisible();
  await expect(switcher.getByRole("button", { name: activeLabel })).toHaveAttribute("aria-pressed", "true");
  await expect(switcher.getByRole("button", { name: inactiveLabel })).toHaveAttribute("aria-pressed", "false");
}

async function switchPortal(page: Page, target: "agency" | "brand") {
  const label = target === "agency" ? /Ajans Portalı|Agency Portal/ : /Marka Portalı|Brand Portal/;
  const switcher = page.getByTestId("demo-portal-switcher");
  let resolvePayload!: (payload: { status: number; body: string }) => void;
  const payloadPromise = new Promise<{ status: number; body: string }>((resolve) => {
    resolvePayload = resolve;
  });
  await page.route("**/api/v1/demo/switch-portal", async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 250));
    const response = await route.fetch();
    resolvePayload({ status: response.status(), body: await response.text() });
    await route.fulfill({ response });
  }, { times: 1 });
  await switcher.getByRole("button", { name: label }).click();
  await expect(switcher).toHaveAttribute("aria-busy", "true");
  const payload = await payloadPromise;
  expect(payload.status, payload.body).toBe(200);
  expect(JSON.parse(payload.body).access_token).toBeTruthy();
  await expectPortal(page, target);
}

async function expectSidebarAtViewports(page: Page) {
  for (const viewport of viewports) {
    await page.setViewportSize(viewport);
    const sidebar = page.getByTestId("app-sidebar");
    const switcher = page.getByTestId("demo-portal-switcher");
    const navigation = page.getByTestId("sidebar-navigation");
    const utilities = page.getByTestId("sidebar-utilities");
    const [sidebarBox, switcherBox, navigationBox, utilitiesBox] = await Promise.all([
      sidebar.boundingBox(),
      switcher.boundingBox(),
      navigation.boundingBox(),
      utilities.boundingBox(),
    ]);

    expect(sidebarBox).not.toBeNull();
    expect(switcherBox).not.toBeNull();
    expect(navigationBox).not.toBeNull();
    expect(utilitiesBox).not.toBeNull();
    expect(Math.round(sidebarBox!.height)).toBe(viewport.height);
    expect(switcherBox!.y + switcherBox!.height).toBeLessThanOrEqual(navigationBox!.y + 1);
    expect(navigationBox!.y + navigationBox!.height).toBeLessThanOrEqual(utilitiesBox!.y + 1);
    await expect(utilities.getByTestId("demo-portal-switcher")).toHaveCount(0);
    await expect(switcher.getByRole("button", { name: /Ajans Portalı|Agency Portal/ })).toBeVisible();
    await expect(switcher.getByRole("button", { name: /Marka Portalı|Brand Portal/ })).toBeVisible();
  }
}

test.describe("demo portal identity switch", () => {
  test("switches both ways repeatedly without exposing a login route", async ({ page }) => {
    const visitedPaths: string[] = [];
    page.on("framenavigated", (frame) => {
      if (frame === page.mainFrame()) visitedPaths.push(new URL(frame.url()).pathname);
    });

    await startDemo(page);
    await dismissDemoOnboarding(page);
    await expectPortal(page, "agency");
    await expectSidebarAtViewports(page);

    await switchPortal(page, "brand");
    await expectSidebarAtViewports(page);
    await switchPortal(page, "agency");
    await switchPortal(page, "brand");

    expect(visitedPaths).not.toContain("/auth/login");
    expect(visitedPaths).not.toContain("/brand/login");
  });
});
