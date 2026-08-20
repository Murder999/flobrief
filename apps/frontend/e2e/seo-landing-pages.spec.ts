import { expect, test, type Page } from "@playwright/test";

const pages = [
  {
    path: "/ajans-programi",
    enH1: "Creative Agency Management Software for Briefs, Feedback, and Approvals",
    enTitle: "Creative Agency Management Software | PostPiloter",
    trH1: "Ajans Programı — Brief, Müşteri, Revizyon ve Onay Yönetimi",
    trTitle: "Ajans Programı: Brief, Revizyon ve Onay Yönetimi | PostPiloter",
  },
  {
    path: "/musteri-onay-sistemi",
    enH1: "Client Approval Software for Creative Work",
    enTitle: "Client Approval Software for Agencies | PostPiloter",
    trH1: "Müşteri Onay Sistemi — Tasarım ve İçerik Onaylarını Tek Yerde Yönetin",
    trTitle: "Müşteri Onay Sistemi: Tasarım ve İçerik Onayı | PostPiloter",
  },
  {
    path: "/revizyon-takip",
    enH1: "Creative Proofing and Revision Tracking Software",
    enTitle: "Creative Proofing and Revision Tracking | PostPiloter",
    trH1: "Revizyon Takip Sistemi — Müşteri Geri Bildirimlerini Kaybetmeyin",
    trTitle: "Revizyon Takip Sistemi: Müşteri Geri Bildirimleri | PostPiloter",
  },
  {
    path: "/musteri-portali",
    enH1: "Client Portal Software for Creative Agencies",
    enTitle: "Client Portal Software for Creative Agencies | PostPiloter",
    trH1: "Ajanslar İçin Müşteri Portalı",
    trTitle: "Ajanslar İçin Müşteri Portalı | PostPiloter",
  },
  {
    path: "/online-brief",
    enH1: "Online Creative Brief Software for Agencies",
    enTitle: "Online Creative Brief Software for Agencies | PostPiloter",
    trH1: "Online Brief Oluşturma — Ajanslar İçin Dijital Brief Formu",
    trTitle: "Online Brief Oluşturma: Dijital Brief Formu | PostPiloter",
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
      await expect(page).toHaveTitle(landing.enTitle);
      await expect(page.locator("h1")).toHaveCount(1);
      await expect(page.locator("h1")).toHaveText(landing.enH1);
      await expect(page.locator("header nav")).toBeVisible();
      await expect(page.getByTestId("public-footer")).toBeVisible();

      const description = page.locator('meta[name="description"]');
      await expect(description).toHaveAttribute("content", /.{40,}/);
      await expect(page.locator('link[rel="canonical"]')).toHaveAttribute("href", `https://postpiloter.com${landing.path}`);
      await expect(page.locator('link[rel="alternate"][hreflang="tr"]')).toHaveAttribute("href", `https://postpiloter.com/tr${landing.path}`);
      const robots = page.locator('meta[name="robots"]');
      if (await robots.count()) await expect(robots).not.toHaveAttribute("content", /noindex/i);

      await assertNoHorizontalOverflow(page);
      expect(consoleErrors).toEqual([]);

      await page.goto(`/tr${landing.path}`, { waitUntil: "networkidle" });
      await expect(page).toHaveTitle(landing.trTitle);
      await expect(page.locator("h1")).toHaveText(landing.trH1);
      await expect(page.locator("html")).toHaveAttribute("lang", "tr");
      await expect(page.locator('link[rel="canonical"]')).toHaveAttribute("href", `https://postpiloter.com/tr${landing.path}`);
    });
  }

  test("mobile navigation remains usable without horizontal overflow", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto("/tr/musteri-portali");
    await page.getByRole("button", { name: "Menüyü aç" }).click();
    const mobileNavigation = page.getByRole("navigation", { name: "Ana sayfa" });
    await expect(mobileNavigation.getByRole("link", { name: "Fiyatlandırma" })).toBeVisible();
    await expect(mobileNavigation.getByRole("button", { name: "Giriş yap" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Demoyu İncele" }).first()).toBeVisible();
    await assertNoHorizontalOverflow(page);
  });

  test("public login actions open the shared modal without navigating", async ({ page }) => {
    await page.route("**/api/v1/auth/refresh", (route) => route.fulfill({ status: 204 }));
    await page.goto("/tr/ajans-programi");
    const landingUrl = page.url();

    await page.locator("header").getByRole("button", { name: "Giriş yap" }).click();
    await expect(page.getByRole("dialog", { name: "PostPiloter’a Giriş Yap" })).toBeVisible();
    expect(page.url()).toBe(landingUrl);
    await expect(page.locator('a[href="/platform/login"]')).toHaveCount(0);

    await page.getByRole("button", { name: "Kapat" }).click();
    await page.getByTestId("public-footer").getByRole("button", { name: "Giriş yap" }).click();
    await expect(page.getByRole("dialog", { name: "PostPiloter’a Giriş Yap" })).toBeVisible();
    expect(page.url()).toBe(landingUrl);
  });

  test("public surfaces do not disclose the platform login route", async ({ request }) => {
    for (const path of ["/", "/ajans-programi", "/auth/login"]) {
      const response = await request.get(path);
      expect(response.ok()).toBeTruthy();
      expect(await response.text()).not.toContain("/platform/login");
    }

    const robotsResponse = await request.get("/robots.txt");
    expect(await robotsResponse.text()).toContain("Disallow: /platform/");

    const platformResponse = await request.get("/platform/login");
    expect(platformResponse.headers()["x-robots-tag"]).toContain("noindex");
    expect(platformResponse.headers()["cache-control"]).toContain("no-store");
    expect(platformResponse.headers()["x-frame-options"]).toContain("DENY");
  });

  test("sitemap includes all five landing URLs", async ({ request }) => {
    const response = await request.get("/sitemap.xml");
    expect(response.ok()).toBeTruthy();
    const sitemap = await response.text();
    for (const landing of pages) {
      expect(sitemap).toContain(`https://postpiloter.com${landing.path}`);
      expect(sitemap).toContain(`https://postpiloter.com/tr${landing.path}`);
    }
    expect(sitemap).not.toContain("/platform/");
  });
});
