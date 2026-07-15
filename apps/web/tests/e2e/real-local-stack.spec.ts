import { expect, test } from "@playwright/test";

test("logs in and creates a request through the real local API", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "Sign in", exact: true })).toBeVisible();
  await page.getByLabel("Username").fill("user@example.test");
  await page.getByRole("textbox", { name: "Password" }).fill("CoeusLocal1!");
  await page.getByRole("button", { name: "Sign in to Istari" }).click();

  await expect(page.getByRole("heading", { name: "My Requests", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Open new request" }).click();
  await page.getByLabel("Message").fill("Need a synthetic Baltic port activity briefing.");
  await page.getByRole("button", { name: "Send" }).click();

  await expect(page.getByText("TCK-0001")).toBeVisible();
  await expect(
    page
      .getByLabel("Conversation with Istari")
      .getByText("Need a synthetic Baltic port activity briefing."),
  ).toBeVisible();
});
