import { Navigate, useLocation } from "react-router-dom";

import { AppShell } from "./AppShell";
import { RouteFallback } from "./RouteFallback";
import {
  LogoutPendingPage,
  LogoutUnconfirmedPage,
} from "../../features/auth/LogoutUnconfirmedPage";
import { useAuth } from "../../lib/auth/auth-context";

export function AuthenticatedShell() {
  const { session, status } = useAuth();
  const location = useLocation();

  if (status === "loading") {
    return <RouteFallback />;
  }
  if (status === "logging_out") {
    return <LogoutPendingPage />;
  }
  if (status === "logout_unconfirmed") {
    return <LogoutUnconfirmedPage />;
  }
  if (status === "expired") {
    return <Navigate to="/session-expired" replace />;
  }
  if (session === null) {
    return <Navigate to="/login" replace />;
  }
  if (session.passwordResetRequired === true && location.pathname !== "/account/password") {
    return <Navigate to="/account/password" replace />;
  }
  return <AppShell profile={session.user} />;
}
