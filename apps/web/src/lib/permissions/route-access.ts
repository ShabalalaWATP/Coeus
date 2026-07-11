import type { AuthUser, Permission } from "../api-client/auth";

export type UserProfile = AuthUser;

type NavigationGroup = "operations" | "teams" | "governance";

const navigationGroupLabels: Record<NavigationGroup, string> = {
  operations: "Operations",
  teams: "Teams",
  governance: "Governance",
};

export type NavigationItem = {
  label: string;
  path: string;
  group: NavigationGroup;
  icon:
    | "requests"
    | "store"
    | "rfa"
    | "collection"
    | "analyst"
    | "qc"
    | "analytics"
    | "admin"
    | "audit"
    | "archive";
  requiredPermissions: readonly Permission[];
};

export const navigationItems: readonly NavigationItem[] = [
  {
    label: "Requests",
    path: "/app/requests",
    group: "operations",
    icon: "requests",
    requiredPermissions: ["ticket:read_own"],
  },
  {
    label: "Intelligence Store",
    path: "/store",
    group: "operations",
    icon: "store",
    requiredPermissions: ["product:read", "product:search"],
  },
  {
    label: "My Products",
    path: "/store/my-products",
    group: "operations",
    icon: "store",
    requiredPermissions: ["product:read", "product:search"],
  },
  {
    label: "My Team",
    path: "/teams",
    group: "teams",
    icon: "analyst",
    // Every authenticated role may open the page; the server only returns
    // teams the user belongs to, and non-members see an empty state.
    requiredPermissions: ["user:read_self"],
  },
  {
    label: "JIOC Queue",
    path: "/jioc/queue",
    group: "teams",
    icon: "rfa",
    requiredPermissions: ["jioc:review"],
  },
  {
    label: "RFA Queue",
    path: "/rfa/queue",
    group: "teams",
    icon: "rfa",
    requiredPermissions: ["rfa:review"],
  },
  {
    label: "RFA Products",
    path: "/rfa/products",
    group: "teams",
    icon: "rfa",
    requiredPermissions: ["rfa:add_product", "product:read", "product:search"],
  },
  {
    label: "RFA Analytics",
    path: "/rfa/analytics",
    group: "teams",
    icon: "analytics",
    requiredPermissions: ["analytics:view_team", "rfa:review"],
  },
  {
    label: "Collection Queue",
    path: "/collection/queue",
    group: "teams",
    icon: "collection",
    requiredPermissions: ["collection:review"],
  },
  {
    label: "Collection Products",
    path: "/collection/products",
    group: "teams",
    icon: "collection",
    requiredPermissions: ["collection:add_product", "product:read", "product:search"],
  },
  {
    label: "Collection Analytics",
    path: "/collection/analytics",
    group: "teams",
    icon: "analytics",
    requiredPermissions: ["analytics:view_team", "collection:review"],
  },
  {
    label: "Analyst",
    path: "/analyst/workbench",
    group: "teams",
    icon: "analyst",
    requiredPermissions: ["analyst:work"],
  },
  {
    label: "QC",
    path: "/qc/queue",
    group: "teams",
    icon: "qc",
    requiredPermissions: ["qc:review"],
  },
  {
    label: "Admin",
    path: "/admin/overview",
    group: "governance",
    icon: "admin",
    requiredPermissions: ["system:configure"],
  },
  {
    label: "Users",
    path: "/admin/users",
    group: "governance",
    icon: "admin",
    requiredPermissions: ["user:assign_role"],
  },
  {
    label: "Admin Analytics",
    path: "/admin/analytics",
    group: "governance",
    icon: "analytics",
    requiredPermissions: ["analytics:view_global"],
  },
  {
    label: "ACGs",
    path: "/admin/acgs",
    group: "governance",
    icon: "admin",
    requiredPermissions: ["acg:view"],
  },
  {
    label: "Audit",
    path: "/audit",
    group: "governance",
    icon: "audit",
    requiredPermissions: ["audit:read"],
  },
];

export const previewProfile: UserProfile = {
  id: "preview-user",
  username: "preview@example.test",
  displayName: "Sprint 2 Operator",
  roles: ["Administrator"],
  defaultRoute: "/admin/overview",
  permissions: [
    ...navigationItems.flatMap((item) => item.requiredPermissions),
    "product:create_existing",
    "product:download",
    "acg:create",
    "acg:update",
    "acg:assign_user",
    "chat:use",
    "ticket:create",
    "ticket:add_information",
    "ticket:add_comment",
    "rfi:search",
    "rfi:accept_product",
    "rfi:reject_product",
  ],
};

export function canAccessRoute(profile: UserProfile, route: NavigationItem) {
  return hasPermissions(profile, route.requiredPermissions);
}

export function hasPermissions(profile: UserProfile, permissions: readonly Permission[]) {
  const grantedPermissions = new Set(profile.permissions);
  return permissions.every((permission) => grantedPermissions.has(permission));
}

export function visibleNavigationItems(profile: UserProfile) {
  return navigationItems.filter(
    (item) =>
      canAccessRoute(profile, item) &&
      (item.path !== "/store/my-products" || hasOwnedProductRole(profile.roles)),
  );
}

function hasOwnedProductRole(roles: readonly string[]) {
  return roles.some((role) =>
    [
      "RFA Manager",
      "RFA Team Member",
      "Request for Assessment Manager",
      "Request for Assessment Team Member",
      "CM Manager",
      "CM Team Member",
      "Collection Manager",
      "Collection Team Member",
    ].includes(role),
  );
}

export function groupedNavigationItems(items: readonly NavigationItem[]) {
  const groups: { group: NavigationGroup; label: string; items: NavigationItem[] }[] = [];
  for (const group of Object.keys(navigationGroupLabels) as NavigationGroup[]) {
    const groupItems = items.filter((item) => item.group === group);
    if (groupItems.length > 0) {
      groups.push({ group, label: navigationGroupLabels[group], items: groupItems });
    }
  }
  return groups;
}

export function routeByPath(path: string) {
  return navigationItems.find((item) => item.path === path);
}
