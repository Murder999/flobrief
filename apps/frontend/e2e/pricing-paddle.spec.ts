import { expect, test, type Page } from "@playwright/test";

const commercialPlans = [
  { code: "brand_solo", name: "Brand Solo", monthly: "$19.00", yearly: "$182.40" },
  { code: "starter_agency", name: "Starter Agency", monthly: "$49.00", yearly: "$470.40" },
  { code: "pro_agency", name: "Pro Agency", monthly: "$99.00", yearly: "$950.40" },
  { code: "agency_plus", name: "Agency Plus", monthly: "$199.00", yearly: "$1,910.40" },
] as const;

const plans = [
  ...commercialPlans.map((plan, index) => ({
    id: `00000000-0000-4000-8000-00000000000${index + 1}`,
    code: plan.code,
    name: plan.name,
    description: `${plan.name} plan`,
    monthly_price_cents: (index + 1) * 1000,
    yearly_price_cents: (index + 1) * 9600,
    currency: "USD",
    max_brands: index + 1,
    max_users: (index + 1) * 5,
    max_brief_templates: (index + 1) * 10,
    max_storage_gb: (index + 1) * 10,
    white_label_enabled: plan.code === "agency_plus",
    advanced_reporting_enabled: plan.code !== "brand_solo",
    pdf_export_enabled: true,
    public_report_link_enabled: plan.code !== "brand_solo",
    whatsapp_infrastructure_enabled: ["pro_agency", "agency_plus"].includes(plan.code),
    is_active: true,
  })),
  {
    id: "00000000-0000-4000-8000-000000000005",
    code: "enterprise",
    name: "Enterprise",
    description: "Enterprise plan",
    monthly_price_cents: 0,
    yearly_price_cents: 0,
    currency: "USD",
    max_brands: null,
    max_users: null,
    max_brief_templates: null,
    max_storage_gb: null,
    white_label_enabled: true,
    advanced_reporting_enabled: true,
    pdf_export_enabled: true,
    public_report_link_enabled: true,
    whatsapp_infrastructure_enabled: true,
    is_active: true,
  },
];

const fakePaddleScript = String.raw`
(() => {
  const prices = {
    pri_e2e_brand_solo_monthly: ["$19.00", "Brand Solo"],
    pri_e2e_brand_solo_yearly: ["$182.40", "Brand Solo"],
    pri_e2e_starter_agency_monthly: ["$49.00", "Starter Agency"],
    pri_e2e_starter_agency_yearly: ["$470.40", "Starter Agency"],
    pri_e2e_pro_agency_monthly: ["$99.00", "Pro Agency"],
    pri_e2e_pro_agency_yearly: ["$950.40", "Pro Agency"],
    pri_e2e_agency_plus_monthly: ["$199.00", "Agency Plus"],
    pri_e2e_agency_plus_yearly: ["$1,910.40", "Agency Plus"],
  };

  window.__paddleE2E = { environment: null, initializeCount: 0, previews: [], lastCheckout: null };
  window.PaddleBillingV1 = {
    Initialized: false,
    Environment: {
      set(environment) {
        window.__paddleE2E.environment = environment;
      },
    },
    Initialize() {
      this.Initialized = true;
      window.__paddleE2E.initializeCount += 1;
    },
    Update() {},
    async PricePreview({ items }) {
      window.__paddleE2E.previews.push(items.map((item) => item.priceId));
      if (window.__paddleE2E.failPreview) throw new Error("Synthetic provider failure");
      return {
        data: {
          customerId: null,
          addressId: null,
          businessId: null,
          currencyCode: "USD",
          address: null,
          customerIpAddress: null,
          discountId: null,
          details: {
            lineItems: items.map((item) => ({
              price: { id: item.priceId },
              formattedTotals: { subtotal: prices[item.priceId][0], discount: "$0.00", tax: "$0.00", total: prices[item.priceId][0] },
            })),
          },
          availablePaymentMethods: ["card"],
        },
        meta: { requestId: "e2e-price-preview" },
      };
    },
    Checkout: {
      open(options) {
        window.__paddleE2E.lastCheckout = options;
        const priceId = options.items[0].priceId;
        document.getElementById("paddle-e2e-checkout")?.remove();
        const overlay = document.createElement("div");
        overlay.id = "paddle-e2e-checkout";
        overlay.setAttribute("role", "dialog");
        overlay.setAttribute("aria-label", "Paddle checkout");
        overlay.innerHTML = '<p>' + prices[priceId][1] + '</p><p>' + prices[priceId][0] + '</p><button type="button">Close checkout</button>';
        overlay.querySelector("button").addEventListener("click", () => overlay.remove());
        document.body.appendChild(overlay);
      },
    },
  };
})();
`;

async function mockPublicApi(page: Page, authenticated = true) {
  await page.route("**/api/v1/**", (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/api/v1/plans") return route.fulfill({ status: 200, json: plans });
    if (path === "/api/v1/auth/refresh") {
      if (!authenticated) return route.fulfill({ status: 401, json: { detail: "Not authenticated" } });
      return route.fulfill({
        status: 200,
        json: { access_token: "pricing-e2e-token", token_type: "bearer", expires_in: 900 },
      });
    }
    if (path === "/api/v1/auth/me") {
      return route.fulfill({
        status: 200,
        json: {
          id: "00000000-0000-4000-8000-000000000099",
          email: "buyer@example.test",
          full_name: "Pricing Buyer",
          user_type: "agency_user",
          is_active: true,
          is_verified: true,
          mfa_enabled: false,
          phone_number: null,
          whatsapp_opt_in: false,
          locale: "en",
          last_login_at: null,
          created_at: "2026-08-24T00:00:00Z",
          updated_at: "2026-08-24T00:00:00Z",
        },
      });
    }
    if (path === "/api/v1/workspaces") {
      return route.fulfill({ status: 200, json: { agencies: [], brands: [] } });
    }
    if (path === "/api/v1/invitations/my-pending") {
      return route.fulfill({ status: 200, json: [] });
    }
    if (path === "/api/v1/public/branding/platform-defaults") {
      return route.fulfill({
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
          public_title: "PostPiloter",
          public_description: "Agency and brand operations platform.",
        },
      });
    }
    return route.fulfill({ status: 404, json: { detail: "Not used by pricing E2E" } });
  });
}

async function mockPaddle(page: Page, failPreview = false) {
  const script = failPreview
    ? fakePaddleScript.replace("lastCheckout: null", "lastCheckout: null, failPreview: true")
    : fakePaddleScript;
  await page.route("https://cdn.paddle.com/paddle/v2/paddle.js", (route) =>
    route.fulfill({ status: 200, contentType: "application/javascript", body: script })
  );
}

test.describe("pricing and Paddle regression", () => {
  test("homepage has no beta product-status marker in English or Turkish", async ({ page }) => {
    await mockPublicApi(page, false);
    await page.goto("/", { waitUntil: "domcontentloaded", timeout: 20_000 });
    await expect(page.getByText(/\bbeta\b/i)).toHaveCount(0);

    await page.getByRole("group", { name: "Language" }).getByRole("button", { name: "TR", exact: true }).click();
    await expect(page).toHaveURL(/\/tr\/?$/);
    await expect(page.getByText(/\bbeta\b/i)).toHaveCount(0);
  });

  test("EN shows four authoritative monthly/yearly prices and mapped checkout items", async ({ page }) => {
    await mockPublicApi(page);
    await mockPaddle(page);
    await page.goto("/pricing", { waitUntil: "domcontentloaded", timeout: 20_000 });

    for (const plan of commercialPlans) {
      const card = page.getByTestId(`pricing-card-${plan.code}`);
      await expect(card.getByText(plan.monthly, { exact: true })).toBeVisible();
      await expect(card.getByRole("button", { name: "Choose this plan", exact: true })).toBeEnabled();
    }
    await expect(page.getByTestId("pricing-card-enterprise").getByText("Custom pricing", { exact: true })).toBeVisible();
    await expect(page.getByText("Price temporarily unavailable", { exact: true })).toHaveCount(0);
    await expect(page.getByText("Checkout devre dışı", { exact: true })).toHaveCount(0);

    for (const plan of commercialPlans) {
      const card = page.getByTestId(`pricing-card-${plan.code}`);
      await card.getByRole("button", { name: "Choose this plan", exact: true }).click();
      const checkout = page.getByRole("dialog", { name: "Paddle checkout" });
      await expect(checkout.getByText(plan.name, { exact: true })).toBeVisible();
      const captured = await page.evaluate(() =>
        (window as typeof window & { __paddleE2E: { lastCheckout: { items: Array<{ priceId: string }>; customer: { email: string }; settings: { locale: string } } } }).__paddleE2E.lastCheckout
      );
      expect(captured.items[0].priceId).toBe(`pri_e2e_${plan.code}_monthly`);
      expect(captured.customer.email).toBe("buyer@example.test");
      expect(captured.settings.locale).toBe("en");
      await checkout.getByRole("button", { name: "Close checkout" }).click();
    }

    const monthlyPrices = await Promise.all(
      commercialPlans.map((plan) => page.getByTestId(`pricing-card-${plan.code}`).getByText(plan.monthly, { exact: true }).textContent())
    );
    await page.getByRole("button", { name: /^Yearly/ }).click();
    for (const plan of commercialPlans) {
      const card = page.getByTestId(`pricing-card-${plan.code}`);
      await expect(card).toHaveAttribute("data-billing-period", "yearly");
      await expect(card.getByText(plan.yearly, { exact: true })).toBeVisible();
      await expect(card.getByText("/year", { exact: true })).toBeVisible();
    }
    const yearlyPrices = await Promise.all(
      commercialPlans.map((plan) => page.getByTestId(`pricing-card-${plan.code}`).getByText(plan.yearly, { exact: true }).textContent())
    );
    expect(yearlyPrices).not.toEqual(monthlyPrices);

    const yearlyCard = page.getByTestId("pricing-card-brand_solo");
    await yearlyCard.getByRole("button", { name: "Choose this plan", exact: true }).click();
    const yearlyCheckout = await page.evaluate(() =>
      (window as typeof window & { __paddleE2E: { lastCheckout: { items: Array<{ priceId: string }> } } }).__paddleE2E.lastCheckout
    );
    expect(yearlyCheckout.items[0].priceId).toBe("pri_e2e_brand_solo_yearly");
    await page.getByRole("dialog", { name: "Paddle checkout" }).getByRole("button", { name: "Close checkout" }).click();

    const paddleState = await page.evaluate(() =>
      (window as typeof window & { __paddleE2E: { environment: string; initializeCount: number; previews: string[][] } }).__paddleE2E
    );
    expect(paddleState.environment).toBe("sandbox");
    expect(paddleState.initializeCount).toBe(1);
    expect(paddleState.previews.length).toBeGreaterThanOrEqual(8);
  });

  test("TR shows all four monthly and yearly prices", async ({ page }) => {
    await mockPublicApi(page, false);
    await mockPaddle(page);
    await page.goto("/tr/pricing", { waitUntil: "domcontentloaded", timeout: 20_000 });

    await expect(page.locator("html")).toHaveAttribute("lang", "tr");
    for (const plan of commercialPlans) {
      const card = page.getByTestId(`pricing-card-${plan.code}`);
      await expect(card.getByText(plan.monthly, { exact: true })).toBeVisible();
      await expect(card.getByRole("button", { name: "Bu planı seç", exact: true })).toBeEnabled();
    }
    await page.getByRole("button", { name: /^Yıllık/ }).first().click();
    for (const plan of commercialPlans) {
      const card = page.getByTestId(`pricing-card-${plan.code}`);
      await expect(card.getByText(plan.yearly, { exact: true })).toBeVisible();
      await expect(card.getByText("/yıl", { exact: true })).toBeVisible();
    }
    await expect(page.getByText("Fiyat şu anda yüklenemiyor", { exact: true })).toHaveCount(0);
    await expect(page.getByText("Checkout devre dışı", { exact: true })).toHaveCount(0);
  });

  test("PricePreview failure reaches a clean retry state and recovers", async ({ page }) => {
    await mockPublicApi(page, false);
    await mockPaddle(page, true);
    await page.goto("/pricing", { waitUntil: "domcontentloaded", timeout: 20_000 });

    await expect(page.getByText("Price information could not be loaded.", { exact: true })).toHaveCount(4);
    await expect(page.getByRole("button", { name: "Try again", exact: true })).toHaveCount(4);
    await expect(page.getByText("Checkout devre dışı", { exact: true })).toHaveCount(0);

    await page.evaluate(() => {
      (window as typeof window & { __paddleE2E: { failPreview?: boolean } }).__paddleE2E.failPreview = false;
    });
    for (const plan of commercialPlans) {
      await page
        .getByTestId(`pricing-card-${plan.code}`)
        .getByRole("button", { name: "Try again", exact: true })
        .click();
    }
    for (const plan of commercialPlans) {
      await expect(page.getByTestId(`pricing-card-${plan.code}`).getByText(plan.monthly, { exact: true })).toBeVisible();
    }
  });
});

test("live Paddle prices and four monthly plus one yearly checkout overlays", async ({ page }) => {
  test.skip(process.env.RUN_LIVE_PADDLE_E2E !== "1", "Requires real Paddle public config at frontend build time");
  const paddleDiagnostics: string[] = [];
  const redact = (value: string) => value
    .replace(/\b(?:live|test)_[A-Za-z0-9_-]+\b/g, "[client-token-redacted]")
    .replace(/\bpri_[A-Za-z0-9_-]+\b/g, "[price-id-redacted]");
  page.on("console", (message) => {
    if (["error", "warning"].includes(message.type()) && /paddle/i.test(message.text())) {
      paddleDiagnostics.push(`console ${message.type()}: ${redact(message.text())}`);
    }
  });
  page.on("requestfailed", (request) => {
    if (/paddle/i.test(request.url())) {
      const url = new URL(request.url());
      paddleDiagnostics.push(`request failed: ${url.origin}${url.pathname} ${request.failure()?.errorText ?? "unknown"}`);
    }
  });
  page.on("response", async (response) => {
    if (/paddle/i.test(response.url()) && !response.ok()) {
      const url = new URL(response.url());
      let detail = "";
      try {
        detail = redact((await response.text()).slice(0, 800));
      } catch {
        detail = "response body unavailable";
      }
      paddleDiagnostics.push(`response ${response.status()}: ${url.origin}${url.pathname} ${detail}`);
    }
  });
  await mockPublicApi(page);

  for (const plan of commercialPlans) {
    await page.goto("/pricing", { waitUntil: "domcontentloaded", timeout: 20_000 });
    const card = page.getByTestId(`pricing-card-${plan.code}`);
    await expect(card.getByRole("button", { name: "Choose this plan", exact: true })).toBeEnabled();
    await card.getByRole("button", { name: "Choose this plan", exact: true }).click();
    await expect(page.locator('iframe[src*="paddle.com"]:visible').first()).toBeVisible({ timeout: 30_000 });
  }

  await page.goto("/pricing", { waitUntil: "domcontentloaded", timeout: 20_000 });
  await page.getByRole("button", { name: /^Yearly/ }).click();
  const validYearlyCard = page.getByTestId("pricing-card-starter_agency");
  await expect(validYearlyCard).toHaveAttribute("data-billing-period", "yearly");
  await expect(validYearlyCard.getByRole("button", { name: "Choose this plan", exact: true })).toBeEnabled();
  await validYearlyCard.getByRole("button", { name: "Choose this plan", exact: true }).click();
  await expect(page.locator('iframe[src*="paddle.com"]:visible').first()).toBeVisible({ timeout: 30_000 });

  await page.goto("/pricing", { waitUntil: "domcontentloaded", timeout: 20_000 });
  await page.getByRole("button", { name: /^Yearly/ }).click();
  const yearlyCard = page.getByTestId("pricing-card-brand_solo");
  await expect(yearlyCard).toHaveAttribute("data-billing-period", "yearly");
  if (await yearlyCard.getByRole("button", { name: "Choose this plan", exact: true }).isDisabled()) {
    await page.waitForTimeout(1_000);
    console.log(`PADDLE LIVE DIAGNOSTICS:\n${paddleDiagnostics.join("\n")}`);
  }
  await expect(yearlyCard.getByRole("button", { name: "Choose this plan", exact: true })).toBeEnabled();
});
