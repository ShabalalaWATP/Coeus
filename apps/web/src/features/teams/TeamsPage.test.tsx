import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import TeamsPage from "./TeamsPage";
import { teamsFetch } from "./teams-page.fixtures";
import { resetQueryClientForTests } from "../../app/query-client";
import { renderWithProviders } from "../../test/test-utils";

beforeEach(() => {
  resetQueryClientForTests();
  vi.stubGlobal(
    "confirm",
    vi.fn(() => true),
  );
});

afterEach(() => {
  vi.restoreAllMocks();
});

test("shows the roster, availability and calendar for the manager", async () => {
  vi.stubGlobal("fetch", teamsFetch());

  renderWithProviders(<TeamsPage />, "/teams");

  expect(await screen.findByText("RFA Assessment Team")).toBeVisible();
  expect(screen.getByText("Manager")).toBeVisible();
  expect(screen.getByText("Senior Imagery Analyst")).toBeVisible();
  expect(screen.getByText("IMINT, Maritime")).toBeVisible();
  expect(await screen.findByText("Availability today")).toBeVisible();
  expect(screen.getByText("Total roster").nextElementSibling).toHaveTextContent("2");
  expect(screen.getByText("Active people").nextElementSibling).toHaveTextContent("2");
  expect(screen.getByText("Assignable analysts").nextElementSibling).toHaveTextContent("1");
  expect(screen.getByText("Free analysts").nextElementSibling).toHaveTextContent("0");
  expect(screen.getByText("Other duties").nextElementSibling).toHaveTextContent("1");
  expect(await screen.findByTitle("Intelligence Analyst: On leave · Annual leave.")).toBeVisible();
});

test("a failed team list is reported and nothing else is rendered", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(() =>
      Promise.resolve({
        ok: false,
        status: 500,
        json: () => Promise.resolve({ error: { code: "server_error", message: "Failed." } }),
      }),
    ),
  );

  renderWithProviders(<TeamsPage />, "/teams");

  expect(await screen.findByRole("button", { name: "Retry" }, { timeout: 5_000 })).toBeVisible();
  expect(screen.queryByText("Availability today")).not.toBeInTheDocument();
  expect(screen.queryByRole("navigation", { name: "Your teams" })).not.toBeInTheDocument();
});

test("an unauthenticated render still explains that no team is assigned", async () => {
  vi.stubGlobal("fetch", teamsFetch({ teams: { teams: [] } }));

  renderWithProviders(<TeamsPage />, "/teams", null);

  expect(await screen.findByText("You are not assigned to a team")).toBeVisible();
});

test("a posted member is never told they have no team", async () => {
  const fetchMock = teamsFetch({ teams: { teams: [] } });
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) =>
      url.includes("/organisation/workspaces")
        ? Promise.resolve({
            ok: true,
            status: 200,
            json: () =>
              Promise.resolve({
                truncated: false,
                workspaces: [
                  {
                    unit: {
                      id: "3c27baa4-c889-53e4-98f0-4fda7d6cc9e5",
                      name: "DI NCGIA",
                      shortName: "NCGIA",
                      category: "delivery_team",
                      parentId: null,
                      timeZone: "Europe/London",
                      description: null,
                      isActive: true,
                      version: 1,
                      validFrom: "2026-08-01T00:00:00Z",
                      validUntil: null,
                    },
                    relationship: "home",
                    managed: false,
                    includeDescendants: false,
                    canViewAvailability: false,
                    canViewDetail: false,
                    canViewTasks: false,
                    canViewPeople: true,
                    canViewCapabilities: false,
                    canConfigure: false,
                    planningGrantId: null,
                  },
                ],
              }),
          })
        : fetchMock(url, init),
    ),
  );

  renderWithProviders(<TeamsPage />, "/teams");

  expect(await screen.findByRole("heading", { name: "DI NCGIA" })).toBeVisible();
  expect(screen.queryByText("You are not assigned to a team")).not.toBeInTheDocument();
  expect(
    screen.queryByText("Workspace views are not included in your authority for this team."),
  ).not.toBeInTheDocument();
});

test("a second team is offered as a switcher and selecting it changes the roster", async () => {
  const first = {
    id: "team-1",
    name: "RFA Assessment Team",
    kind: "rfa",
    capabilityTeamId: null,
    members: [],
  };
  const second = { ...first, id: "team-2", name: "Collection Management Team", kind: "cm" };
  vi.stubGlobal("fetch", teamsFetch({ teams: { teams: [first, second] } }));

  renderWithProviders(<TeamsPage />, "/teams");

  const switcher = await screen.findByRole("navigation", { name: "Your teams" });
  expect(await screen.findByRole("heading", { name: "RFA Assessment Team" })).toBeVisible();

  await userEvent.click(
    within(switcher).getByRole("button", { name: "Collection Management Team" }),
  );

  expect(await screen.findByRole("heading", { name: "Collection Management Team" })).toBeVisible();
  expect(
    within(switcher).getByRole("button", { name: "Collection Management Team" }),
  ).toHaveAttribute("aria-pressed", "true");
});

test("an availability failure is reported without hiding the roster", async () => {
  const fetchMock = vi.fn((url: string, init?: RequestInit) => {
    if (url.includes("/availability")) {
      return Promise.resolve({
        ok: false,
        status: 500,
        json: () => Promise.resolve({ error: { code: "server_error", message: "Failed." } }),
      });
    }
    return teamsFetch()(url, init);
  });
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<TeamsPage />, "/teams");

  expect(await screen.findByRole("heading", { name: "RFA Assessment Team" })).toBeVisible();
  // The shared client retries once before reporting, so allow for that delay.
  expect(await screen.findByRole("button", { name: "Retry" }, { timeout: 5_000 })).toBeVisible();
  expect(screen.queryByText("Availability today")).not.toBeInTheDocument();
});

test("manager adds a member from directory suggestions and removes members", async () => {
  const fetchMock = teamsFetch();
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<TeamsPage />, "/teams");

  await userEvent.type(await screen.findByLabelText("Add member"), "colleague");
  await userEvent.click(
    await screen.findByRole("button", { name: /Colleague/ }, { timeout: 5_000 }),
  );
  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8001/api/v1/teams/team-1/members",
      expect.objectContaining({
        body: JSON.stringify({ userId: "user-9" }),
        method: "POST",
      }),
    ),
  );

  await userEvent.click(screen.getByRole("button", { name: "Remove Intelligence Analyst" }));
  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8001/api/v1/teams/team-1/members/analyst-1",
      expect.objectContaining({ method: "DELETE" }),
    ),
  );
});

test("tells the manager when a search matches nobody addable", async () => {
  const fetchMock = teamsFetch({
    directory: { users: [] },
  });
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<TeamsPage />, "/teams");

  await userEvent.type(await screen.findByLabelText("Add member"), "nobody");

  expect(await screen.findByText("No matching users found.")).toBeVisible();
  expect(fetchMock).not.toHaveBeenCalledWith(
    "http://127.0.0.1:8001/api/v1/teams/team-1/members",
    expect.objectContaining({ method: "POST" }),
  );
});

test("surfaces a failure when adding a member is rejected", async () => {
  vi.stubGlobal("fetch", teamsFetch({ addMemberFails: true }));

  renderWithProviders(<TeamsPage />, "/teams");

  await userEvent.type(await screen.findByLabelText("Add member"), "colleague");
  await userEvent.click(await screen.findByRole("button", { name: /Colleague/ }));
  expect(await screen.findByText("Failed.")).toBeVisible();
});

test("shows an empty state for users on no team", async () => {
  vi.stubGlobal("fetch", teamsFetch({ teams: { teams: [] } }));

  renderWithProviders(<TeamsPage />, "/teams");

  expect(await screen.findByText("You are not assigned to a team")).toBeVisible();
});
