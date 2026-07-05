import { expect, test } from "@playwright/test";

test("loads the authenticated app shell", async ({ page }) => {
  await page.route("http://127.0.0.1:8001/api/v1/auth/me", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      json: {
        csrfToken: "csrf-e2e",
        user: {
          id: "e2e-user",
          username: "admin@example.test",
          displayName: "Admin Operator",
          roles: ["Administrator"],
          permissions: [
            "ticket:read_own",
            "product:read",
            "product:search",
            "project:read",
            "acg:view",
            "rfa:review",
            "rfa:add_product",
            "collection:review",
            "collection:add_product",
            "analyst:work",
            "qc:review",
            "system:configure",
            "audit:read",
          ],
          defaultRoute: "/app/requests",
        },
      },
    });
  });
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "Requests" })).toBeVisible();
  await expect(page.getByLabel("Primary navigation")).toContainText("Intelligence Store");
  await expect(page.getByLabel("Primary navigation")).toContainText("Projects");
  await expect(page.getByLabel("Primary navigation")).toContainText("ACGs");
  await expect(page.getByRole("button", { name: "Notifications" })).toBeVisible();
});
