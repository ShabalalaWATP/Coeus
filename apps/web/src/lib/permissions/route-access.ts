import type { AuthUser, Permission } from "../api-client/client";

export type UserProfile = AuthUser;

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
  { label: "RFA Queue", path: "/rfa/queue", icon: "rfa", requiredPermissions: ["rfa:review"] },
  {
    label: "RFA Products",
    path: "/rfa/products",
    icon: "rfa",
    requiredPermissions: ["rfa:add_product"],
  },
  {
    label: "Collection Queue",
    path: "/collection/queue",
    icon: "collection",
    requiredPermissions: ["collection:review"],
  },
  {
    label: "Collection Products",
    path: "/collection/products",
    icon: "collection",
    requiredPermissions: ["collection:add_product"],
  },
  {
    label: "Analyst",
    path: "/analyst/workbench",
    icon: "analyst",
    requiredPermissions: ["analyst:work"],
  },
  { label: "QC", path: "/qc/queue", icon: "qc", requiredPermissions: ["qc:review"] },
  {
    label: "Admin",
    path: "/admin/overview",
    icon: "admin",
    requiredPermissions: ["system:configure"],
  },
  { label: "ACGs", path: "/admin/acgs", icon: "admin", requiredPermissions: ["acg:view"] },
  { label: "Audit", path: "/audit", icon: "audit", requiredPermissions: ["audit:read"] },
];

export const previewProfile: UserProfile = {
  id: "preview-user",
  username: "preview@example.test",
  displayName: "Sprint 2 Operator",
  roles: ["Administrator"],
  defaultRoute: "/admin/overview",
  permissions: navigationItems.flatMap((item) => item.requiredPermissions),
};

export function canAccessRoute(profile: UserProfile, route: NavigationItem) {
  return hasPermissions(profile, route.requiredPermissions);
}

export function hasPermissions(profile: UserProfile, permissions: readonly Permission[]) {
  const grantedPermissions = new Set(profile.permissions);
  return permissions.every((permission) => grantedPermissions.has(permission));
}

export function visibleNavigationItems(profile: UserProfile) {
  return navigationItems.filter((item) => canAccessRoute(profile, item));
}

export function routeByPath(path: string) {
  return navigationItems.find((item) => item.path === path);
}
