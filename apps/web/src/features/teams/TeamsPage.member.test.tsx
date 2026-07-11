import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import TeamsPage from "./TeamsPage";
import { resetQueryClientForTests } from "../../app/query-client";
import type { OrgTeam } from "../../lib/api-client/teams";
import { renderWithProviders } from "../../test/test-utils";

const rfaTeam: OrgTeam = {
  id: "team-1",
  name: "RFA Assessment Team",
  kind: "rfa",
  capabilityTeamId: null,
  members: [
    {
      userId: "manager-1",
      username: "rfa.manager@example.test",
      displayName: "RFA Manager",
      isManager: true,
      title: "Team Lead",
      specialisms: [],
      bio: "Team manager.",
    },
    {
      userId: "preview-user",
      username: "analyst@example.test",
      displayName: "Intelligence Analyst",
      isManager: false,
      title: "",
      specialisms: [],
      bio: "Analyst profile.",
    },
  ],
};

const cmTeam: OrgTeam = {
  ...rfaTeam,
  id: "team-2",
  name: "Collection Management Team",
  kind: "cm",
};

const managerEntry = {
  id: "entry-9",
  userId: "manager-1",
  date: "2026-07-16",
  status: "on_task" as const,
  note: "",
  createdByUserId: "manager-1",
};

function memberFetch({ calendarFails = false } = {}) {
  return vi.fn((url: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    const respond = (payload: unknown, status = 200) =>
      Promise.resolve({ ok: status < 400, status, json: () => Promise.resolve(payload) });
    if (url.endsWith("/api/v1/teams")) {
      return respond({ teams: [rfaTeam, cmTeam] });
    }
    if (url.includes("/availability")) {
      return respond({
        teamId: "team-1",
        date: "2026-07-10",
        members: 2,
        onLeave: 0,
        onTaskCalendar: 1,
        assignedLive: 0,
        free: 1,
      });
    }
    if (url.includes("/calendar?")) {
      return calendarFails
        ? respond({ error: { code: "server_error", message: "Failed." } }, 500)
        : respond({ entries: [managerEntry] });
    }
    if (url.includes("/calendar") && method === "POST") {
      return respond({ ...managerEntry, id: "entry-10", userId: "preview-user" });
    }
    if (url.includes("/users/me/profile") && method === "PUT") {
      return respond({ error: { code: "server_error", message: "Failed." } }, 500);
    }
    if (url.includes("/users/me/profile")) {
      return respond({
        userId: "preview-user",
        title: "",
        specialisms: [],
        bio: "",
        updatedAt: "2026-07-10T00:00:00Z",
      });
    }
    return respond({});
  });
}

beforeEach(() => {
  resetQueryClientForTests();
});

afterEach(() => {
  vi.restoreAllMocks();
});

test("members see the roster read-only, switch teams and log their own time", async () => {
  const fetchMock = memberFetch();
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<TeamsPage />, "/teams");

  expect(await screen.findByRole("heading", { name: "RFA Assessment Team" })).toBeVisible();
  // No management controls for a plain member.
  expect(screen.queryByLabelText("Add member")).not.toBeInTheDocument();
  expect(screen.queryByLabelText("Member")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Remove RFA Manager" })).not.toBeInTheDocument();
  // Another member's entry is not removable by this member.
  expect(
    screen.queryByRole("button", { name: /Remove entry for RFA Manager/ }),
  ).not.toBeInTheDocument();

  // The member logs their own availability without picking a member.
  await userEvent.selectOptions(screen.getByLabelText("Status"), "available");
  await userEvent.click(screen.getByRole("button", { name: "Add entry" }));
  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8001/api/v1/teams/team-1/calendar",
      expect.objectContaining({ method: "POST" }),
    ),
  );
  const entryCall = fetchMock.mock.calls.find(
    ([url, init]) => String(url).endsWith("/calendar") && init?.method === "POST",
  );
  const rawBody = entryCall?.[1]?.body;
  expect(typeof rawBody).toBe("string");
  const entryBody: unknown = JSON.parse(rawBody as string);
  expect(entryBody).toMatchObject({ userId: "preview-user", status: "available" });

  // Being on two teams shows the switcher.
  await userEvent.click(screen.getByRole("button", { name: "Collection Management Team" }));
  expect(await screen.findByRole("heading", { name: "Collection Management Team" })).toBeVisible();
});

test("surfaces calendar load and profile save failures", async () => {
  vi.stubGlobal("fetch", memberFetch({ calendarFails: true }));

  renderWithProviders(<TeamsPage />, "/teams");

  expect(
    await screen.findByText("The calendar could not be loaded.", undefined, { timeout: 5000 }),
  ).toBeVisible();

  await userEvent.type(await screen.findByLabelText("Title"), "Analyst");
  await userEvent.click(screen.getByRole("button", { name: "Save profile" }));
  expect(await screen.findByText("Failed.")).toBeVisible();
});

test("shows a retryable error when the team list cannot load", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: () => Promise.resolve({ error: { code: "server_error", message: "Failed." } }),
    }),
  );

  renderWithProviders(<TeamsPage />, "/teams");

  expect(
    await screen.findByText("Unable to load data", undefined, { timeout: 5000 }),
  ).toBeVisible();
});
