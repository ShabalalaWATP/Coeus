import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useLocation } from "react-router-dom";

import { TopCommandBar } from "./TopCommandBar";
import { resetQueryClientForTests } from "../../app/query-client";
import { previewProfile } from "../../lib/permissions/route-access";
import { renderWithProviders } from "../../test/test-utils";

beforeEach(() => {
  resetQueryClientForTests();
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ notifications: [], unread: 0 }),
    }),
  );
});

afterEach(() => {
  vi.restoreAllMocks();
});

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

test("links to the change password page from the profile panel", async () => {
  const user = userEvent.setup();
  renderWithProviders(<TopCommandBar onLogout={vi.fn()} profile={previewProfile} />);

  await user.click(screen.getByRole("button", { name: "Profile" }));

  const changePassword = screen.getByRole("link", { name: "Change password" });
  expect(changePassword).toHaveAttribute("href", "/account/password");
  await user.click(changePassword);
  expect(screen.queryByLabelText("Profile panel")).not.toBeInTheDocument();
});

test("closes popovers on Escape and on outside clicks", async () => {
  const user = userEvent.setup();
  renderWithProviders(<TopCommandBar onLogout={vi.fn()} profile={previewProfile} />);

  await user.click(screen.getByRole("button", { name: "Profile" }));
  expect(screen.getByLabelText("Profile panel")).toBeVisible();
  await user.keyboard("{Escape}");
  expect(screen.queryByLabelText("Profile panel")).not.toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "Notifications" }));
  expect(screen.getByLabelText("Notifications panel")).toBeVisible();
  await user.click(document.body);
  expect(screen.queryByLabelText("Notifications panel")).not.toBeInTheDocument();
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
  await user.click(screen.getByRole("option", { name: "Audit" }));

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

test("focuses the command input with Ctrl+K and clears it with Escape", async () => {
  const user = userEvent.setup();
  renderWithProviders(<TopCommandBar onLogout={vi.fn()} profile={previewProfile} />);

  await user.keyboard("{Control>}k{/Control}");
  expect(screen.getByLabelText("Command")).toHaveFocus();

  await user.type(screen.getByLabelText("Command"), "Audit");
  expect(screen.getByRole("option", { name: "Audit" })).toBeVisible();
  await user.keyboard("{Escape}");
  expect(screen.getByLabelText("Command")).toHaveValue("");
});

test("moves through command results with arrow keys", async () => {
  const user = userEvent.setup();
  renderWithProviders(
    <>
      <TopCommandBar onLogout={vi.fn()} profile={previewProfile} />
      <LocationProbe />
    </>,
    "/",
  );

  await user.type(screen.getByLabelText("Command"), "Analytics");
  const options = screen.getAllByRole("option");
  expect(options[0]).toHaveAttribute("aria-selected", "true");
  await user.keyboard("{ArrowUp}");
  expect(options.at(-1)).toHaveAttribute("aria-selected", "true");
  await user.keyboard("{ArrowDown}{ArrowDown}{Enter}");
  expect(screen.getByTestId("location")).toHaveTextContent("/collection/analytics");
});

function LocationProbe() {
  const location = useLocation();
  return <span data-testid="location">{location.pathname}</span>;
}
