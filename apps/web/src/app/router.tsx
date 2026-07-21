import { Suspense } from "react";
import { createBrowserRouter } from "react-router-dom";

import { DefaultRouteRedirect } from "../components/auth/DefaultRouteRedirect";
import { AuthTransitionBoundary } from "../components/auth/AuthTransitionBoundary";
import { ProtectedRoute } from "../components/auth/ProtectedRoute";
import { AuthenticatedShell } from "../components/layout/AuthenticatedShell";
import { RouteFallback } from "../components/layout/RouteFallback";
import { RouteRecoveryPage } from "../components/layout/RouteRecoveryPage";
import type { Permission } from "../lib/api-client/auth";
import { routePolicy } from "./route-policy";
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
  ProfilePage,
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
          path: routePolicy.accountPassword.path,
          element: protectedPage(<ChangePasswordPage />, routePolicy.accountPassword.permissions),
        },
        {
          path: routePolicy.accountProfile.path,
          element: protectedPage(<ProfilePage />, routePolicy.accountProfile.permissions),
        },
        {
          path: routePolicy.requests.path,
          element: protectedPage(<RequestsPage />, routePolicy.requests.permissions),
        },
        {
          path: routePolicy.requestNew.path,
          element: protectedPage(<RequestsPage />, routePolicy.requestNew.permissions),
        },
        {
          // Tagged collaborators from any role can follow a shared request link.
          path: routePolicy.requestDetail.path,
          element: protectedPage(<RequestsPage />, routePolicy.requestDetail.permissions),
        },
        {
          path: routePolicy.accessGroups.path,
          element: protectedPage(<AccessGroupsPage />, routePolicy.accessGroups.permissions),
        },
        {
          path: routePolicy.store.path,
          element: protectedPage(<StorePage />, routePolicy.store.permissions),
        },
        {
          path: routePolicy.myProducts.path,
          element: protectedPage(<StorePage scope="mine" />, routePolicy.myProducts.permissions),
        },
        {
          path: routePolicy.storeUpload.path,
          element: protectedPage(<ProductUploadPage />, routePolicy.storeUpload.permissions),
        },
        {
          path: routePolicy.storeProduct.path,
          element: protectedPage(<ProductDetailPage />, routePolicy.storeProduct.permissions),
        },
        {
          path: routePolicy.storeAsset.path,
          element: protectedPage(<ProductDetailPage />, routePolicy.storeAsset.permissions),
        },
        {
          path: routePolicy.jiocQueue.path,
          element: protectedPage(
            <RoutingQueuePage queue="jioc" />,
            routePolicy.jiocQueue.permissions,
          ),
        },
        {
          path: routePolicy.jiocOversight.path,
          element: protectedPage(<JiocOversightPage />, routePolicy.jiocOversight.permissions),
        },
        {
          path: routePolicy.rfaQueue.path,
          element: protectedPage(
            <RoutingQueuePage queue="rfa" />,
            routePolicy.rfaQueue.permissions,
          ),
        },
        {
          path: routePolicy.rfaProducts.path,
          element: protectedPage(
            <StorePage
              ownerTeam="RFA"
              title="RFA Products"
              description="Request for Assessment product workspace."
            />,
            routePolicy.rfaProducts.permissions,
          ),
        },
        {
          path: routePolicy.rfaAnalytics.path,
          element: protectedPage(
            <AnalyticsDashboardPage audience="rfa" />,
            routePolicy.rfaAnalytics.permissions,
          ),
        },
        {
          path: routePolicy.collectionQueue.path,
          element: protectedPage(
            <RoutingQueuePage queue="cm" />,
            routePolicy.collectionQueue.permissions,
          ),
        },
        {
          path: routePolicy.collectionProducts.path,
          element: protectedPage(
            <StorePage
              ownerTeam="Collection"
              title="Collection Products"
              description="Collection product workspace."
            />,
            routePolicy.collectionProducts.permissions,
          ),
        },
        {
          path: routePolicy.collectionAnalytics.path,
          element: protectedPage(
            <AnalyticsDashboardPage audience="collection" />,
            routePolicy.collectionAnalytics.permissions,
          ),
        },
        {
          // Membership is checked server-side; non-members see an empty state.
          path: routePolicy.teams.path,
          element: protectedPage(<TeamsPage />, routePolicy.teams.permissions),
        },
        {
          path: routePolicy.analystWorkbench.path,
          element: protectedPage(
            <AnalystWorkbenchPage />,
            routePolicy.analystWorkbench.permissions,
          ),
        },
        {
          path: routePolicy.analystTask.path,
          element: protectedPage(<AnalystWorkbenchPage />, routePolicy.analystTask.permissions),
        },
        {
          path: routePolicy.qcQueue.path,
          element: protectedPage(<QcQueuePage />, routePolicy.qcQueue.permissions),
        },
        {
          path: routePolicy.qcProduct.path,
          element: protectedPage(<QcQueuePage />, routePolicy.qcProduct.permissions),
        },
        {
          path: routePolicy.adminOverview.path,
          element: protectedPage(<AdminOverviewPage />, routePolicy.adminOverview.permissions),
        },
        {
          path: routePolicy.adminUsers.path,
          element: protectedPage(<UserManagementPage />, routePolicy.adminUsers.permissions),
        },
        {
          path: routePolicy.adminAcgs.path,
          element: protectedPage(<AcgAdminPage />, routePolicy.adminAcgs.permissions),
        },
        {
          path: routePolicy.adminAnalytics.path,
          element: protectedPage(
            <AnalyticsDashboardPage audience="admin" />,
            routePolicy.adminAnalytics.permissions,
          ),
        },
        {
          path: routePolicy.adminAcgDetail.path,
          element: protectedPage(<AcgAdminPage />, routePolicy.adminAcgDetail.permissions),
        },
        {
          path: routePolicy.audit.path,
          element: protectedPage(<AuditPage />, routePolicy.audit.permissions),
        },
      ],
    },
  ]);
}
