import { render, type RenderResult } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router-dom";

import { AppProviders } from "../app/providers";
import type { AuthSession } from "../lib/api-client/auth";
import { previewProfile } from "../lib/permissions/route-access";

export const previewSession: AuthSession = {
  user: previewProfile,
  csrfToken: "test-csrf-token",
};

export function renderWithProviders(
  ui: ReactElement,
  initialPath = "/app/requests",
  initialAuthSession: AuthSession | null = previewSession,
  locationState?: unknown,
): RenderResult {
  window.history.pushState({}, "Test page", initialPath);
  const initialEntry =
    locationState === undefined ? initialPath : { pathname: initialPath, state: locationState };
  return render(
    <AppProviders initialAuthSession={initialAuthSession}>
      <MemoryRouter initialEntries={[initialEntry]}>{ui}</MemoryRouter>
    </AppProviders>,
  );
}
