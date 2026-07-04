import { lazy, Suspense } from "react";
import { createBrowserRouter, Navigate } from "react-router-dom";

import { AppShell } from "../components/layout/AppShell";
import { RouteFallback } from "../components/layout/RouteFallback";
import { previewProfile } from "../lib/permissions/route-access";
import type { UserProfile } from "../lib/permissions/route-access";

const OverviewPage = lazy(() => import("../features/overview/OverviewPage"));
const PlaceholderPage = lazy(() => import("../features/placeholder/PlaceholderPage"));

function withSuspense(element: React.ReactNode) {
  return <Suspense fallback={<RouteFallback />}>{element}</Suspense>;
}

export function createAppRouter(profile: UserProfile = previewProfile) {
  return createBrowserRouter([
    {
      path: "/",
      element: <AppShell profile={profile} />,
      children: [
        { index: true, element: <Navigate to="/app/requests" replace /> },
        {
          path: "app/requests",
          element: withSuspense(<OverviewPage />),
        },
        {
          path: "store",
          element: withSuspense(
            <PlaceholderPage
              title="Intelligence Store"
              description="Controlled search and product retrieval workspace."
            />,
          ),
        },
        {
          path: "projects",
          element: withSuspense(
            <PlaceholderPage
              title="Projects"
              description="Project workspaces will connect RFIs, teams, ACGs and products."
            />,
          ),
        },
        {
          path: "rfa",
          element: withSuspense(
            <PlaceholderPage title="RFA" description="Request for Assessment queue shell." />,
          ),
        },
        {
          path: "collection",
          element: withSuspense(
            <PlaceholderPage title="Collection" description="Collection management queue shell." />,
          ),
        },
        {
          path: "analyst",
          element: withSuspense(
            <PlaceholderPage
              title="Analyst"
              description="Analyst workbench shell for assigned tasks."
            />,
          ),
        },
        {
          path: "qc",
          element: withSuspense(
            <PlaceholderPage
              title="QC"
              description="Quality Control queue shell for product review."
            />,
          ),
        },
        {
          path: "admin",
          element: withSuspense(
            <PlaceholderPage title="Admin" description="Administrative controls shell." />,
          ),
        },
        {
          path: "audit",
          element: withSuspense(
            <PlaceholderPage title="Audit" description="Immutable audit event review shell." />,
          ),
        },
      ],
    },
  ]);
}
