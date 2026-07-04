import { Navigate } from "react-router-dom";

import { RouteFallback } from "../layout/RouteFallback";
import { useAuth } from "../../lib/auth/auth-context";

export function DefaultRouteRedirect() {
  const { session, status } = useAuth();

  if (status === "loading") {
    return <RouteFallback />;
  }
  if (status === "expired") {
    return <Navigate to="/session-expired" replace />;
  }
  if (session === null) {
    return <Navigate to="/login" replace />;
  }
  return <Navigate to={session.user.defaultRoute} replace />;
}
