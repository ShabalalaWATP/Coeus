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
  ],
};

beforeEach(() => {
  resetQueryClientForTests();
});

afterEach(() => {
  vi.restoreAllMocks();
});

test("assigns an analyst with custom work packages", async () => {
  const onAssigned = vi.fn();
  const assignedTask = { ticketId: "ticket-1", state: "ANALYST_IN_PROGRESS" };
  const fetchMock = vi.fn((url: string) =>
    Promise.resolve({
      ok: true,
      json: () => Promise.resolve(url.includes("/candidates") ? candidates : assignedTask),
    }),
  );
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(
    <AssignAnalystPanel csrfToken="test-csrf-token" onAssigned={onAssigned} ticketId="ticket-1" />,
    "/rfa/queue",
  );

  await screen.findByRole("option", { name: "Intelligence Analyst" });
  await userEvent.selectOptions(screen.getByLabelText("Analyst"), "analyst-1");
  await userEvent.type(screen.getByLabelText("Team name"), "Maritime Assessment Cell");
  await userEvent.type(
    screen.getByLabelText("Work packages (semicolon separated)"),
    "Validate scope; Draft assessment ;",
  );
  await userEvent.click(screen.getByRole("button", { name: "Assign analyst" }));

  await waitFor(() => expect(onAssigned).toHaveBeenCalledWith(assignedTask));
  expect(fetchMock).toHaveBeenCalledWith(
    "http://127.0.0.1:8001/api/v1/analyst/tasks/ticket-1/assign",
    {
      body: JSON.stringify({
        analystUserId: "analyst-1",
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

  expect(await screen.findByRole("button", { name: "Assign analyst" })).toBeDisabled();
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
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(candidates) })
    .mockResolvedValue({
      ok: false,
      status: 409,
      json: () => Promise.resolve({ error: { code: "invalid_ticket_state", message: "No." } }),
    });
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(
    <AssignAnalystPanel csrfToken="test-csrf-token" onAssigned={vi.fn()} ticketId="ticket-1" />,
    "/rfa/queue",
  );

  await screen.findByRole("option", { name: "Intelligence Analyst" });
  await userEvent.selectOptions(screen.getByLabelText("Analyst"), "analyst-1");
  await userEvent.click(screen.getByRole("button", { name: "Assign analyst" }));

  expect(
    await screen.findByText("Assignment failed. Confirm the ticket is still awaiting assignment."),
  ).toBeVisible();
});
