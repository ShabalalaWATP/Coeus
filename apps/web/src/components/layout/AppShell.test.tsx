import { axe } from "jest-axe";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { AppShell } from "./AppShell";
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

test("renders the expected shell landmarks and navigation", () => {
  renderWithProviders(<AppShell profile={previewProfile} />);

  expect(screen.getByLabelText("Primary navigation")).toBeVisible();
  expect(screen.getByLabelText("Istari workspace")).toBeVisible();
  expect(screen.getByRole("combobox", { name: "Command" })).toBeVisible();
  expect(screen.getByRole("button", { name: "Notifications" })).toBeVisible();
  expect(screen.getByRole("button", { name: "Profile" })).toBeVisible();
});

test("marks only the most specific navigation item active", () => {
  renderWithProviders(
    <AppShell profile={{ ...previewProfile, roles: ["RFA Manager"] }} />,
    "/store/my-products",
  );

  expect(screen.getByRole("link", { name: "Intelligence Store" })).not.toHaveAttribute(
    "aria-current",
  );
  expect(screen.getByRole("link", { name: "My Products" })).toHaveAttribute("aria-current", "page");
});

test("has no automated accessibility violations in the shell", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(() => new Promise(() => undefined)),
  );
  const { container } = renderWithProviders(<AppShell profile={previewProfile} />);

  expect(await axe(container)).toHaveNoViolations();
});

test("logs out through the shell command bar", async () => {
  const user = userEvent.setup();
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve({ notifications: [], unread: 0 }),
  });
  vi.stubGlobal("fetch", fetchMock);
  renderWithProviders(<AppShell profile={previewProfile} />);

  await user.click(screen.getByRole("button", { name: "Log out" }));

  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8001/api/v1/auth/logout",
      expect.objectContaining({ method: "POST" }),
    ),
  );
});
