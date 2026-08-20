import { expect, test } from "@playwright/test";

test.describe("English and Turkish locale behavior", () => {
  test("English is the global default and unsupported browser locales fall back to English", async ({ browser }) => {
    for (const browserLocale of ["en-US", "fr-FR"]) {
      const context = await browser.newContext({ locale: browserLocale });
      const page = await context.newPage();
      await page.route("**/api/v1/auth/refresh", (route) => route.fulfill({ status: 204 }));
      await page.goto("/");
      await expect(page).toHaveURL(/\/$/);
      await expect(page.locator("html")).toHaveAttribute("lang", "en");
      await expect(page.getByRole("heading", { level: 1 })).toContainText("Move every brief");
      await context.close();
    }
  });

  test("a Turkish browser is sent to the directly accessible Turkish route", async ({ browser }) => {
    const context = await browser.newContext({ locale: "tr-TR" });
    const page = await context.newPage();
    await page.route("**/api/v1/auth/refresh", (route) => route.fulfill({ status: 204 }));
    await page.goto("/");
    await expect(page).toHaveURL(/\/tr\/?$/);
    await expect(page.locator("html")).toHaveAttribute("lang", "tr");
    await expect(page.getByRole("heading", { level: 1 })).toContainText("Her briefi, revizyonu ve onayı");
    await context.close();
  });

  test("manual selection persists and keeps the equivalent public route", async ({ page }) => {
    await page.route("**/api/v1/auth/refresh", (route) => route.fulfill({ status: 204 }));
    await page.goto("/ajans-programi");
    await page.getByRole("group", { name: "Language" }).getByRole("button", { name: "TR", exact: true }).click();
    await expect(page).toHaveURL(/\/tr\/ajans-programi$/);
    await expect(page.locator("html")).toHaveAttribute("lang", "tr");
    expect(await page.evaluate(() => localStorage.getItem("postpiloter_locale"))).toBe("tr");
    expect((await page.context().cookies()).find((cookie) => cookie.name === "postpiloter_locale")?.value).toBe("tr");

    await page.goto("/");
    await expect(page).toHaveURL(/\/tr\/?$/);

    await page.getByRole("group", { name: "Dil" }).getByRole("button", { name: "EN", exact: true }).click();
    await expect(page).toHaveURL(/\/$/);
    await expect(page.locator("html")).toHaveAttribute("lang", "en");
  });

  test("the premium flag selector stays visible without changing the home composition", async ({ browser }) => {
    const context = await browser.newContext({ locale: "en-US", viewport: { width: 360, height: 800 } });
    const page = await context.newPage();
    await page.route("**/api/v1/auth/refresh", (route) => route.fulfill({ status: 204 }));
    await page.goto("/");

    const selector = page.getByRole("group", { name: "Language" });
    await expect(selector).toBeVisible();
    await expect(selector.getByRole("button", { name: "TR", exact: true })).toContainText("🇹🇷");
    await expect(selector.getByRole("button", { name: "EN", exact: true })).toContainText("🇬🇧");
    const englishStructure = await page.locator("main").evaluate((main) =>
      Array.from(main.querySelectorAll("*")).map((element) => `${element.tagName}:${element.className}`).join("|")
    );

    await selector.getByRole("button", { name: "TR", exact: true }).click();
    await expect(page).toHaveURL(/\/tr\/?$/);
    const turkishStructure = await page.locator("main").evaluate((main) =>
      Array.from(main.querySelectorAll("*")).map((element) => `${element.tagName}:${element.className}`).join("|")
    );
    expect(turkishStructure).toBe(englishStructure);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await context.close();
  });

  test("pricing copy and currency formatting follow the UI locale without changing plan currency", async ({ page }) => {
    await page.route("**/api/v1/auth/refresh", (route) => route.fulfill({ status: 204 }));
    await page.route("**/api/v1/plans", (route) => route.fulfill({ status: 200, json: [] }));
    await page.goto("/pricing");
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("Choose the plan that fits your agency");
    await page.getByRole("group", { name: "Language" }).getByRole("button", { name: "TR", exact: true }).click();
    await expect(page).toHaveURL(/\/tr\/pricing$/);
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("Ajansınıza uygun planı seçin");
  });
});
