import { lazy } from "react";

export const LoginPage = lazy(() => import("../features/auth/LoginPage"));
export const ForbiddenPage = lazy(() => import("../features/auth/ForbiddenPage"));
export const SessionExpiredPage = lazy(() => import("../features/auth/SessionExpiredPage"));
export const AcgAdminPage = lazy(() => import("../features/access/AcgAdminPage"));
export const AnalyticsDashboardPage = lazy(
  () => import("../features/analytics/AnalyticsDashboardPage"),
);
export const AnalystWorkbenchPage = lazy(() => import("../features/analyst/AnalystWorkbenchPage"));
export const QcQueuePage = lazy(() => import("../features/qc/QcQueuePage"));
export const RequestsPage = lazy(() => import("../features/requests/RequestsPage"));
export const RoutingQueuePage = lazy(() => import("../features/routing/RoutingQueuePage"));
export const PlaceholderPage = lazy(() => import("../features/placeholder/PlaceholderPage"));
export const ProductDetailPage = lazy(() => import("../features/store/ProductDetailPage"));
export const ProductUploadPage = lazy(() => import("../features/store/ProductUploadPage"));
export const ProjectWorkspacePage = lazy(() => import("../features/projects/ProjectWorkspacePage"));
export const StorePage = lazy(() => import("../features/store/StorePage"));
