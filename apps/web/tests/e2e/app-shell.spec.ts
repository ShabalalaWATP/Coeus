import { expect, test } from "@playwright/test";

const API = "http://127.0.0.1:8021/api/v1";

test("loads the authenticated app shell", async ({ page }) => {
  await page.route(`${API}/**`, async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname.replace("/api/v1", "");

    if (request.method() === "GET" && path === "/auth/me") {
      return route.fulfill({
        contentType: "application/json",
        json: {
          csrfToken: "csrf-e2e",
          user: {
            defaultRoute: "/app/requests",
            displayName: "Admin Operator",
            id: "e2e-user",
            permissions: [
              "ticket:read_own",
              "chat:use",
              "product:read",
              "product:search",
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
            roles: ["Administrator"],
            username: "admin@example.test",
          },
        },
      });
    }
    if (request.method() === "GET" && path === "/tickets") {
      return route.fulfill({ contentType: "application/json", json: { tickets: [] } });
    }
    if (request.method() === "GET" && path === "/notifications") {
      return route.fulfill({
        contentType: "application/json",
        json: { notifications: [], unread: 0 },
      });
    }
    if (request.method() === "GET" && path === "/feedback/requests") {
      return route.fulfill({ contentType: "application/json", json: { requests: [] } });
    }
    return route.fulfill({ contentType: "application/json", json: {} });
  });
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "My Requests", exact: true })).toBeVisible();
  await expect(page.getByLabel("Primary navigation")).toContainText("Intelligence Store");
  await expect(page.getByLabel("Primary navigation")).toContainText("ACGs");
  await expect(page.getByRole("button", { name: "Notifications" })).toBeVisible();
});
