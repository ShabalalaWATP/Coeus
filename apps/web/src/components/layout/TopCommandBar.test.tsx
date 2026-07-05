import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useLocation } from "react-router-dom";

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

test("opens notifications and profile panels", async () => {
  const user = userEvent.setup();
  renderWithProviders(<TopCommandBar onLogout={vi.fn()} profile={previewProfile} />);

  await user.click(screen.getByRole("button", { name: "Notifications" }));
  expect(screen.getByLabelText("Notifications panel")).toHaveTextContent("No new notifications.");

  await user.click(screen.getByRole("button", { name: "Profile" }));
  expect(screen.getByLabelText("Profile panel")).toHaveTextContent(previewProfile.username);
});

test("navigates from command search results", async () => {
  const user = userEvent.setup();
  renderWithProviders(
    <>
      <TopCommandBar onLogout={vi.fn()} profile={previewProfile} />
      <LocationProbe />
    </>,
    "/",
  );

  await user.type(screen.getByLabelText("Command"), "Audit");
  await user.click(screen.getByRole("button", { name: "Audit" }));

  expect(screen.getByTestId("location")).toHaveTextContent("/audit");
});

test("supports enter key command navigation and no-match feedback", async () => {
  const user = userEvent.setup();
  renderWithProviders(
    <>
      <TopCommandBar onLogout={vi.fn()} profile={previewProfile} />
      <LocationProbe />
    </>,
    "/",
  );

  await user.type(screen.getByLabelText("Command"), "Not a route");
  expect(screen.getByText("No matching route.")).toBeVisible();
  await user.keyboard("{Enter}");
  expect(screen.getByTestId("location")).toHaveTextContent("/");

  await user.clear(screen.getByLabelText("Command"));
  await user.type(screen.getByLabelText("Command"), "Audit{Enter}");
  expect(screen.getByTestId("location")).toHaveTextContent("/audit");
});

function LocationProbe() {
  const location = useLocation();
  return <span data-testid="location">{location.pathname}</span>;
}
