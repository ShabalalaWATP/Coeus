import { Suspense } from "react";
import { createBrowserRouter } from "react-router-dom";

import { DefaultRouteRedirect } from "../components/auth/DefaultRouteRedirect";
import { ProtectedRoute } from "../components/auth/ProtectedRoute";
import { AuthenticatedShell } from "../components/layout/AuthenticatedShell";
import { RouteFallback } from "../components/layout/RouteFallback";
import type { Permission } from "../lib/api-client/client";
import {
  AcgAdminPage,
  AdminOverviewPage,
  AnalystWorkbenchPage,
  AnalyticsDashboardPage,
  AuditPage,
  ChangePasswordPage,
  ForbiddenPage,
  LoginPage,
  ProductDetailPage,
  ProductUploadPage,
  QcQueuePage,
  RequestsPage,
  RoutingQueuePage,
  SessionExpiredPage,
  StorePage,
  UserManagementPage,
} from "./route-components";

function withSuspense(element: React.ReactNode) {
  return <Suspense fallback={<RouteFallback />}>{element}</Suspense>;
}

function protectedPage(element: React.ReactNode, requiredPermissions: readonly Permission[]) {
  return withSuspense(
    <ProtectedRoute requiredPermissions={requiredPermissions}>{element}</ProtectedRoute>,
  );
}

export function createAppRouter() {
  return createBrowserRouter([
    {
      path: "/login",
      element: withSuspense(<LoginPage />),
    },
    {
      path: "/forbidden",
      element: withSuspense(<ForbiddenPage />),
    },
    {
      path: "/session-expired",
      element: withSuspense(<SessionExpiredPage />),
    },
    {
      path: "/",
      element: <AuthenticatedShell />,
      children: [
        { index: true, element: <DefaultRouteRedirect /> },
        {
          path: "account/password",
          element: protectedPage(<ChangePasswordPage />, []),
        },
        {
          path: "app/requests",
          element: protectedPage(<RequestsPage />, ["ticket:read_own"]),
        },
        {
          path: "app/requests/new",
          element: protectedPage(<RequestsPage />, ["ticket:read_own", "chat:use"]),
        },
        {
          // Tagged collaborators from any role can follow a shared request link.
          path: "app/requests/:ticketId",
          element: protectedPage(<RequestsPage />, []),
        },
        {
          path: "store",
          element: protectedPage(<StorePage />, ["product:read", "product:search"]),
        },
        {
          path: "store/my-products",
          element: protectedPage(<StorePage scope="mine" />, ["product:read", "product:search"]),
        },
        {
          path: "store/upload",
          element: protectedPage(<ProductUploadPage />, ["product:create_existing"]),
        },
        {
          path: "store/products/:productId",
          element: protectedPage(<ProductDetailPage />, ["product:read"]),
        },
        {
          path: "store/products/:productId/assets/:assetId",
          element: protectedPage(<ProductDetailPage />, ["product:read", "product:download"]),
        },
        {
          path: "rfa/queue",
          element: protectedPage(<RoutingQueuePage route="rfa" />, ["rfa:review"]),
        },
        {
          path: "rfa/products",
          element: protectedPage(
            <StorePage
              ownerTeam="RFA"
              title="RFA Products"
              description="Request for Assessment product workspace."
            />,
            ["rfa:add_product", "product:read", "product:search"],
          ),
        },
        {
          path: "rfa/analytics",
          element: protectedPage(<AnalyticsDashboardPage audience="rfa" />, [
            "analytics:view_team",
            "rfa:review",
          ]),
        },
        {
          path: "collection/queue",
          element: protectedPage(<RoutingQueuePage route="cm" />, ["collection:review"]),
        },
        {
          path: "collection/products",
          element: protectedPage(
            <StorePage
              ownerTeam="Collection"
              title="Collection Products"
              description="Collection product workspace."
            />,
            ["collection:add_product", "product:read", "product:search"],
          ),
        },
        {
          path: "collection/analytics",
          element: protectedPage(<AnalyticsDashboardPage audience="collection" />, [
            "analytics:view_team",
            "collection:review",
          ]),
        },
        {
          path: "analyst/workbench",
          element: protectedPage(<AnalystWorkbenchPage />, ["analyst:work"]),
        },
        {
          path: "analyst/tasks/:taskId",
          element: protectedPage(<AnalystWorkbenchPage />, ["analyst:work"]),
        },
        {
          path: "qc/queue",
          element: protectedPage(<QcQueuePage />, ["qc:review"]),
        },
        {
          path: "qc/products/:productId",
          element: protectedPage(<QcQueuePage />, ["qc:review"]),
        },
        {
          path: "admin/overview",
          element: protectedPage(<AdminOverviewPage />, ["system:configure"]),
        },
        {
          path: "admin/users",
          element: protectedPage(<UserManagementPage />, ["user:assign_role"]),
        },
        {
          path: "admin/acgs",
          element: protectedPage(<AcgAdminPage />, ["acg:view"]),
        },
        {
          path: "admin/analytics",
          element: protectedPage(<AnalyticsDashboardPage audience="admin" />, [
            "analytics:view_global",
          ]),
        },
        {
          path: "admin/acgs/:acgId",
          element: protectedPage(<AcgAdminPage />, ["acg:view"]),
        },
        {
          path: "audit",
          element: protectedPage(<AuditPage />, ["audit:read"]),
        },
      ],
    },
  ]);
}
