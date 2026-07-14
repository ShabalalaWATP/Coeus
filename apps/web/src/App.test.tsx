import { render, screen } from "@testing-library/react";

import { App } from "./App";
import { previewSession } from "./test/test-utils";

test("renders the app shell at the default route", async () => {
  await import("./features/requests/RequestsPage");
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

  expect(
    await screen.findByRole("heading", { name: "My Requests" }, { timeout: 5_000 }),
  ).toBeVisible();
  expect(screen.getByText("Knowledge-led intelligence tasking")).toBeVisible();
});
