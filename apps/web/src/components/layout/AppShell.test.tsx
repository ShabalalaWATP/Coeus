import { axe } from "jest-axe";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { AppShell } from "./AppShell";
import { previewProfile } from "../../lib/permissions/route-access";
import { renderWithProviders } from "../../test/test-utils";

test("renders the expected shell landmarks and navigation", () => {
  renderWithProviders(<AppShell profile={previewProfile} />);

  expect(screen.getByLabelText("Primary navigation")).toBeVisible();
  expect(screen.getByLabelText("Istari workspace")).toBeVisible();
  expect(screen.getByRole("searchbox", { name: "Command" })).toBeVisible();
  expect(screen.getByRole("button", { name: "Notifications" })).toBeVisible();
  expect(screen.getByRole("button", { name: "Profile" })).toBeVisible();
});

test("has no automated accessibility violations in the shell", async () => {
  const { container } = renderWithProviders(<AppShell profile={previewProfile} />);

  expect(await axe(container)).toHaveNoViolations();
});

test("logs out through the shell command bar", async () => {
  const user = userEvent.setup();
  const fetchMock = vi.fn().mockResolvedValue({ ok: true });
  vi.stubGlobal("fetch", fetchMock);
  renderWithProviders(<AppShell profile={previewProfile} />);

  await user.click(screen.getByRole("button", { name: "Log out" }));

  await waitFor(() => expect(fetchMock).toHaveBeenCalled());
});
