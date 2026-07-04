import { expect, test } from "@playwright/test";

test("loads the sprint one app shell", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "Requests" })).toBeVisible();
  await expect(page.getByLabel("Primary navigation")).toContainText("Intelligence Store");
  await expect(page.getByRole("button", { name: "Notifications" })).toBeVisible();
});
