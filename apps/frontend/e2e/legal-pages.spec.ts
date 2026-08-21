import { expect, test, type Page } from "@playwright/test";

const englishPages = [
  { path: "/terms", heading: "Terms of Service", title: "Terms of Service | PostPiloter" },
  { path: "/privacy", heading: "Privacy Policy", title: "Privacy Policy | PostPiloter" },
  { path: "/refund-policy", heading: "Refund Policy", title: "Refund Policy | PostPiloter" },
  { path: "/contact", heading: "Contact Us", title: "Contact PostPiloter" },
] as const;

async function stabilizePublicPage(page: Page) {
  await page.route("**/api/v1/auth/refresh", (route) => route.fulfill({ status: 204 }));
  await page.route("**/api/v1/public/branding/platform-defaults", (route) => route.fulfill({
    status: 200,
    json: {
      portal_name: "PostPiloter",
      primary_color: "#4F46E5",
      secondary_color: "#7C3AED",
      accent_color: "#6366F1",
      background_color: "#FAF9F7",
      surface_color: "#FFFFFF",
      text_color: "#1A1917",
      border_color: "#E5E2DC",
      link_color: "#4338CA",
      website_url: "https://postpiloter.com",
      footer_company_name: "PostPiloter",
      copyright_text: "PostPiloter. All rights reserved.",
      public_title: "PostPiloter",
      public_description: "Agency and brand operations platform.",
    },
  }));
}

test.describe("legal and Paddle-readiness pages", () => {
  test("English legal pages publish unique content, metadata, and footer links", async ({ page }) => {
    await stabilizePublicPage(page);

    for (const legalPage of englishPages) {
      await page.goto(legalPage.path);
      await expect(page.locator("html")).toHaveAttribute("lang", "en");
      await expect(page.getByRole("heading", { level: 1 })).toHaveText(legalPage.heading);
      await expect(page).toHaveTitle(legalPage.title);
      await expect(page.locator('link[rel="canonical"]')).toHaveAttribute("href", `https://postpiloter.com${legalPage.path}`);
      await expect(page.locator('meta[name="description"]')).not.toHaveAttribute("content", "Legal page");
      await expect(page.getByTestId("public-footer").getByRole("link", { name: "Privacy Policy" })).toBeVisible();
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    }
  });

  test("Turkish rendering, contact channels, and sitemap alternates are complete", async ({ page, request }) => {
    await stabilizePublicPage(page);
    await page.goto("/tr/privacy");

    await expect(page.locator("html")).toHaveAttribute("lang", "tr");
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("Gizlilik Politikası");
    await expect(page.getByText("Bu sayfada", { exact: true })).toBeVisible();
    await expect(page.getByRole("heading", { level: 2, name: "GDPR (AB) Kapsamında Değerlendirmeler" })).toBeVisible();
    await expect(page.locator('link[rel="canonical"]')).toHaveAttribute("href", "https://postpiloter.com/tr/privacy");

    await page.goto("/contact");
    for (const email of ["support@postpiloter.com", "legal@postpiloter.com", "sales@postpiloter.com"]) {
      await expect(page.getByRole("link", { name: email, exact: true }).first()).toHaveAttribute("href", `mailto:${email}`);
    }

    const sitemap = await request.get("/sitemap.xml");
    expect(sitemap.ok()).toBe(true);
    const xml = await sitemap.text();
    for (const legalPage of englishPages) {
      expect(xml).toContain(`https://postpiloter.com${legalPage.path}`);
      expect(xml).toContain(`https://postpiloter.com/tr${legalPage.path}`);
    }
  });
});
