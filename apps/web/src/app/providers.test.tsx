import { QueryClient } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { previewSession } from "../test/test-utils";
import { AppProviders } from "./providers";
import { getQueryClient, resetQueryClientForTests } from "./query-client";
import { useAuth } from "../lib/auth/auth-context";
import type { AuthApi } from "../lib/api-client/auth";

function LogoutProbe() {
  const { logout } = useAuth();
  return (
    <button type="button" onClick={() => void logout()}>
      Logout
    </button>
  );
}

function fakeClient(overrides: Partial<AuthApi>): AuthApi {
  return overrides as AuthApi;
}

beforeEach(() => {
  resetQueryClientForTests();
});

test("logout clears protected query cache through the app provider", async () => {
  const user = userEvent.setup();
  const client = fakeClient({
    logout: vi.fn().mockResolvedValue(undefined),
  });
  const queryClient = getQueryClient();
  queryClient.setQueryData(["store-product", "restricted"], { title: "Restricted product" });

  render(
    <AppProviders authApi={client} initialAuthSession={previewSession}>
      <LogoutProbe />
    </AppProviders>,
  );

  await user.click(screen.getByRole("button", { name: "Logout" }));

  expect(queryClient).toBeInstanceOf(QueryClient);
  expect(queryClient.getQueryData(["store-product", "restricted"])).toBeUndefined();
});
