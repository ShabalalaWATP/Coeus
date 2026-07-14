import { Suspense } from "react";
import { createBrowserRouter } from "react-router-dom";

import { DefaultRouteRedirect } from "../components/auth/DefaultRouteRedirect";
import { AuthTransitionBoundary } from "../components/auth/AuthTransitionBoundary";
import { ProtectedRoute } from "../components/auth/ProtectedRoute";
import { AuthenticatedShell } from "../components/layout/AuthenticatedShell";
import { RouteFallback } from "../components/layout/RouteFallback";
import { RouteRecoveryPage } from "../components/layout/RouteRecoveryPage";
import type { Permission } from "../lib/api-client/auth";
import {
  AcgAdminPage,
  AccessGroupsPage,
  AdminOverviewPage,
  AnalystWorkbenchPage,
  AnalyticsDashboardPage,
  AuditPage,
  ChangePasswordPage,
  ForbiddenPage,
  LoginPage,
  JiocOversightPage,
  ProductDetailPage,
  ProductUploadPage,
  QcQueuePage,
  RequestsPage,
  RoutingQueuePage,
  SessionExpiredPage,
  StorePage,
  TeamsPage,
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

function publicPage(element: React.ReactNode) {
  return <AuthTransitionBoundary>{withSuspense(element)}</AuthTransitionBoundary>;
}

export function createAppRouter() {
  return createBrowserRouter([
    {
      path: "/login",
      element: publicPage(<LoginPage />),
    },
    {
      path: "/forbidden",
      element: publicPage(<ForbiddenPage />),
    },
    {
      path: "/session-expired",
      element: publicPage(<SessionExpiredPage />),
    },
    {
      path: "/",
      element: <AuthenticatedShell />,
      errorElement: <RouteRecoveryPage />,
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
          path: "access-groups",
          element: protectedPage(<AccessGroupsPage />, ["user:read_self"]),
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
          element: protectedPage(<ProductDetailPage />, ["product:read"]),
        },
        {
          path: "jioc/queue",
          element: protectedPage(<RoutingQueuePage queue="jioc" />, ["jioc:review"]),
        },
        {
          path: "jioc/oversight",
          element: protectedPage(<JiocOversightPage />, ["jioc:review"]),
        },
        {
          path: "rfa/queue",
          element: protectedPage(<RoutingQueuePage queue="rfa" />, ["rfa:review"]),
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
          element: protectedPage(<RoutingQueuePage queue="cm" />, ["collection:review"]),
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
          // Membership is checked server-side; non-members see an empty state.
          path: "teams",
          element: protectedPage(<TeamsPage />, ["user:read_self"]),
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
