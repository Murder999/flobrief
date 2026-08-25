import { expect, test, type Page, type Route } from "@playwright/test";

const AGENCY_ID = "00000000-0000-4000-8000-000000000001";
const BRAND_ID = "00000000-0000-4000-8000-000000000002";

const platformBranding = {
  portal_name: "PostPiloter",
  primary_color: "#4F46E5",
  secondary_color: "#7C3AED",
  accent_color: "#6366F1",
  background_color: "#FAF9F7",
  surface_color: "#FFFFFF",
  text_color: "#1A1917",
  border_color: "#E5E2DC",
  logo_url: null,
  logo_dark_url: null,
  favicon_url: null,
  og_image_url: null,
  support_email: "support@postpiloter.com",
  support_phone: null,
  website_url: "https://postpiloter.com",
  footer_company_name: "PostPiloter",
  copyright_text: "PostPiloter. All rights reserved.",
  footer_text: null,
  public_title: "PostPiloter",
  public_description: "Agency and brand operations platform.",
};

async function fulfillApi(route: Route, userType: "agency_user" | "brand_user" | null) {
  const path = new URL(route.request().url()).pathname;
  if (path === "/api/v1/auth/refresh") {
    if (!userType) return route.fulfill({ status: 401, json: { detail: "Not authenticated" } });
    return route.fulfill({ json: { access_token: "e2e-help-token", token_type: "bearer", expires_in: 900 } });
  }
  if (path === "/api/v1/auth/me" && userType) {
    return route.fulfill({
      json: {
        id: userType === "agency_user" ? AGENCY_ID : BRAND_ID,
        email: `${userType}@example.test`,
        full_name: userType === "agency_user" ? "E2E Ajans" : "E2E Marka",
        job_title: null,
        avatar_url: null,
        user_type: userType,
        is_active: true,
        is_verified: true,
        mfa_enabled: false,
        phone_number: null,
        whatsapp_opt_in: false,
        locale: "tr",
        last_login_at: null,
        created_at: "2026-08-24T00:00:00Z",
        updated_at: "2026-08-24T00:00:00Z",
      },
    });
  }
  if (path === "/api/v1/public/branding/platform-defaults") {
    return route.fulfill({ json: platformBranding });
  }
  if (path === "/api/v1/workspaces") {
    return route.fulfill({
      json: {
        agencies: [{ id: AGENCY_ID, name: "E2E Ajans", slug: "e2e-ajans", member_role: "owner" }],
        brands: [],
      },
    });
  }
  if (path === "/api/v1/invitations/my-pending") return route.fulfill({ json: [] });
  if (path === "/api/v1/brand-portal/me") {
    return route.fulfill({
      json: {
        user_id: BRAND_ID,
        email: "brand_user@example.test",
        full_name: "E2E Marka",
        user_type: "brand_user",
        brand_id: BRAND_ID,
        brand_name: "E2E Marka",
        brand_slug: "e2e-marka",
        brand_status: "active",
        membership_role: "brand_owner",
      },
    });
  }
  if (path === "/api/v1/brand-portal/branding") {
    return route.fulfill({
      json: {
        brand_name: "E2E Marka",
        is_branded: false,
        primary_color: "#4F46E5",
        secondary_color: "#7C3AED",
        accent_color: "#6366F1",
        background_color: "#FAF9F7",
        surface_color: "#FFFFFF",
        text_color: "#1A1917",
        border_color: "#E5E2DC",
        logo_url: null,
        dark_logo_url: null,
        favicon_url: null,
        support_email: "support@postpiloter.com",
        support_phone: null,
        website_url: "https://postpiloter.com",
        footer_company_name: "PostPiloter",
        copyright_text: "PostPiloter",
        custom_footer_text: null,
        seo_title: "PostPiloter",
        seo_description: "Brand portal",
      },
    });
  }
  if (path === "/api/v1/plans") return route.fulfill({ json: [] });
  if (path === "/api/v1/demo/status") {
    return route.fulfill({
      json: {
        enabled: true,
        available: false,
        unavailable_reason: "Demo is unavailable during this test.",
        duration_hours: 2,
        captcha_required: false,
        captcha_site_key: null,
      },
    });
  }
  return route.fulfill({ status: 404, json: { detail: "Not needed by this acceptance test" } });
}

async function mockApi(page: Page, userType: "agency_user" | "brand_user" | null = null) {
  await page.route("**/api/v1/**", (route) => fulfillApi(route, userType));
}

async function expectNoHorizontalOverflow(page: Page) {
  const [scrollWidth, clientWidth] = await page.evaluate(() => [
    document.documentElement.scrollWidth,
    document.documentElement.clientWidth,
  ]);
  expect(scrollWidth).toBeLessThanOrEqual(clientWidth + 1);
}

test.describe("Help Center final UX", () => {
  test("brand help supports search, categories, articles, FAQ, quick actions, and deep links", async ({ page }) => {
    await mockApi(page, "brand_user");
    await page.goto("/brand/help?topic=approval");

    const help = page.getByTestId("brand-help-center");
    await expect(help.getByRole("heading", { level: 1, name: "Yardım Merkezi" })).toBeVisible();
    await expect(help.getByRole("searchbox", { name: "Yardım Merkezi'nde ara" })).toBeVisible();
    await expect(help.getByTestId("help-categories")).toBeVisible();
    await expect(help.getByTestId("help-quick-actions")).toBeVisible();
    await expect(help.getByRole("heading", { level: 2, name: "Onay Verme" })).toBeVisible();

    await help.getByTestId("help-categories").getByRole("button", { name: "Briefler", exact: true }).click();
    await expect(help.getByRole("heading", { level: 2, name: "Brief Verme" })).toBeVisible();

    const quickAction = help.getByTestId("help-quick-actions").getByRole("link", { name: /Onayları Gör/ });
    await expect(quickAction).toHaveAttribute("href", "/brand/approvals");
    await quickAction.click();
    await expect(page).toHaveURL(/\/brand\/approvals$/);

    await page.goto("/brand/help");
    const search = page.getByRole("searchbox", { name: "Yardım Merkezi'nde ara" });
    await search.fill("WhatsApp");
    const results = page.getByTestId("help-search-results");
    await expect(results.getByText("WhatsApp Bildirimleri", { exact: true })).toBeVisible();
    await results.getByText("WhatsApp Bildirimleri", { exact: true }).click();
    await expect(page.getByRole("heading", { level: 2, name: "WhatsApp Bildirimleri" })).toBeVisible();
    const faq = page.getByText("WhatsApp bildirimi neden gelmiyor?", { exact: true });
    await faq.click();
    await expect(page.getByText(/Telefon ve izin bilgilerinizin tanımlı/)).toBeVisible();

    await search.fill("sonucu-olmayan-ifade-xyz");
    await expect(page.getByTestId("help-empty-state")).toBeVisible();
  });

  test("agency help supports search, categories, articles, FAQ, quick actions, and deep links", async ({ page }) => {
    await mockApi(page, "agency_user");
    await page.goto("/dashboard/help?topic=template-use");

    const help = page.getByTestId("agency-help-center");
    await expect(help.getByRole("heading", { level: 1, name: "Yardım Merkezi" })).toBeVisible();
    await expect(help.getByRole("searchbox", { name: "Yardım Merkezi'nde ara" })).toBeVisible();
    await expect(help.getByTestId("help-categories")).toBeVisible();
    await expect(help.getByTestId("help-quick-actions")).toBeVisible();
    await expect(help.getByRole("heading", { level: 2, name: "Şablonu Kullanma" })).toBeVisible();

    await help.getByTestId("help-categories").getByRole("button", { name: "Briefler", exact: true }).click();
    await expect(help.getByRole("heading", { level: 2, name: "Yeni Brief Oluştur" })).toBeVisible();

    const quickAction = help.getByTestId("help-quick-actions").getByRole("link", { name: /Rapor Oluştur/ });
    await expect(quickAction).toHaveAttribute("href", "/dashboard/reports/new");
    await quickAction.click();
    await expect(page).toHaveURL(/\/dashboard\/reports\/new$/);

    await page.goto("/dashboard/help");
    const search = page.getByRole("searchbox", { name: "Yardım Merkezi'nde ara" });
    await search.fill("kapasite");
    const results = page.getByTestId("help-search-results");
    await expect(results.getByText("Kapasite", { exact: true })).toBeVisible();
    await results.getByText("Kapasite", { exact: true }).click();
    await expect(page.getByRole("heading", { level: 2, name: "Kapasite" })).toBeVisible();
    await page.getByText("Atamaları kim değiştirebilir?", { exact: true }).click();
    await expect(page.getByText(/gerekli ajans izinlerine sahip/)).toBeVisible();
  });

  test("help remains usable without overflow on mobile", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await mockApi(page, "brand_user");
    await page.goto("/brand/help?topic=brief-create");

    await expect(page.getByRole("searchbox", { name: "Yardım Merkezi'nde ara" })).toBeVisible();
    await expect(page.locator("#brand-help-category")).toBeVisible();
    await expect(page.getByTestId("help-article")).toBeVisible();
    await expectNoHorizontalOverflow(page);
  });
});

test.describe("Public footer visibility", () => {
  const publicPaths = ["/", "/pricing", "/demo", "/terms", "/privacy", "/refund-policy", "/contact"] as const;
  const legalLinks = [
    ["Terms of Service", "/terms"],
    ["Privacy Policy", "/privacy"],
    ["Refund Policy", "/refund-policy"],
    ["Contact", "/contact"],
  ] as const;
  const turkishLegalLinks = [
    ["Kullanım Koşulları", "/tr/terms"],
    ["Gizlilik Politikası", "/tr/privacy"],
    ["İade Politikası", "/tr/refund-policy"],
    ["İletişim", "/tr/contact"],
  ] as const;

  test("LEGAL and all four links are visible on every English public page", async ({ page }) => {
    await mockApi(page);
    for (const path of publicPaths) {
      await page.goto(path);
      const footer = page.getByTestId("public-footer");
      await expect(footer).toBeVisible();
      await expect(footer.getByRole("heading", { name: "LEGAL", exact: true })).toBeVisible();
      for (const [label, href] of legalLinks) {
        const link = footer.getByRole("link", { name: label, exact: true });
        await expect(link).toBeVisible();
        await expect(link).toHaveAttribute("href", href);
      }
    }
  });

  test("YASAL and all four links are visible on every Turkish public page", async ({ page }) => {
    await mockApi(page);
    for (const path of publicPaths) {
      const localizedPath = path === "/" ? "/tr" : `/tr${path}`;
      await page.goto(localizedPath);
      const footer = page.getByTestId("public-footer");
      await expect(footer).toBeVisible();
      await expect(footer.getByRole("heading", { name: "YASAL", exact: true })).toBeVisible();
      for (const [label, href] of turkishLegalLinks) {
        const link = footer.getByRole("link", { name: label, exact: true });
        await expect(link).toBeVisible();
        await expect(link).toHaveAttribute("href", href);
      }
    }
  });

  test("five-column footer remains visible and contained on mobile", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await mockApi(page);
    for (const path of ["/", "/pricing", "/demo", "/tr/privacy"]) {
      await page.goto(path);
      const footer = page.getByTestId("public-footer");
      await expect(footer).toBeVisible();
      await expect(footer.getByRole("heading", { name: /LEGAL|YASAL/ })).toBeVisible();
      await expectNoHorizontalOverflow(page);
    }
  });
});
