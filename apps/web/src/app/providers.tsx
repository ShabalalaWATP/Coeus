import type { PropsWithChildren } from "react";
import { QueryClientProvider } from "@tanstack/react-query";

import { getQueryClient } from "./query-client";
import { ThemeProvider } from "../lib/theme/theme-context";

export function AppProviders({ children }: PropsWithChildren) {
  return (
    <QueryClientProvider client={getQueryClient()}>
      <ThemeProvider>{children}</ThemeProvider>
    </QueryClientProvider>
  );
}
