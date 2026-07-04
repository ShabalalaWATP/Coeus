import { render, screen, waitFor } from "@testing-library/react";

import { App } from "./App";
import { previewSession } from "./test/test-utils";

test("renders the app shell at the default route", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          ...previewSession,
          user: { ...previewSession.user, defaultRoute: "/app/requests" },
        }),
    }),
  );
  window.history.pushState({}, "Home", "/");

  render(<App />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "Requests" })).toBeVisible());
  expect(screen.getByText("Knowledge-led intelligence tasking")).toBeVisible();
});
