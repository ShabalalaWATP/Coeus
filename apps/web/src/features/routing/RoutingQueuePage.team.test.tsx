import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import RoutingQueuePage from "./RoutingQueuePage";
import { jsonResponse, queueWith, reviewedTicket, stubRoutingFetch } from "./routing-test-fixtures";
import { resetQueryClientForTests } from "../../app/query-client";
import { renderWithProviders } from "../../test/test-utils";
import type { RoutingTicket } from "../../lib/api-client/routing";

beforeEach(() => {
  resetQueryClientForTests();
});

afterEach(() => {
  vi.restoreAllMocks();
});

test("assigns analysts from the manager team queue and clears the ticket", async () => {
  const assignmentTicket: RoutingTicket = { ...reviewedTicket, state: "ANALYST_ASSIGNMENT" };
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(jsonResponse(queueWith([assignmentTicket])))
    .mockResolvedValueOnce(
      jsonResponse({
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
      }),
    )
    .mockResolvedValueOnce(jsonResponse({ ticketId: "ticket-1", state: "ANALYST_IN_PROGRESS" }));
  stubRoutingFetch(fetchMock);

  renderWithProviders(<RoutingQueuePage queue="rfa" />, "/rfa/queue");

  await userEvent.click(await screen.findByRole("button", { name: /TCK-0001/ }));
  await userEvent.click(await screen.findByRole("checkbox", { name: "Intelligence Analyst" }));
  await userEvent.click(screen.getByRole("checkbox", { name: "Che Adams" }));
  expect(screen.getByLabelText("Team")).toHaveValue("RFA-MARITIME");
  await userEvent.click(screen.getByRole("button", { name: "Assign analysts" }));

  expect(await screen.findByText("No tickets in this queue.")).toBeVisible();
  expect(screen.getByText("No ticket selected")).toBeVisible();
  expect(fetchMock).toHaveBeenNthCalledWith(
    3,
    "http://127.0.0.1:8001/api/v1/analyst/tasks/ticket-1/assign",
    expect.objectContaining({
      body: JSON.stringify({
        analystUserIds: ["analyst-1", "analyst-2"],
        teamId: "RFA-MARITIME",
        workPackages: [],
      }),
      method: "POST",
    }),
  );
});

test("manager approves submitted work onward to quality control", async () => {
  const approvalTicket: RoutingTicket = { ...reviewedTicket, state: "MANAGER_APPROVAL" };
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(jsonResponse(queueWith([approvalTicket])))
    .mockResolvedValueOnce(jsonResponse({ ...approvalTicket, state: "QC_REVIEW" }));
  stubRoutingFetch(fetchMock);

  renderWithProviders(<RoutingQueuePage queue="rfa" />, "/rfa/queue");

  await userEvent.click(await screen.findByRole("button", { name: /TCK-0001/ }));
  await userEvent.click(await screen.findByRole("button", { name: "Approve and send to QC" }));

  // Forwarded to QC, the ticket leaves the manager's team queue.
  expect(await screen.findByText("No tickets in this queue.")).toBeVisible();
  expect(fetchMock).toHaveBeenNthCalledWith(
    2,
    "http://127.0.0.1:8001/api/v1/routing/ticket-1/manager-approval",
    expect.objectContaining({ method: "POST" }),
  );
});

test("manager returns submitted work for rework with a reason", async () => {
  const approvalTicket: RoutingTicket = { ...reviewedTicket, state: "MANAGER_APPROVAL" };
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(jsonResponse(queueWith([approvalTicket])))
    .mockResolvedValueOnce(jsonResponse({ ...approvalTicket, state: "ANALYST_IN_PROGRESS" }));
  stubRoutingFetch(fetchMock);

  renderWithProviders(<RoutingQueuePage queue="rfa" />, "/rfa/queue");

  await userEvent.click(await screen.findByRole("button", { name: /TCK-0001/ }));
  const reworkButton = await screen.findByRole("button", { name: "Return for rework" });
  expect(reworkButton).toBeDisabled();
  await userEvent.type(screen.getByLabelText("Rework reason"), "Tighten the source trace.");
  await userEvent.click(reworkButton);

  await waitFor(() =>
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "http://127.0.0.1:8001/api/v1/routing/ticket-1/manager-rework",
      expect.objectContaining({
        body: JSON.stringify({ route: "rfa", reason: "Tighten the source trace." }),
        method: "POST",
      }),
    ),
  );
  // Rework keeps the ticket in the team queue.
  expect((await screen.findAllByText("Analyst in progress")).length).toBeGreaterThan(0);
});

test("surfaces a manager approval failure inline", async () => {
  const approvalTicket: RoutingTicket = { ...reviewedTicket, state: "MANAGER_APPROVAL" };
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(jsonResponse(queueWith([approvalTicket])))
    .mockResolvedValue({
      ok: false,
      status: 409,
      json: () => Promise.resolve({ error: { code: "invalid_ticket_state", message: "No." } }),
    });
  stubRoutingFetch(fetchMock);

  renderWithProviders(<RoutingQueuePage queue="rfa" />, "/rfa/queue");

  await userEvent.click(await screen.findByRole("button", { name: /TCK-0001/ }));
  await userEvent.click(await screen.findByRole("button", { name: "Approve and send to QC" }));

  expect(await screen.findByText("The decision could not be recorded. Try again.")).toBeVisible();
});

test("offers analyst assignment without a team suggestion in the collection queue", async () => {
  const assignmentTicket: RoutingTicket = { ...reviewedTicket, state: "ANALYST_ASSIGNMENT" };
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(jsonResponse(queueWith([assignmentTicket])))
    .mockResolvedValue(jsonResponse({ analysts: [] }));
  stubRoutingFetch(fetchMock);

  renderWithProviders(<RoutingQueuePage queue="cm" />, "/cm/queue");

  expect(await screen.findByRole("heading", { name: "Collection Queue" })).toBeVisible();
  // The CM review offered no collection team, so the suggestion stays empty.
  expect(await screen.findByLabelText("Team")).toHaveValue("");
});

test("renders a readable routed-team status message", async () => {
  const routedTicket: RoutingTicket = { ...reviewedTicket, state: "ANALYST_ASSIGNMENT" };
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(jsonResponse(queueWith([routedTicket])))
    .mockResolvedValue(jsonResponse({ analysts: [] }));
  stubRoutingFetch(fetchMock);

  renderWithProviders(<RoutingQueuePage queue="rfa" />, "/rfa/queue");

  await userEvent.click(await screen.findByRole("button", { name: /TCK-0001/ }));
  expect(
    screen.getByText(
      "This request is already routed to the RFA team. The recommendations below are retained as decision context.",
    ),
  ).toBeVisible();
});
