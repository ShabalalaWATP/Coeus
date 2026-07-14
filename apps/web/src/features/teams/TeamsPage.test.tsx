import { screen, waitFor } from "@testing-library/react";
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
  expect(screen.getByText("Free").nextElementSibling).toHaveTextContent("0");
  expect(screen.getByText("Other duties").nextElementSibling).toHaveTextContent("1");
  expect(await screen.findByTitle("Intelligence Analyst: On leave · Annual leave.")).toBeVisible();
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

test("saves the caller's own profile", async () => {
  const fetchMock = teamsFetch();
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<TeamsPage />, "/teams");

  const titleInput = await screen.findByLabelText("Title");
  await waitFor(() => expect(titleInput).toHaveValue("Team Lead"));
  await userEvent.clear(titleInput);
  await userEvent.type(titleInput, "Head of Assessments");
  await userEvent.click(screen.getByRole("button", { name: "Save profile" }));

  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8001/api/v1/users/me/profile",
      expect.objectContaining({
        body: JSON.stringify({
          title: "Head of Assessments",
          specialisms: ["Management"],
          bio: "MOCK DATA ONLY.",
        }),
        method: "PUT",
      }),
    ),
  );
  expect(await screen.findByText("Profile saved.")).toBeVisible();
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
