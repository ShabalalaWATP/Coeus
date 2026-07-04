import {
  canAccessRoute,
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
