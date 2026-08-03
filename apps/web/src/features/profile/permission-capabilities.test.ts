import { capabilityAreas, describedPermissionCount } from "./permission-capabilities";

test("groups granted permissions into areas a person would recognise", () => {
  const areas = capabilityAreas([
    "product:search",
    "product:download",
    "ticket:create",
    "analyst:work",
  ]);

  expect(areas).toEqual([
    { name: "Intelligence Store", capabilities: ["Search holdings", "Download assets"] },
    { name: "Requests", capabilities: ["Raise requests"] },
    { name: "Analysis", capabilities: ["Work assigned analyst tasks"] },
  ]);
});

test("omits an area entirely when none of its permissions are held", () => {
  const areas = capabilityAreas(["product:search"]);

  expect(areas.map((area) => area.name)).toEqual(["Intelligence Store"]);
});

test("never renders a permission that has no description", () => {
  // A permission added to the backend must not leak machine text onto a profile.
  const areas = capabilityAreas(["something:invented", "product:search"]);

  const rendered = areas.flatMap((area) => area.capabilities);
  expect(rendered).toEqual(["Search holdings"]);
});

test("an account with only sign-in permissions describes no capabilities", () => {
  expect(capabilityAreas(["auth:login", "auth:logout", "user:read_self"])).toEqual([]);
  expect(capabilityAreas([])).toEqual([]);
});

test("counts granted access without counting the ability to sign in", () => {
  expect(
    describedPermissionCount([
      "auth:login",
      "auth:logout",
      "user:read_self",
      "user:update_self",
      "product:search",
      "ticket:create",
    ]),
  ).toBe(2);
  expect(describedPermissionCount(["auth:login"])).toBe(0);
});
