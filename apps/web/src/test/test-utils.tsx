import { render, type RenderResult } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router-dom";

import { AppProviders } from "../app/providers";
import type { AuthSession, AuthUser } from "../lib/api-client/auth";

export const previewProfile: AuthUser = {
  id: "preview-user",
  username: "preview@example.test",
  displayName: "Sprint 2 Operator",
  roles: ["Administrator"],
  defaultRoute: "/admin/overview",
  passwordResetRequired: false,
  permissions: [
    "ticket:read_own",
    "user:read_self",
    "product:read",
    "product:search",
    "jioc:review",
    "jioc:oversight",
    "rfa:review",
    "rfa:add_product",
    "analytics:view_team",
    "collection:review",
    "collection:add_product",
    "analyst:work",
    "qc:review",
    "system:configure",
    "user:assign_role",
    "analytics:view_global",
    "acg:view",
    "audit:read",
    "product:create_existing",
    "product:download",
    "acg:create",
    "acg:update",
    "acg:assign_user",
    "chat:use",
    "ticket:create",
    "ticket:add_information",
    "ticket:add_comment",
    "rfi:search",
    "rfi:accept_product",
    "rfi:reject_product",
  ],
};

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
