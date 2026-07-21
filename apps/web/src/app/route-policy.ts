import type { Permission } from "../lib/api-client/auth";

type RoutePolicy = {
  path: string;
  permissions: readonly Permission[];
};

export const routePolicy = {
  accountPassword: { path: "account/password", permissions: [] },
  accountProfile: { path: "account/profile", permissions: ["user:read_self"] },
  requests: { path: "app/requests", permissions: ["ticket:read_own"] },
  requestNew: {
    path: "app/requests/new",
    permissions: ["ticket:read_own", "chat:use"],
  },
  requestDetail: { path: "app/requests/:ticketId", permissions: [] },
  accessGroups: { path: "access-groups", permissions: ["user:read_self"] },
  store: { path: "store", permissions: ["product:read", "product:search"] },
  myProducts: {
    path: "store/my-products",
    permissions: ["product:read", "product:search"],
  },
  storeUpload: { path: "store/upload", permissions: ["product:create_existing"] },
  storeProduct: { path: "store/products/:productId", permissions: ["product:read"] },
  storeAsset: {
    path: "store/products/:productId/assets/:assetId",
    permissions: ["product:read"],
  },
  jiocQueue: { path: "jioc/queue", permissions: ["jioc:review"] },
  jiocOversight: { path: "jioc/oversight", permissions: ["jioc:oversight"] },
  rfaQueue: { path: "rfa/queue", permissions: ["rfa:review"] },
  rfaProducts: {
    path: "rfa/products",
    permissions: ["rfa:add_product", "product:read", "product:search"],
  },
  rfaAnalytics: {
    path: "rfa/analytics",
    permissions: ["analytics:view_team", "rfa:review"],
  },
  collectionQueue: { path: "collection/queue", permissions: ["collection:review"] },
  collectionProducts: {
    path: "collection/products",
    permissions: ["collection:add_product", "product:read", "product:search"],
  },
  collectionAnalytics: {
    path: "collection/analytics",
    permissions: ["analytics:view_team", "collection:review"],
  },
  teams: { path: "teams", permissions: ["user:read_self"] },
  analystWorkbench: { path: "analyst/workbench", permissions: ["analyst:work"] },
  analystTask: { path: "analyst/tasks/:taskId", permissions: ["analyst:work"] },
  qcQueue: { path: "qc/queue", permissions: ["qc:review"] },
  qcProduct: { path: "qc/products/:productId", permissions: ["qc:review"] },
  adminOverview: { path: "admin/overview", permissions: ["system:configure"] },
  adminUsers: { path: "admin/users", permissions: ["user:assign_role"] },
  adminAcgs: { path: "admin/acgs", permissions: ["acg:view"] },
  adminAnalytics: { path: "admin/analytics", permissions: ["analytics:view_global"] },
  adminAcgDetail: { path: "admin/acgs/:acgId", permissions: ["acg:view"] },
  audit: { path: "audit", permissions: ["audit:read"] },
} as const satisfies Record<string, RoutePolicy>;

export function navigationPath(policy: RoutePolicy): string {
  return `/${policy.path}`;
}
