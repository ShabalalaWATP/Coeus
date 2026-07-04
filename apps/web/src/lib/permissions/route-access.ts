export type Permission =
  | "ticket:read_own"
  | "product:read"
  | "project:read"
  | "rfa:review"
  | "collection:review"
  | "analyst:work"
  | "qc:review"
  | "system:configure"
  | "audit:read";

export type UserProfile = {
  displayName: string;
  permissions: readonly Permission[];
};

export type NavigationItem = {
  label: string;
  path: string;
  icon:
    | "requests"
    | "store"
    | "projects"
    | "rfa"
    | "collection"
    | "analyst"
    | "qc"
    | "admin"
    | "audit"
    | "archive";
  requiredPermissions: readonly Permission[];
};

export const navigationItems: readonly NavigationItem[] = [
  {
    label: "Requests",
    path: "/app/requests",
    icon: "requests",
    requiredPermissions: ["ticket:read_own"],
  },
  {
    label: "Intelligence Store",
    path: "/store",
    icon: "store",
    requiredPermissions: ["product:read"],
  },
  { label: "Projects", path: "/projects", icon: "projects", requiredPermissions: ["project:read"] },
  { label: "RFA", path: "/rfa", icon: "rfa", requiredPermissions: ["rfa:review"] },
  {
    label: "Collection",
    path: "/collection",
    icon: "collection",
    requiredPermissions: ["collection:review"],
  },
  { label: "Analyst", path: "/analyst", icon: "analyst", requiredPermissions: ["analyst:work"] },
  { label: "QC", path: "/qc", icon: "qc", requiredPermissions: ["qc:review"] },
  { label: "Admin", path: "/admin", icon: "admin", requiredPermissions: ["system:configure"] },
  { label: "Audit", path: "/audit", icon: "audit", requiredPermissions: ["audit:read"] },
];

export const previewProfile: UserProfile = {
  displayName: "Sprint 1 Operator",
  permissions: navigationItems.flatMap((item) => item.requiredPermissions),
};

export function canAccessRoute(profile: UserProfile, route: NavigationItem) {
  const grantedPermissions = new Set(profile.permissions);
  return route.requiredPermissions.every((permission) => grantedPermissions.has(permission));
}

export function visibleNavigationItems(profile: UserProfile) {
  return navigationItems.filter((item) => canAccessRoute(profile, item));
}
