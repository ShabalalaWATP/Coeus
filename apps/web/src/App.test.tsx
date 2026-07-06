import { render, screen, waitFor } from "@testing-library/react";

import { App } from "./App";
import { previewSession } from "./test/test-utils";

test("renders the app shell at the default route", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      if (url.includes("/auth/me")) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              ...previewSession,
              user: { ...previewSession.user, defaultRoute: "/app/requests" },
            }),
        });
      }
      if (url.includes("/feedback/requests")) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ requests: [] }) });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ tickets: [] }) });
    }),
  );
  window.history.pushState({}, "Home", "/");

  render(<App />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "My Requests" })).toBeVisible());
  expect(screen.getByText("Knowledge-led intelligence tasking")).toBeVisible();
});
