import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import TeamsPage from "./TeamsPage";
import { resetQueryClientForTests } from "../../app/query-client";
import type { OrgTeam } from "../../lib/api-client/teams";
import { renderWithProviders } from "../../test/test-utils";

const team: OrgTeam = {
  id: "team-1",
  name: "RFA Assessment Team",
  kind: "rfa",
  capabilityTeamId: "RFA-MARITIME",
  members: [
    {
      userId: "preview-user",
      username: "rfa.manager@example.test",
      displayName: "RFA Manager",
      isManager: true,
      title: "Team Lead",
      specialisms: [],
      bio: "Leads the assessment team.",
    },
    {
      userId: "analyst-1",
      username: "analyst@example.test",
      displayName: "Intelligence Analyst",
      isManager: false,
      title: "Senior Imagery Analyst",
      specialisms: ["IMINT", "Maritime"],
      bio: "Maritime imagery specialist.",
    },
  ],
};

const availability = {
  teamId: "team-1",
  date: "2026-07-10",
  members: 2,
  onLeave: 1,
  onTaskCalendar: 0,
  assignedLive: 1,
  onTask: 1,
  free: 0,
};

const entry = {
  id: "entry-1",
  userId: "analyst-1",
  date: "2026-07-15",
  status: "leave" as const,
  note: "Annual leave.",
  createdByUserId: "analyst-1",
};

const profile = {
  userId: "preview-user",
  title: "Team Lead",
  specialisms: ["Management"],
  bio: "MOCK DATA ONLY.",
  updatedAt: "2026-07-10T00:00:00Z",
};

function teamsFetch(overrides: Record<string, unknown> = {}) {
  return vi.fn((url: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    const respond = (payload: unknown, status = 200) =>
      Promise.resolve({ ok: status < 400, status, json: () => Promise.resolve(payload) });
    if (url.endsWith("/api/v1/teams")) {
      return respond(overrides.teams ?? { teams: [team] });
    }
    if (url.includes("/availability")) {
      return respond(availability);
    }
    if (url.includes("/calendar?")) {
      return respond(overrides.calendar ?? { entries: [entry] });
    }
    if (url.includes("/calendar/") && method === "DELETE") {
      return respond(null, 204);
    }
    if (url.includes("/calendar") && method === "POST") {
      return overrides.addEntryFails
        ? respond({ error: { code: "server_error", message: "Failed." } }, 500)
        : respond({ ...entry, id: "entry-2" });
    }
    if (url.includes("/member-candidates")) {
      return respond(
        overrides.directory ?? {
          users: [
            {
              userId: "user-9",
              username: "colleague@example.test",
              displayName: "Colleague",
              isManager: false,
              title: "Liaison",
              specialisms: [],
              bio: "",
            },
          ],
        },
      );
    }
    if (url.includes("/members/") && method === "DELETE") {
      return respond(team);
    }
    if (url.includes("/members") && method === "POST") {
      return overrides.addMemberFails
        ? respond({ error: { code: "server_error", message: "Failed." } }, 500)
        : respond(team);
    }
    if (url.includes("/users/me/profile")) {
      return respond(profile);
    }
    return respond({});
  });
}

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
  expect(await screen.findByText("Annual leave.")).toBeVisible();
});

test("adds a calendar entry for a team member", async () => {
  const fetchMock = teamsFetch();
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<TeamsPage />, "/teams");

  await screen.findByText("Annual leave.");
  await userEvent.selectOptions(screen.getByLabelText("Member"), "analyst-1");
  await userEvent.selectOptions(screen.getByLabelText("Status"), "leave");
  await userEvent.click(screen.getByRole("button", { name: "Add entry" }));

  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8001/api/v1/teams/team-1/calendar",
      expect.objectContaining({ method: "POST" }),
    ),
  );
});

test("removes a calendar entry it may manage", async () => {
  const fetchMock = teamsFetch();
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<TeamsPage />, "/teams");

  await userEvent.click(
    await screen.findByRole("button", {
      name: "Remove entry for Intelligence Analyst on 2026-07-15",
    }),
  );

  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8001/api/v1/teams/team-1/calendar/entry-1",
      expect.objectContaining({ method: "DELETE" }),
    ),
  );
});

test("manager adds a member from directory suggestions and removes members", async () => {
  const fetchMock = teamsFetch();
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<TeamsPage />, "/teams");

  await userEvent.type(await screen.findByLabelText("Add member"), "colleague");
  await userEvent.click(await screen.findByRole("button", { name: /Colleague/ }));
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

test("marks today's group and shows the day summary", async () => {
  const now = new Date();
  const today = [now.getFullYear(), now.getMonth() + 1, now.getDate()]
    .map((part, index) => String(part).padStart(index === 0 ? 4 : 2, "0"))
    .join("-");
  vi.stubGlobal("fetch", teamsFetch({ calendar: { entries: [{ ...entry, date: today }] } }));

  renderWithProviders(<TeamsPage />, "/teams");

  expect(await screen.findByText("1 on leave")).toBeVisible();
  expect(screen.getAllByText("Today").some((element) => element.tagName === "SPAN")).toBe(true);
});

test("shows an empty calendar and surfaces entry failures", async () => {
  vi.stubGlobal("fetch", teamsFetch({ addEntryFails: true, calendar: { entries: [] } }));

  renderWithProviders(<TeamsPage />, "/teams");

  expect(await screen.findByText("No entries in this fortnight.")).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Add entry" }));
  expect(await screen.findByText("Failed.")).toBeVisible();
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
