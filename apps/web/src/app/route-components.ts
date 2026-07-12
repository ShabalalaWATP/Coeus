import { lazy } from "react";

export const LoginPage = lazy(() => import("../features/auth/LoginPage"));
export const ForbiddenPage = lazy(() => import("../features/auth/ForbiddenPage"));
export const SessionExpiredPage = lazy(() => import("../features/auth/SessionExpiredPage"));
export const ChangePasswordPage = lazy(() => import("../features/auth/ChangePasswordPage"));
export const AcgAdminPage = lazy(() => import("../features/access/AcgAdminPage"));
export const AccessGroupsPage = lazy(() => import("../features/access/AccessGroupsPage"));
export const AdminOverviewPage = lazy(() => import("../features/admin/AdminOverviewPage"));
export const UserManagementPage = lazy(() => import("../features/admin/UserManagementPage"));
export const AnalyticsDashboardPage = lazy(
  () => import("../features/analytics/AnalyticsDashboardPage"),
);
export const AnalystWorkbenchPage = lazy(() => import("../features/analyst/AnalystWorkbenchPage"));
export const AuditPage = lazy(() => import("../features/audit/AuditPage"));
export const QcQueuePage = lazy(() => import("../features/qc/QcQueuePage"));
export const RequestsPage = lazy(() => import("../features/requests/RequestsPage"));
export const RoutingQueuePage = lazy(() => import("../features/routing/RoutingQueuePage"));
export const JiocOversightPage = lazy(() => import("../features/routing/JiocOversightPage"));
export const ProductDetailPage = lazy(() => import("../features/store/ProductDetailPage"));
export const ProductUploadPage = lazy(() => import("../features/store/ProductUploadPage"));
export const StorePage = lazy(() => import("../features/store/StorePage"));
export const TeamsPage = lazy(() => import("../features/teams/TeamsPage"));
