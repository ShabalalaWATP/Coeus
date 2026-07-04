import type { PropsWithChildren } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { RouteFallback } from "../layout/RouteFallback";
import type { Permission } from "../../lib/api-client/client";
import { useAuth } from "../../lib/auth/auth-context";
import { hasPermissions } from "../../lib/permissions/route-access";

type ProtectedRouteProps = PropsWithChildren<{
  requiredPermissions?: readonly Permission[];
}>;

export function ProtectedRoute({ children, requiredPermissions = [] }: ProtectedRouteProps) {
  const { session, status } = useAuth();
  const location = useLocation();

  if (status === "loading") {
    return <RouteFallback />;
  }
  if (status === "expired") {
    return <Navigate to="/session-expired" replace state={{ from: location.pathname }} />;
  }
  if (session === null) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  if (!hasPermissions(session.user, requiredPermissions)) {
    return <Navigate to="/forbidden" replace state={{ from: location.pathname }} />;
  }
  return children;
}
