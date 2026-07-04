import { render, screen, waitFor } from "@testing-library/react";

import { App } from "./App";

test("renders the app shell at the default route", async () => {
  window.history.pushState({}, "Home", "/");

  render(<App />);

  await waitFor(() => expect(screen.getByRole("heading", { name: "Requests" })).toBeVisible());
  expect(screen.getByText("Knowledge-led intelligence tasking")).toBeVisible();
});
