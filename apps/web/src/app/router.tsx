import { lazy, Suspense } from "react";
import { createBrowserRouter } from "react-router-dom";

import { DefaultRouteRedirect } from "../components/auth/DefaultRouteRedirect";
import { ProtectedRoute } from "../components/auth/ProtectedRoute";
import { AuthenticatedShell } from "../components/layout/AuthenticatedShell";
import { RouteFallback } from "../components/layout/RouteFallback";
import type { Permission } from "../lib/api-client/client";

const LoginPage = lazy(() => import("../features/auth/LoginPage"));
const ForbiddenPage = lazy(() => import("../features/auth/ForbiddenPage"));
const SessionExpiredPage = lazy(() => import("../features/auth/SessionExpiredPage"));
const AcgAdminPage = lazy(() => import("../features/access/AcgAdminPage"));
const RequestsPage = lazy(() => import("../features/requests/RequestsPage"));
const PlaceholderPage = lazy(() => import("../features/placeholder/PlaceholderPage"));
const ProjectWorkspacePage = lazy(() => import("../features/projects/ProjectWorkspacePage"));

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
          path: "app/requests",
          element: protectedPage(<RequestsPage />, ["ticket:read_own"]),
        },
        {
          path: "store",
          element: protectedPage(
            <PlaceholderPage
              title="Intelligence Store"
              description="Controlled search and product retrieval workspace."
            />,
            ["product:read"],
          ),
        },
        {
          path: "projects",
          element: protectedPage(<ProjectWorkspacePage />, ["project:read"]),
        },
        {
          path: "projects/:projectId",
          element: protectedPage(<ProjectWorkspacePage />, ["project:read"]),
        },
        {
          path: "projects/:projectId/plan",
          element: protectedPage(<ProjectWorkspacePage view="plan" />, ["project:read"]),
        },
        {
          path: "projects/:projectId/members",
          element: protectedPage(<ProjectWorkspacePage view="members" />, ["project:read"]),
        },
        {
          path: "projects/:projectId/products",
          element: protectedPage(<ProjectWorkspacePage view="products" />, ["project:read"]),
        },
        {
          path: "rfa/queue",
          element: protectedPage(
            <PlaceholderPage title="RFA Queue" description="Request for Assessment queue shell." />,
            ["rfa:review"],
          ),
        },
        {
          path: "rfa/products",
          element: protectedPage(
            <PlaceholderPage
              title="RFA Products"
              description="Request for Assessment product workspace."
            />,
            ["rfa:add_product"],
          ),
        },
        {
          path: "collection/queue",
          element: protectedPage(
            <PlaceholderPage
              title="Collection Queue"
              description="Collection management queue shell."
            />,
            ["collection:review"],
          ),
        },
        {
          path: "collection/products",
          element: protectedPage(
            <PlaceholderPage
              title="Collection Products"
              description="Collection product workspace."
            />,
            ["collection:add_product"],
          ),
        },
        {
          path: "analyst/workbench",
          element: protectedPage(
            <PlaceholderPage
              title="Analyst"
              description="Analyst workbench shell for assigned tasks."
            />,
            ["analyst:work"],
          ),
        },
        {
          path: "qc/queue",
          element: protectedPage(
            <PlaceholderPage
              title="QC"
              description="Quality Control queue shell for product review."
            />,
            ["qc:review"],
          ),
        },
        {
          path: "admin/overview",
          element: protectedPage(
            <PlaceholderPage title="Admin" description="Administrative controls shell." />,
            ["system:configure"],
          ),
        },
        {
          path: "admin/acgs",
          element: protectedPage(<AcgAdminPage />, ["acg:view"]),
        },
        {
          path: "admin/acgs/:acgId",
          element: protectedPage(<AcgAdminPage />, ["acg:view"]),
        },
        {
          path: "audit",
          element: protectedPage(
            <PlaceholderPage title="Audit" description="Immutable audit event review shell." />,
            ["audit:read"],
          ),
        },
      ],
    },
  ]);
}
