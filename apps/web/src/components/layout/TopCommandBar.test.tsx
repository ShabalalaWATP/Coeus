import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { TopCommandBar } from "./TopCommandBar";
import { previewProfile } from "../../lib/permissions/route-access";
import { renderWithProviders } from "../../test/test-utils";

test("toggles the theme from the command bar", async () => {
  const user = userEvent.setup();
  renderWithProviders(<TopCommandBar onLogout={vi.fn()} profile={previewProfile} />);

  await user.click(screen.getByRole("button", { name: "Switch to light theme" }));

  expect(document.documentElement.dataset.theme).toBe("light");
  expect(screen.getByRole("button", { name: "Switch to dark theme" })).toBeVisible();
});

test("calls logout from the command bar", async () => {
  const user = userEvent.setup();
  const onLogout = vi.fn();
  renderWithProviders(<TopCommandBar onLogout={onLogout} profile={previewProfile} />);

  await user.click(screen.getByRole("button", { name: "Log out" }));

  expect(onLogout).toHaveBeenCalledTimes(1);
});
