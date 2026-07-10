import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { ReleaseQueuePanel } from "./ReleaseQueuePanel";
import { resetQueryClientForTests } from "../../app/query-client";
import { renderWithProviders } from "../../test/test-utils";

const releaseTicket = {
  ticketId: "ticket-1",
  reference: "TCK-0001",
  requesterUserId: "user-1",
  state: "MANAGER_RELEASE",
  title: "Arctic Fisheries Assessment",
  priority: "high",
  rfaReview: null,
  cmReview: null,
  recommendation: null,
  clarifications: [],
  managerDecisions: [],
  workflowPlanUpdates: [],
};

const queue = {
  tickets: [releaseTicket],
  stats: {
    routeAssessmentCount: 0,
    rfaReviewCount: 0,
    cmReviewCount: 0,
    clarificationCount: 0,
    analystAssignmentCount: 0,
    rfaAcceptanceRate: 0,
    cmFallbackRate: 0,
  },
};

beforeEach(() => {
  resetQueryClientForTests();
});

afterEach(() => {
  vi.restoreAllMocks();
});

test("releases a QC-approved product to the customer", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(queue) })
    .mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ ...releaseTicket, state: "DISSEMINATION_READY" }),
    });
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<ReleaseQueuePanel csrfToken="test-csrf-token" route="rfa" />, "/rfa/queue");

  expect(await screen.findByText("Arctic Fisheries Assessment")).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Release to customer" }));

  expect(
    await screen.findByText(
      "TCK-0001 released. The customer has been notified by email and in Istari.",
    ),
  ).toBeVisible();
  expect(screen.getByText("Nothing awaiting release")).toBeVisible();
  expect(fetchMock).toHaveBeenNthCalledWith(
    2,
    "http://127.0.0.1:8001/api/v1/routing/ticket-1/release",
    expect.objectContaining({
      body: JSON.stringify({ route: "rfa" }),
      headers: { "Content-Type": "application/json", "X-CSRF-Token": "test-csrf-token" },
      method: "POST",
    }),
  );
});

test("shows a generic release failure", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(queue) })
    .mockResolvedValue({
      ok: false,
      status: 409,
      json: () => Promise.resolve({ error: { code: "invalid_ticket_state", message: "No." } }),
    });
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(
    <ReleaseQueuePanel csrfToken="test-csrf-token" route="cm" />,
    "/collection/queue",
  );

  await userEvent.click(await screen.findByRole("button", { name: "Release to customer" }));

  await waitFor(() =>
    expect(
      screen.getByText("The release could not be completed. Refresh and try again."),
    ).toBeVisible(),
  );
});

test("renders a release queue error state", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: () => Promise.resolve({ error: { code: "server_error", message: "Failed." } }),
    }),
  );

  renderWithProviders(<ReleaseQueuePanel csrfToken="test-csrf-token" route="rfa" />, "/rfa/queue");

  expect(
    await screen.findByText("Unable to load data", undefined, { timeout: 5000 }),
  ).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Retry" }));
});
