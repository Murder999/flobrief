import { expect, test, type Page } from "@playwright/test";

const pages = [
  {
    path: "/ajans-programi",
    h1: "Ajans Programı — Brief, Müşteri, Revizyon ve Onay Yönetimi",
    title: "Ajans Programı: Brief, Revizyon ve Onay Yönetimi | PostPiloter",
  },
  {
    path: "/musteri-onay-sistemi",
    h1: "Müşteri Onay Sistemi — Tasarım ve İçerik Onaylarını Tek Yerde Yönetin",
    title: "Müşteri Onay Sistemi: Tasarım ve İçerik Onayı | PostPiloter",
  },
  {
    path: "/revizyon-takip",
    h1: "Revizyon Takip Sistemi — Müşteri Geri Bildirimlerini Kaybetmeyin",
    title: "Revizyon Takip Sistemi: Müşteri Geri Bildirimleri | PostPiloter",
  },
  {
    path: "/musteri-portali",
    h1: "Ajanslar İçin Müşteri Portalı",
    title: "Ajanslar İçin Müşteri Portalı | PostPiloter",
  },
  {
    path: "/online-brief",
    h1: "Online Brief Oluşturma — Ajanslar İçin Dijital Brief Formu",
    title: "Online Brief Oluşturma: Dijital Brief Formu | PostPiloter",
  },
] as const;

async function assertNoHorizontalOverflow(page: Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(1);
}

test.describe("SEO landing pages", () => {
  for (const landing of pages) {
    test(`${landing.path} renders with unique SEO and shared public shell`, async ({ page }) => {
      const consoleErrors: string[] = [];
      page.on("console", (message) => {
        if (message.type() === "error") consoleErrors.push(message.text());
      });

      // These pages are public and static. Keep the global AuthProvider's
      // background refresh deterministic without requiring the backend stack.
      await page.route("**/api/v1/auth/refresh", (route) =>
        route.fulfill({
          status: 204,
        })
      );

      const response = await page.goto(landing.path, { waitUntil: "networkidle" });
      expect(response?.ok()).toBeTruthy();
      await expect(page).toHaveTitle(landing.title);
      await expect(page.locator("h1")).toHaveCount(1);
      await expect(page.locator("h1")).toHaveText(landing.h1);
      await expect(page.locator("header nav")).toBeVisible();
      await expect(page.getByTestId("public-footer")).toBeVisible();

      const description = page.locator('meta[name="description"]');
      await expect(description).toHaveAttribute("content", /.{40,}/);
      await expect(page.locator('link[rel="canonical"]')).toHaveAttribute("href", `https://postpiloter.com${landing.path}`);
      const robots = page.locator('meta[name="robots"]');
      if (await robots.count()) await expect(robots).not.toHaveAttribute("content", /noindex/i);

      await assertNoHorizontalOverflow(page);
      expect(consoleErrors).toEqual([]);
    });
  }

  test("mobile navigation remains usable without horizontal overflow", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto("/musteri-portali");
    await page.getByRole("button", { name: "Menüyü aç" }).click();
    await expect(page.getByRole("navigation", { name: "Ana navigasyon" }).getByRole("link", { name: "Fiyatlandırma" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Giriş Yap" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Demoyu İncele" }).first()).toBeVisible();
    await assertNoHorizontalOverflow(page);
  });

  test("sitemap includes all five landing URLs", async ({ request }) => {
    const response = await request.get("/sitemap.xml");
    expect(response.ok()).toBeTruthy();
    const sitemap = await response.text();
    for (const landing of pages) {
      expect(sitemap).toContain(`https://postpiloter.com${landing.path}`);
    }
  });
});
