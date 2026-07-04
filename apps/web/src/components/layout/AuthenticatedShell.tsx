import { Navigate } from "react-router-dom";

import { AppShell } from "./AppShell";
import { RouteFallback } from "./RouteFallback";
import { useAuth } from "../../lib/auth/auth-context";

export function AuthenticatedShell() {
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
  return <AppShell profile={session.user} />;
}
