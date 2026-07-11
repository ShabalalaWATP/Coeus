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
      username: "analyst.geo@example.test",
      displayName: "Geospatial Assessment Analyst",
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
    teams: [{ id: "team-1", name: "RFA Assessment Team", kind: "rfa", members: [] }],
  };
  const availability = {
    teamId: "team-1",
    date: "2026-07-10",
    members: 6,
    onLeave: 1,
    onTaskCalendar: 0,
    assignedLive: 2,
    free: 3,
  };
  const fetchMock = vi.fn((url: string) =>
    Promise.resolve({
      ok: true,
      json: () =>
        Promise.resolve(
          url.includes("/candidates")
            ? candidates
            : url.endsWith("/api/v1/teams")
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
  await userEvent.click(screen.getByRole("checkbox", { name: "Geospatial Assessment Analyst" }));
  await userEvent.type(screen.getByLabelText("Team name"), "Maritime Assessment Cell");
  await userEvent.type(
    screen.getByLabelText("Work packages (semicolon separated)"),
    "Validate scope; Draft assessment ;",
  );
  await userEvent.click(screen.getByRole("button", { name: "Assign analysts" }));

  await waitFor(() => expect(onAssigned).toHaveBeenCalledWith(assignedTask));
  expect(fetchMock).toHaveBeenCalledWith(
    "http://127.0.0.1:8001/api/v1/analyst/tasks/ticket-1/assign",
    {
      body: JSON.stringify({
        analystUserIds: ["analyst-1", "analyst-2"],
        teamName: "Maritime Assessment Cell",
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
    vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve(candidates) }),
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
    vi.fn().mockResolvedValue({
      ok: false,
      status: 403,
      json: () => Promise.resolve({ error: { code: "forbidden", message: "Denied." } }),
    }),
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
      url.includes("/candidates") || url.endsWith("/api/v1/teams")
        ? {
            ok: true,
            json: () => Promise.resolve(url.includes("/candidates") ? candidates : { teams: [] }),
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
