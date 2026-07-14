import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { AssignAnalystPanel } from "./AssignAnalystPanel";
import { resetQueryClientForTests } from "../../app/query-client";
import { renderWithProviders } from "../../test/test-utils";

const candidates = {
  analysts: [
    {
      userId: "analyst-1",
      username: "analyst@example.test",
      displayName: "Intelligence Analyst",
    },
    {
      userId: "analyst-2",
      username: "analyst.4@example.test",
      displayName: "Che Adams",
    },
  ],
};

beforeEach(() => {
  resetQueryClientForTests();
});

afterEach(() => {
  vi.restoreAllMocks();
});

test("assigns multiple analysts with custom work packages", async () => {
  const onAssigned = vi.fn();
  const assignedTask = { ticketId: "ticket-1", state: "ANALYST_IN_PROGRESS" };
  const orgTeams = {
    teams: [{ teamId: "team-1", name: "RFA Assessment Team", kind: "rfa" }],
  };
  const availability = {
    teamId: "team-1",
    date: "2026-07-10",
    members: 6,
    onLeave: 1,
    onTaskCalendar: 0,
    assignedLive: 2,
    onTask: 3,
    free: 3,
  };
  const fetchMock = vi.fn((url: string) =>
    Promise.resolve({
      ok: true,
      json: () =>
        Promise.resolve(
          url.includes("/candidates")
            ? candidates
            : url.includes("/assignment-teams?")
              ? orgTeams
              : url.includes("/availability")
                ? availability
                : assignedTask,
        ),
    }),
  );
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(
    <AssignAnalystPanel
      csrfToken="test-csrf-token"
      onAssigned={onAssigned}
      route="rfa"
      ticketId="ticket-1"
    />,
    "/rfa/queue",
  );

  // Live availability guides the manager before they pick analysts.
  expect(
    await screen.findByText("3 of 6 team members are free today (2 on live tasks, 1 on leave)."),
  ).toBeVisible();

  await userEvent.click(await screen.findByRole("checkbox", { name: "Intelligence Analyst" }));
  await userEvent.click(screen.getByRole("checkbox", { name: "Che Adams" }));
  await userEvent.type(
    screen.getByLabelText("Work packages (one per line)"),
    "Validate scope; Draft assessment ;",
  );
  await userEvent.click(screen.getByRole("button", { name: "Assign analysts" }));

  await waitFor(() => expect(onAssigned).toHaveBeenCalledWith(assignedTask));
  expect(fetchMock).toHaveBeenCalledWith(
    "http://127.0.0.1:8001/api/v1/analyst/tasks/ticket-1/assign",
    {
      body: JSON.stringify({
        analystUserIds: ["analyst-1", "analyst-2"],
        teamId: "team-1",
        workPackages: ["Validate scope", "Draft assessment"],
      }),
      credentials: "include",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": "test-csrf-token" },
      method: "POST",
    },
  );
});

test("keeps the assign action disabled until an analyst is selected", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) =>
      Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve(
            url.includes("/assignment-teams?")
              ? { teams: [{ teamId: "team-1", name: "RFA Team", kind: "rfa" }] }
              : url.includes("/availability")
                ? {
                    teamId: "team-1",
                    date: "2026-07-10",
                    members: 2,
                    onLeave: 0,
                    onTaskCalendar: 0,
                    assignedLive: 0,
                    onTask: 0,
                    free: 2,
                  }
                : candidates,
          ),
      }),
    ),
  );

  renderWithProviders(
    <AssignAnalystPanel csrfToken="test-csrf-token" onAssigned={vi.fn()} ticketId="ticket-1" />,
    "/rfa/queue",
  );

  expect(await screen.findByRole("button", { name: "Assign analysts" })).toBeDisabled();

  // Unticking the only selected analyst disables the action again.
  const checkbox = await screen.findByRole("checkbox", { name: "Intelligence Analyst" });
  await userEvent.click(checkbox);
  expect(screen.getByRole("button", { name: "Assign analysts" })).toBeEnabled();
  await userEvent.click(checkbox);
  expect(screen.getByRole("button", { name: "Assign analysts" })).toBeDisabled();
});

test("shows a candidates error without leaking details", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) =>
      Promise.resolve(
        url.includes("/assignment-teams?")
          ? {
              ok: true,
              json: () =>
                Promise.resolve({ teams: [{ teamId: "team-1", name: "RFA Team", kind: "rfa" }] }),
            }
          : url.includes("/availability")
            ? {
                ok: true,
                json: () =>
                  Promise.resolve({
                    teamId: "team-1",
                    members: 1,
                    free: 1,
                    assignedLive: 0,
                    onLeave: 0,
                  }),
              }
            : {
                ok: false,
                status: 403,
                json: () => Promise.resolve({ error: { code: "forbidden", message: "Denied." } }),
              },
      ),
    ),
  );

  renderWithProviders(
    <AssignAnalystPanel csrfToken="test-csrf-token" onAssigned={vi.fn()} ticketId="ticket-1" />,
    "/rfa/queue",
  );

  expect(
    await screen.findByText(
      "Analyst candidates could not be loaded. Refresh to try again.",
      undefined,
      {
        timeout: 5000,
      },
    ),
  ).toBeVisible();
});

test("shows an assignment failure message", async () => {
  const fetchMock = vi.fn((url: string) =>
    Promise.resolve(
      url.includes("/candidates") ||
        url.includes("/assignment-teams?") ||
        url.includes("/availability")
        ? {
            ok: true,
            json: () =>
              Promise.resolve(
                url.includes("/candidates")
                  ? candidates
                  : url.includes("/assignment-teams?")
                    ? { teams: [{ teamId: "team-1", name: "RFA Team", kind: "rfa" }] }
                    : { teamId: "team-1", members: 1, free: 1, assignedLive: 0, onLeave: 0 },
              ),
          }
        : {
            ok: false,
            status: 409,
            json: () =>
              Promise.resolve({ error: { code: "invalid_ticket_state", message: "No." } }),
          },
    ),
  );
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(
    <AssignAnalystPanel csrfToken="test-csrf-token" onAssigned={vi.fn()} ticketId="ticket-1" />,
    "/rfa/queue",
  );

  await userEvent.click(await screen.findByRole("checkbox", { name: "Intelligence Analyst" }));
  await userEvent.click(screen.getByRole("button", { name: "Assign analysts" }));

  expect(
    await screen.findByText("Assignment failed. Confirm the ticket is still awaiting assignment."),
  ).toBeVisible();
});
