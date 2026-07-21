import type { AuthUser, Permission } from "../api-client/auth";
import { navigationPath, routePolicy } from "../../app/route-policy";

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

const navigationItems: readonly NavigationItem[] = [
  {
    label: "Requests",
    path: navigationPath(routePolicy.requests),
    group: "operations",
    icon: "requests",
    requiredPermissions: routePolicy.requests.permissions,
  },
  {
    label: "Access Groups",
    path: navigationPath(routePolicy.accessGroups),
    group: "operations",
    icon: "admin",
    requiredPermissions: routePolicy.accessGroups.permissions,
  },
  {
    label: "Intelligence Store",
    path: navigationPath(routePolicy.store),
    group: "operations",
    icon: "store",
    requiredPermissions: routePolicy.store.permissions,
  },
  {
    label: "My Products",
    path: navigationPath(routePolicy.myProducts),
    group: "operations",
    icon: "store",
    requiredPermissions: routePolicy.myProducts.permissions,
  },
  {
    label: "My Team",
    path: navigationPath(routePolicy.teams),
    group: "teams",
    icon: "analyst",
    // Every authenticated role may open the page; the server only returns
    // teams the user belongs to, and non-members see an empty state.
    requiredPermissions: routePolicy.teams.permissions,
  },
  {
    label: "JIOC Queue",
    path: navigationPath(routePolicy.jiocQueue),
    group: "teams",
    icon: "rfa",
    requiredPermissions: routePolicy.jiocQueue.permissions,
  },
  {
    label: "JIOC Oversight",
    path: navigationPath(routePolicy.jiocOversight),
    group: "teams",
    icon: "analytics",
    requiredPermissions: routePolicy.jiocOversight.permissions,
  },
  {
    label: "RFA Queue",
    path: navigationPath(routePolicy.rfaQueue),
    group: "teams",
    icon: "rfa",
    requiredPermissions: routePolicy.rfaQueue.permissions,
  },
  {
    label: "RFA Products",
    path: navigationPath(routePolicy.rfaProducts),
    group: "teams",
    icon: "rfa",
    requiredPermissions: routePolicy.rfaProducts.permissions,
  },
  {
    label: "RFA Analytics",
    path: navigationPath(routePolicy.rfaAnalytics),
    group: "teams",
    icon: "analytics",
    requiredPermissions: routePolicy.rfaAnalytics.permissions,
  },
  {
    label: "Collection Queue",
    path: navigationPath(routePolicy.collectionQueue),
    group: "teams",
    icon: "collection",
    requiredPermissions: routePolicy.collectionQueue.permissions,
  },
  {
    label: "Collection Products",
    path: navigationPath(routePolicy.collectionProducts),
    group: "teams",
    icon: "collection",
    requiredPermissions: routePolicy.collectionProducts.permissions,
  },
  {
    label: "Collection Analytics",
    path: navigationPath(routePolicy.collectionAnalytics),
    group: "teams",
    icon: "analytics",
    requiredPermissions: routePolicy.collectionAnalytics.permissions,
  },
  {
    label: "Analyst",
    path: navigationPath(routePolicy.analystWorkbench),
    group: "teams",
    icon: "analyst",
    requiredPermissions: routePolicy.analystWorkbench.permissions,
  },
  {
    label: "QC",
    path: navigationPath(routePolicy.qcQueue),
    group: "teams",
    icon: "qc",
    requiredPermissions: routePolicy.qcQueue.permissions,
  },
  {
    label: "Admin",
    path: navigationPath(routePolicy.adminOverview),
    group: "governance",
    icon: "admin",
    requiredPermissions: routePolicy.adminOverview.permissions,
  },
  {
    label: "Users",
    path: navigationPath(routePolicy.adminUsers),
    group: "governance",
    icon: "admin",
    requiredPermissions: routePolicy.adminUsers.permissions,
  },
  {
    label: "Admin Analytics",
    path: navigationPath(routePolicy.adminAnalytics),
    group: "governance",
    icon: "analytics",
    requiredPermissions: routePolicy.adminAnalytics.permissions,
  },
  {
    label: "ACGs",
    path: navigationPath(routePolicy.adminAcgs),
    group: "governance",
    icon: "admin",
    requiredPermissions: routePolicy.adminAcgs.permissions,
  },
  {
    label: "Audit",
    path: navigationPath(routePolicy.audit),
    group: "governance",
    icon: "audit",
    requiredPermissions: routePolicy.audit.permissions,
  },
];

function canAccessRoute(profile: UserProfile, route: NavigationItem) {
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
