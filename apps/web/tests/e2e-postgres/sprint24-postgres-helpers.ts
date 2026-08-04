import { expect, type Page } from "@playwright/test";

const API_BASE_URL = "http://127.0.0.1:8022";
const PASSWORD = "CoeusLocal1!";

export async function login(page: Page, username: string, heading: string) {
  await page.goto("/");
  await page.getByLabel("Username").fill(username);
  await page.getByRole("textbox", { name: "Password" }).fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in to Istari" }).click();
  await expect(page.getByRole("heading", { name: heading, exact: true })).toBeVisible();
}

export async function logout(page: Page) {
  await page.getByRole("button", { name: "Log out" }).click();
  await expect(page.getByRole("heading", { name: "Sign in", exact: true })).toBeVisible();
}

export async function ensureSyntheticOrganisation(page: Page) {
  await login(page, "admin@example.test", "Admin");
  await page.goto("/admin/organisation");
  await expect(page.getByRole("heading", { name: "Organisation", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Exercise data" }).click();
  await page.getByRole("button", { name: "Check exercise data" }).click();
  const ready = page.getByRole("heading", { name: "Ready to build" });
  const current = page.getByText("Exercise organisation is up to date.");
  await expect(ready.or(current)).toBeVisible({ timeout: 30_000 });
  if (await ready.isVisible()) {
    await page.getByLabel("Current password").fill(PASSWORD);
    await page.getByRole("button", { name: "Build exercise organisation" }).click();
    await expect(current).toBeVisible({ timeout: 60_000 });
  }
  await logout(page);
}

export async function fetchStatus(
  page: Page,
  path: string,
): Promise<{ body: unknown; method: string; status: number }> {
  return page.evaluate(
    async ({ apiBaseUrl, requestPath }) => {
      const response = await fetch(`${apiBaseUrl}${requestPath}`, { credentials: "include" });
      const text = await response.text();
      return {
        body: text ? (JSON.parse(text) as unknown) : null,
        method: "GET",
        status: response.status,
      };
    },
    { apiBaseUrl: API_BASE_URL, requestPath: path },
  );
}
