import {
  canAccessRoute,
  navigationItems,
  previewProfile,
  visibleNavigationItems,
  type UserProfile,
} from "./route-access";

test("preview profile can see every sprint shell route", () => {
  expect(visibleNavigationItems(previewProfile)).toHaveLength(navigationItems.length);
});

test("route access requires all route permissions", () => {
  const profile: UserProfile = { displayName: "Customer", permissions: ["ticket:read_own"] };

  expect(canAccessRoute(profile, navigationItems[0])).toBe(true);
  expect(canAccessRoute(profile, navigationItems[1])).toBe(false);
  expect(visibleNavigationItems(profile).map((item) => item.label)).toEqual(["Requests"]);
});
