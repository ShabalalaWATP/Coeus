import type { PropsWithChildren } from "react";
import { QueryClientProvider } from "@tanstack/react-query";

import type { ApiClient, AuthSession } from "../lib/api-client/client";
import { getQueryClient } from "./query-client";
import { AuthProvider } from "../lib/auth/auth-context";
import { ThemeProvider } from "../lib/theme/theme-context";

type AppProvidersProps = PropsWithChildren<{
  apiClient?: ApiClient;
  initialAuthSession?: AuthSession | null;
}>;

export function AppProviders({ apiClient, children, initialAuthSession }: AppProvidersProps) {
  return (
    <QueryClientProvider client={getQueryClient()}>
      <ThemeProvider>
        <AuthProvider client={apiClient} initialSession={initialAuthSession}>
          {children}
        </AuthProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
}
