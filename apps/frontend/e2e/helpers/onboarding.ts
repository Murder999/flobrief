import type { Page } from "@playwright/test";

/**
 * Closes the OnboardingWizard welcome modal if it happens to be visible
 * (fresh fixture user, first page load after login) so specs that are not
 * testing onboarding itself never race its overlay. No-ops silently if the
 * modal never appears — most fixtures now seed onboarding as dismissed via
 * the real dismiss endpoint (see e2e_seed_mention_onboarding_*.py), so this
 * is a defensive fallback, not the primary mechanism.
 *
 * Do not use this in onboarding-flow.spec.ts — that spec asserts on the
 * welcome modal's own real behavior.
 */
export async function dismissOnboardingIfVisible(page: Page): Promise<void> {
  const laterButton = page.getByRole("button", { name: "Daha Sonra" });
  const appeared = await laterButton
    .waitFor({ state: "visible", timeout: 2_000 })
    .then(() => true)
    .catch(() => false);
  if (!appeared) return;
  await laterButton.click();
  await laterButton.waitFor({ state: "hidden", timeout: 5_000 }).catch(() => {});
}
