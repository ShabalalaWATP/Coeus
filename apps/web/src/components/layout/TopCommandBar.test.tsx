import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { TopCommandBar } from "./TopCommandBar";
import { previewProfile } from "../../lib/permissions/route-access";
import { renderWithProviders } from "../../test/test-utils";

test("toggles the theme from the command bar", async () => {
  const user = userEvent.setup();
  renderWithProviders(<TopCommandBar profile={previewProfile} />);

  await user.click(screen.getByRole("button", { name: "Switch to light theme" }));

  expect(document.documentElement.dataset.theme).toBe("light");
  expect(screen.getByRole("button", { name: "Switch to dark theme" })).toBeVisible();
});
