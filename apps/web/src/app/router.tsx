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
const OverviewPage = lazy(() => import("../features/overview/OverviewPage"));
const PlaceholderPage = lazy(() => import("../features/placeholder/PlaceholderPage"));

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
          element: protectedPage(<OverviewPage />, ["ticket:read_own"]),
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
          element: protectedPage(
            <PlaceholderPage
              title="Projects"
              description="Project workspaces will connect RFIs, teams, ACGs and products."
            />,
            ["project:read"],
          ),
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
