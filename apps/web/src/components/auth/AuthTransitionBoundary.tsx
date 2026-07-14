import type { PropsWithChildren } from "react";

import {
  LogoutPendingPage,
  LogoutUnconfirmedPage,
} from "../../features/auth/LogoutUnconfirmedPage";
import { useAuth } from "../../lib/auth/auth-context";
import { RouteFallback } from "../layout/RouteFallback";

export function AuthTransitionBoundary({ children }: PropsWithChildren) {
  const { status } = useAuth();

  if (status === "loading") {
    return <RouteFallback />;
  }
  if (status === "logging_out") {
    return <LogoutPendingPage />;
  }
  if (status === "logout_unconfirmed") {
    return <LogoutUnconfirmedPage />;
  }
  return children;
}
