import { groupedNavigationItems, visibleNavigationItems, type UserProfile } from "./route-access";
import { previewProfile } from "../../test/test-utils";

test("preview profile can see every sprint shell route", () => {
  expect(visibleNavigationItems(previewProfile).map((item) => item.label)).toEqual(
    expect.arrayContaining(["Requests", "Intelligence Store", "Admin", "Audit"]),
  );
});

test("route access requires all route permissions", () => {
  const profile: UserProfile = {
    id: "customer",
    username: "customer@example.test",
    displayName: "Customer",
    roles: ["User"],
    defaultRoute: "/app/requests",
    passwordResetRequired: false,
    permissions: ["ticket:read_own"],
  };

  expect(visibleNavigationItems(profile).map((item) => item.label)).toEqual(["Requests"]);
});

test("store manager sees store administration surfaces without admin overview", () => {
  const profile: UserProfile = {
    id: "store-manager",
    username: "store.manager@example.test",
    displayName: "Intelligence Store Manager",
    roles: ["Intelligence Store Manager"],
    defaultRoute: "/store",
    passwordResetRequired: false,
    permissions: [
      "acg:view",
      "acg:assign_user",
      "acg:assign_product",
      "product:create_existing",
      "product:read",
      "product:search",
    ],
  };

  expect(visibleNavigationItems(profile).map((item) => item.label)).toEqual([
    "Intelligence Store",
    "ACGs",
  ]);
});

test("my products is reachable from the navigation", () => {
  const profile: UserProfile = {
    ...previewProfile,
    roles: ["RFA Manager"],
    permissions: ["product:read", "product:search"],
  };

  expect(visibleNavigationItems(profile).map((item) => item.label)).toEqual([
    "Intelligence Store",
    "My Products",
  ]);
});

test("retired workspace feature is not exposed in navigation", () => {
  const labels = visibleNavigationItems(previewProfile).map((item) => item.label);

  expect(labels).not.toContain("Projects");
});

test("groups navigation items and omits empty groups", () => {
  const items = visibleNavigationItems(previewProfile);
  const operationsOnly = items.filter((item) => item.group === "operations");
  const groups = groupedNavigationItems(operationsOnly);

  expect(groups).toHaveLength(1);
  expect(groups[0].label).toBe("Operations");
  expect(groups[0].items.map((item) => item.label)).toContain("Requests");

  const allGroups = groupedNavigationItems(items);
  expect(allGroups.map((group) => group.label)).toEqual(["Operations", "Teams", "Governance"]);
});

test("route metadata includes active navigation paths", () => {
  const routes = visibleNavigationItems(previewProfile);

  expect(routes.map((item) => item.path)).toEqual(
    expect.arrayContaining(["/admin/overview", "/admin/acgs", "/rfa/queue", "/analyst/workbench"]),
  );
  expect(routes.find((item) => item.path === "/admin/overview")?.label).toBe("Admin");
  expect(routes.find((item) => item.path === "/admin/acgs")?.requiredPermissions).toEqual([
    "acg:view",
  ]);
});
