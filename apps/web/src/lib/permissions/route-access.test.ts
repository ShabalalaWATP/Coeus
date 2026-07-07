import {
  canAccessRoute,
  groupedNavigationItems,
  navigationItems,
  previewProfile,
  routeByPath,
  visibleNavigationItems,
  type UserProfile,
} from "./route-access";

test("preview profile can see every sprint shell route", () => {
  expect(visibleNavigationItems(previewProfile)).toHaveLength(navigationItems.length);
});

test("route access requires all route permissions", () => {
  const profile: UserProfile = {
    id: "customer",
    username: "customer@example.test",
    displayName: "Customer",
    roles: ["User"],
    defaultRoute: "/app/requests",
    permissions: ["ticket:read_own"],
  };

  expect(canAccessRoute(profile, navigationItems[0])).toBe(true);
  expect(canAccessRoute(profile, navigationItems[1])).toBe(false);
  expect(visibleNavigationItems(profile).map((item) => item.label)).toEqual(["Requests"]);
});

test("store manager sees store administration surfaces without admin overview", () => {
  const profile: UserProfile = {
    id: "store-manager",
    username: "store.manager@example.test",
    displayName: "Intelligence Store Manager",
    roles: ["Intelligence Store Manager"],
    defaultRoute: "/store",
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
  expect(canAccessRoute(profile, routeByPath("/admin/overview")!)).toBe(false);
});

test("groups navigation items and omits empty groups", () => {
  const operationsOnly = navigationItems.filter((item) => item.group === "operations");
  const groups = groupedNavigationItems(operationsOnly);

  expect(groups).toHaveLength(1);
  expect(groups[0].label).toBe("Operations");
  expect(groups[0].items.map((item) => item.label)).toContain("Requests");

  const allGroups = groupedNavigationItems(navigationItems);
  expect(allGroups.map((group) => group.label)).toEqual(["Operations", "Teams", "Governance"]);
});

test("route metadata includes sprint three access paths", () => {
  expect(navigationItems.map((item) => item.path)).toContain("/admin/overview");
  expect(navigationItems.map((item) => item.path)).toContain("/admin/acgs");
  expect(navigationItems.map((item) => item.path)).toContain("/projects");
  expect(navigationItems.map((item) => item.path)).toContain("/rfa/queue");
  expect(navigationItems.map((item) => item.path)).toContain("/analyst/workbench");
  expect(routeByPath("/admin/overview")?.label).toBe("Admin");
  expect(routeByPath("/admin/acgs")?.requiredPermissions).toEqual(["acg:view"]);
  expect(routeByPath("/missing")).toBeUndefined();
});
