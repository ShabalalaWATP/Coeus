import type { PropsWithChildren } from "react";
import { useCallback } from "react";
import { QueryClientProvider } from "@tanstack/react-query";

import type { AuthApi, AuthSession } from "../lib/api-client/auth";
import { getQueryClient } from "./query-client";
import { AuthProvider } from "../lib/auth/auth-context";
import { ThemeProvider } from "../lib/theme/theme-context";

type AppProvidersProps = PropsWithChildren<{
  authApi?: AuthApi;
  initialAuthSession?: AuthSession | null;
}>;

export function AppProviders({ authApi, children, initialAuthSession }: AppProvidersProps) {
  const queryClient = getQueryClient();
  const clearSensitiveCache = useCallback(() => queryClient.clear(), [queryClient]);
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <AuthProvider
          clearSensitiveCache={clearSensitiveCache}
          authApi={authApi}
          initialSession={initialAuthSession}
        >
          {children}
        </AuthProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
}
