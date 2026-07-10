import { render, screen, waitFor } from "@testing-library/react";
import { RouterProvider } from "react-router-dom";

import { AppProviders } from "./providers";
import { resetQueryClientForTests } from "./query-client";
import { createAppRouter } from "./router";
import { productFixture } from "../features/store/store-test-fixtures";
import type { AuthSession } from "../lib/api-client/auth";
import { previewSession } from "../test/test-utils";

beforeEach(() => {
  resetQueryClientForTests();
  window.history.pushState({}, "Test page", "/");
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

test("allows product readers to open direct asset URLs without download access", async () => {
  const sessionWithoutDownloads: AuthSession = {
    ...previewSession,
    user: {
      ...previewSession.user,
      permissions: previewSession.user.permissions.filter(
        (permission) => permission !== "product:download",
      ),
    },
  };
  const fetchMock = vi.fn((input: RequestInfo | URL) => {
    const url = requestUrl(input);
    if (url.endsWith("/api/v1/notifications")) {
      return Promise.resolve(jsonResponse({ notifications: [], unread: 0 }));
    }
    if (url.endsWith("/api/v1/store/products/product-regional")) {
      return Promise.resolve(jsonResponse(productFixture));
    }
    return Promise.reject(new Error(`Unexpected request: ${url}`));
  });
  vi.stubGlobal("fetch", fetchMock);
  window.history.pushState(
    {},
    "Product asset",
    "/store/products/product-regional/assets/asset-brief",
  );

  render(
    <AppProviders initialAuthSession={sessionWithoutDownloads}>
      <RouterProvider router={createAppRouter()} />
    </AppProviders>,
  );

  expect(await screen.findByText("regional-brief.pdf")).toBeVisible();
  expect(screen.queryByRole("heading", { name: "Access denied" })).not.toBeInTheDocument();
  await waitFor(() =>
    expect(
      fetchMock.mock.calls.some(([input]) =>
        requestUrl(input).includes("/assets/asset-brief/access"),
      ),
    ).toBe(false),
  );
});

function jsonResponse(body: unknown) {
  return {
    ok: true,
    json: () => Promise.resolve(body),
  } as Response;
}

function requestUrl(input: RequestInfo | URL): string {
  if (typeof input === "string") {
    return input;
  }
  if (input instanceof URL) {
    return input.href;
  }
  return input.url;
}
