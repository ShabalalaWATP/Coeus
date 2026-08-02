import { render, screen } from "@testing-library/react";

import { NoMatchConsentPanel } from "./NoMatchConsentPanel";

test("disables every decision while a refined search is starting", () => {
  render(
    <NoMatchConsentPanel
      canRefine
      isPending={false}
      isRefining
      onConsent={vi.fn()}
      onRefine={vi.fn()}
    />,
  );

  expect(screen.getByRole("button", { name: "Searching…" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Continue to the JIOC Agent" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Close as unfulfilled" })).toBeDisabled();
});
