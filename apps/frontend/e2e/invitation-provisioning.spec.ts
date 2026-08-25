import { expect, test, type Page } from "@playwright/test";

const future = "2030-01-01T12:00:00Z";
const now = "2026-08-25T12:00:00Z";

function preview(overrides: Record<string, unknown> = {}) {
  return {
    agency_name: "TEST Northstar Agency",
    brand_name: "TEST Atlas Brand",
    invitation_type: "brand",
    email: "test.brand@example.com",
    role: "brand_owner",
    expires_at: future,
    state: "pending",
    account_exists: false,
    account_type_compatible: null,
    ...overrides,
  };
}

function authUser(email: string, userType: "agency_user" | "brand_user") {
  return {
    id: "10000000-0000-0000-0000-000000000001",
    email,
    full_name: "TEST User",
    job_title: null,
    avatar_url: null,
    user_type: userType,
    is_active: true,
    is_verified: true,
    mfa_enabled: false,
    phone_number: null,
    whatsapp_opt_in: false,
    locale: "en",
    last_login_at: null,
    created_at: now,
    updated_at: now,
  };
}

async function mockInvitation(page: Page, invitation: Record<string, unknown>, loggedIn?: ReturnType<typeof authUser>) {
  let signupComplete = false;
  await page.route("**/api/v1/invitations/preview/**", (route) => route.fulfill({ json: invitation }));
  await page.route("**/api/v1/invitations/signup/**", async (route) => {
    signupComplete = true;
    await route.fulfill({ status: 201, json: { access_token: "signup-token", token_type: "bearer", expires_in: 900, redirect_to: invitation.invitation_type === "brand" ? "/brand/dashboard" : "/dashboard" } });
  });
  await page.route("**/api/v1/auth/refresh", (route) => {
    if (loggedIn || signupComplete) return route.fulfill({ json: { access_token: "access-token", token_type: "bearer", expires_in: 900 } });
    return route.fulfill({ status: 401, json: { detail: "No session" } });
  });
  await page.route("**/api/v1/auth/me", (route) => route.fulfill({ json: loggedIn ?? authUser(String(invitation.email), invitation.invitation_type === "brand" ? "brand_user" : "agency_user") }));
}

test.describe("invitation-aware onboarding", () => {
  test("new Brand recipient sees locked email, signs up, and reaches Brand dashboard", async ({ page }) => {
    await mockInvitation(page, preview());
    await page.route("**/brand/dashboard", (route) => route.fulfill({ contentType: "text/html", body: "<h1>TEST Brand Dashboard</h1>" }));
    await page.goto("/invite/test-brand-token");
    await expect(page.getByLabel("Email")).toHaveValue("test.brand@example.com");
    await expect(page.getByLabel("Email")).toHaveAttribute("readonly", "");
    await page.getByLabel("Full Name").fill("TEST Brand Recipient");
    await page.getByLabel("Password", { exact: true }).fill("StrongPass123!");
    await page.getByLabel("Confirm Password").fill("StrongPass123!");
    await page.getByRole("button", { name: "Create My Account & Accept Invitation" }).click();
    await expect(page.getByRole("heading", { name: "Invitation accepted" })).toBeVisible();
    await page.waitForURL("**/brand/dashboard", { timeout: 5_000 });
  });

  test("new Agency recipient joins the invited workspace and reaches Agency dashboard", async ({ page }) => {
    await mockInvitation(page, preview({ invitation_type: "agency", brand_name: null, email: "test.agency@example.com", role: "designer" }));
    await page.route("**/dashboard", (route) => route.fulfill({ contentType: "text/html", body: "<h1>TEST Agency Dashboard</h1>" }));
    await page.goto("/invite/test-agency-token");
    await page.getByLabel("Full Name").fill("TEST Agency Recipient");
    await page.getByLabel("Password", { exact: true }).fill("StrongPass123!");
    await page.getByLabel("Confirm Password").fill("StrongPass123!");
    await page.getByRole("button", { name: "Create My Account & Accept Invitation" }).click();
    await page.waitForURL("**/dashboard", { timeout: 5_000 });
  });

  test("existing recipient logs in, returns to the invitation, accepts it, and reaches Brand dashboard", async ({ page }) => {
    await mockInvitation(page, preview({ account_exists: true, account_type_compatible: true }));
    await page.route("**/api/v1/auth/login", (route) => {
      if (route.request().method() !== "POST") return route.fallback();
      return route.fulfill({ json: { access_token: "login-token", token_type: "bearer", expires_in: 900 } });
    });
    await page.route("**/api/v1/invitations/accept/**", (route) => route.fulfill({ status: 204 }));
    await page.route("**/brand/dashboard", (route) => route.fulfill({ contentType: "text/html", body: "<h1>TEST Brand Dashboard</h1>" }));
    await page.goto("/invite/existing-token");
    await page.getByRole("button", { name: "Log In & Accept Invitation" }).click();
    await expect(page).toHaveURL(/\/auth\/login\?redirect=%2Finvite%2Fexisting-token/);
    await page.getByRole("button", { name: "Brand portal" }).click();
    await page.getByLabel("Email address").fill("test.brand@example.com");
    await page.getByLabel("Password").fill("StrongPass123!");
    await page.getByRole("button", { name: "Log in" }).click();
    await expect(page).toHaveURL(/\/invite\/existing-token/);
    await page.getByRole("button", { name: "Accept invitation" }).click();
    await page.waitForURL("**/brand/dashboard", { timeout: 5_000 });
  });

  test("wrong logged-in account cannot accept the invitation", async ({ page }) => {
    await mockInvitation(page, preview({ account_exists: true, account_type_compatible: true }), authUser("another@example.com", "brand_user"));
    let acceptCalls = 0;
    await page.route("**/api/v1/invitations/accept/**", (route) => { acceptCalls += 1; return route.fulfill({ status: 204 }); });
    await page.goto("/invite/wrong-account-token");
    await expect(page.getByRole("alert").filter({ hasText: "Use the invited account" })).toContainText("test.brand@example.com");
    await expect(page.getByRole("button", { name: "Log Out & Use the Correct Account" })).toBeVisible();
    expect(acceptCalls).toBe(0);
  });

  for (const state of ["expired", "revoked"] as const) {
    test(`${state} invitation renders a dedicated terminal state`, async ({ page }) => {
      await mockInvitation(page, preview({ state, account_exists: null, account_type_compatible: null }));
      await page.goto(`/invite/${state}-token`);
      await expect(page.getByRole("heading", { name: state === "expired" ? "Invitation expired" : "Invitation cancelled" })).toBeVisible();
    });
  }
});

const agency = {
  id: "20000000-0000-0000-0000-000000000001",
  name: "TEST Existing Agency",
  slug: "test-existing-agency",
  status: "active",
  owner_user_id: null,
  plan_id: "30000000-0000-0000-0000-000000000001",
  member_count: 1,
  brand_count: 0,
  created_at: now,
  updated_at: now,
};

const plan = {
  id: "30000000-0000-0000-0000-000000000001",
  code: "test-manual",
  name: "TEST Manual Plan",
  description: null,
  monthly_price_cents: 9900,
  yearly_price_cents: null,
  currency: "USD",
  max_brands: 10,
  max_users: 10,
  max_brief_templates: 10,
  max_storage_gb: 10,
  white_label_enabled: false,
  advanced_reporting_enabled: false,
  pdf_export_enabled: false,
  public_report_link_enabled: false,
  whatsapp_infrastructure_enabled: false,
  is_active: true,
};

async function mockPlatform(page: Page) {
  await page.route("**/api/v1/platform/auth/refresh", (route) => route.fulfill({ json: { access_token: "platform-token", expires_in: 300 } }));
  await page.route("**/api/v1/platform/agencies?**", (route) => route.fulfill({ json: [agency] }));
  await page.route("**/api/v1/platform/brands?**", (route) => route.fulfill({ json: [] }));
  await page.route("**/api/v1/platform/plans", (route) => route.fulfill({ json: [plan] }));
  await page.route("**/api/v1/platform/agencies", async (route) => {
    if (route.request().method() !== "POST") return route.fallback();
    const body = route.request().postDataJSON();
    await route.fulfill({ status: 201, json: { agency: { ...agency, id: "20000000-0000-0000-0000-000000000002", name: body.name, slug: "test-created-agency" }, owner_action: "invited", owner_email: body.owner_email } });
  });
  await page.route("**/api/v1/platform/brands", async (route) => {
    if (route.request().method() !== "POST") return route.fallback();
    const body = route.request().postDataJSON();
    await route.fulfill({ status: 201, json: { brand: { id: "40000000-0000-0000-0000-000000000001", name: body.name, slug: "test-created-brand", status: body.status, agency_id: agency.id, agency_name: agency.name, member_count: 0, brief_count: 0, created_at: now, updated_at: now }, contact_action: "invited", contact_email: body.contact_email } });
  });
  await page.route("**/api/v1/platform/agencies/*", (route) => route.fulfill({ json: { ...agency, subscription_status: "active", plan_name: plan.name, plan_code: plan.code, monthly_price_cents: plan.monthly_price_cents } }));
  await page.route("**/api/v1/platform/agencies/*/members", (route) => route.fulfill({ json: [] }));
  await page.route("**/api/v1/platform/agencies/*/invitations", (route) => route.fulfill({ json: [] }));
  await page.route("**/api/v1/platform/brands/*/members", (route) => route.fulfill({ json: [] }));
}

test.describe("platform provisioning UI", () => {
  test("creates an Agency through the guided owner-invite flow", async ({ page }) => {
    await mockPlatform(page);
    await page.goto("/platform/agencies");
    await page.getByTestId("new-tenant-button").click();
    await page.getByTestId("agency-name").fill("TEST Created Agency");
    await page.getByTestId("provisioning-next").click();
    await page.getByLabel("Owner email").fill("test.owner@example.com");
    await page.getByTestId("provisioning-next").click();
    await page.getByTestId("provisioning-next").click();
    await page.getByTestId("provisioning-next").click();
    await expect(page.getByRole("heading", { name: "TEST Created Agency" })).toBeVisible();
  });

  test("creates a Brand with searchable parent Agency on a mobile viewport", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await mockPlatform(page);
    await page.goto("/platform/agencies");
    await page.getByTestId("platform-tab-brands").click();
    await page.getByTestId("new-tenant-button").click();
    await page.getByLabel("Search agencies…").fill("Existing");
    await expect(page.getByTestId("brand-agency")).toHaveValue(agency.id);
    await page.getByTestId("brand-name").fill("TEST Created Brand");
    await page.getByTestId("provisioning-next").click();
    await page.getByLabel("Contact email").fill("test.contact@example.com");
    await page.getByTestId("provisioning-next").click();
    await page.getByTestId("provisioning-next").click();
    await expect(page.getByRole("heading", { name: "TEST Created Brand" })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  });
});
