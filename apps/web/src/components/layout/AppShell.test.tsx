import { axe } from "jest-axe";
import { screen } from "@testing-library/react";

import { AppShell } from "./AppShell";
import { previewProfile } from "../../lib/permissions/route-access";
import { renderWithProviders } from "../../test/test-utils";

test("renders the expected shell landmarks and navigation", () => {
  renderWithProviders(<AppShell profile={previewProfile} />);

  expect(screen.getByLabelText("Primary navigation")).toBeVisible();
  expect(screen.getByLabelText("Coeus workspace")).toBeVisible();
  expect(screen.getByRole("searchbox", { name: "Command" })).toBeVisible();
  expect(screen.getByRole("button", { name: "Notifications" })).toBeVisible();
  expect(screen.getByRole("button", { name: "Profile" })).toBeVisible();
});

test("has no automated accessibility violations in the shell", async () => {
  const { container } = renderWithProviders(<AppShell profile={previewProfile} />);

  expect(await axe(container)).toHaveNoViolations();
});
