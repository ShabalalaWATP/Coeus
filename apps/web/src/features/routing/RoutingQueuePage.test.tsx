import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import RoutingQueuePage from "./RoutingQueuePage";
import { resetQueryClientForTests } from "../../app/query-client";
import { renderWithProviders } from "../../test/test-utils";
import type { RoutingQueue, RoutingTicket } from "../../lib/api-client/routing";

const baseTicket: RoutingTicket = {
  ticketId: "ticket-1",
  reference: "TCK-0001",
  requesterUserId: "user-1",
  state: "ROUTE_ASSESSMENT",
  title: "Arctic Fisheries Assessment",
  priority: "high",
  rfaReview: null,
  cmReview: null,
  recommendation: null,
  clarifications: [],
  managerDecisions: [],
  projectPlanUpdates: [],
};

const reviewedTicket: RoutingTicket = {
  ...baseTicket,
  state: "RFA_MANAGER_REVIEW",
  recommendation: {
    id: "recommendation-1",
    recommendedRoute: "rfa",
    reasoningSummary: "RFA route preferred because assessment can satisfy the request.",
    createdAt: "2026-07-05T00:00:00Z",
  },
  rfaReview: {
    id: "rfa-review-1",
    canSatisfy: true,
    confidence: 0.86,
    requiredClarifications: [],
    suggestedWorkPackages: ["Validate assumptions."],
    suggestedTeamId: "RFA-MOCK-REGIONAL",
    estimatedEffort: "1-2 days",
    risks: [],
    managerReviewRequired: true,
    reasoningSummary: "RFA can satisfy the request with assessment-led work packages.",
    createdAt: "2026-07-05T00:00:00Z",
  },
  cmReview: {
    id: "cm-review-1",
    canSatisfy: false,
    confidence: 0.34,
    requiredClarifications: [],
    suggestedCollectionRoute: null,
    suggestedCollectionSources: [],
    estimatedEffort: "1-2 days",
    risks: [],
    managerReviewRequired: true,
    reasoningSummary: "No strong collection signal was found in the intake.",
    createdAt: "2026-07-05T00:00:00Z",
  },
  projectPlanUpdates: [
    {
      id: "plan-1",
      title: "RFA manager route review",
      ownerRole: "RFA Manager",
      status: "proposed",
      note: "RFA route preferred.",
      createdAt: "2026-07-05T00:00:00Z",
    },
  ],
};

beforeEach(() => {
  resetQueryClientForTests();
});

afterEach(() => {
  vi.restoreAllMocks();
});

test("runs RFA capability checks and approves the recommended route", async () => {
  const approvedTicket = {
    ...reviewedTicket,
    state: "ANALYST_ASSIGNMENT",
    managerDecisions: [
      {
        id: "decision-1",
        route: "rfa",
        status: "approved",
        reason: "Approved for analyst assignment.",
        overrideReason: null,
        actorUserId: "manager-1",
        createdAt: "2026-07-05T00:00:00Z",
      },
    ],
  };
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(jsonResponse(queueWith([baseTicket])))
    .mockResolvedValueOnce(jsonResponse(reviewedTicket))
    .mockResolvedValueOnce(jsonResponse(approvedTicket))
    .mockResolvedValue(jsonResponse({ analysts: [] }));
  stubRoutingFetch(fetchMock);

  renderWithProviders(<RoutingQueuePage route="rfa" />, "/rfa/queue");

  await userEvent.click(await screen.findByRole("button", { name: "Run capability checks" }));
  expect(await screen.findByText("Recommended route: RFA")).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Approve route" }));

  expect(await screen.findByLabelText("Assign analyst")).toBeVisible();
  expect(fetchMock).toHaveBeenNthCalledWith(
    3,
    "http://127.0.0.1:8001/api/v1/routing/ticket-1/approve",
    {
      body: JSON.stringify({ route: "rfa" }),
      credentials: "include",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": "test-csrf-token" },
      method: "POST",
    },
  );
});

test("requests clarification from an RFA manager review", async () => {
  const clarificationTicket = {
    ...reviewedTicket,
    rfaReview: {
      ...reviewedTicket.rfaReview!,
      requiredClarifications: ["Confirm a supported mock region."],
    },
  };
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(jsonResponse(queueWith([clarificationTicket])))
    .mockResolvedValueOnce(jsonResponse({ ...clarificationTicket, state: "INFO_REQUIRED" }));
  stubRoutingFetch(fetchMock);

  renderWithProviders(<RoutingQueuePage route="rfa" />, "/rfa/queue");

  await screen.findByText("Recommended route: RFA");
  expect(screen.getByText("Confirm a supported mock region.")).toBeVisible();
  await userEvent.click(screen.getByText("Query or reject this route"));
  await userEvent.type(screen.getByLabelText("Clarification reason"), "Need tighter scope.");
  await userEvent.type(screen.getByLabelText("Clarification question"), "Which mock region?");
  await userEvent.click(screen.getByRole("button", { name: "Request clarification" }));

  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
  expect(fetchMock).toHaveBeenNthCalledWith(
    2,
    "http://127.0.0.1:8001/api/v1/routing/ticket-1/clarification",
    {
      body: JSON.stringify({
        route: "rfa",
        reason: "Need tighter scope.",
        questions: ["Which mock region?"],
      }),
      credentials: "include",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": "test-csrf-token" },
      method: "POST",
    },
  );
});

test("renders an empty collection queue", async () => {
  stubRoutingFetch(vi.fn().mockResolvedValueOnce(jsonResponse(queueWith([]))));

  renderWithProviders(<RoutingQueuePage route="cm" />, "/collection/queue");

  expect(await screen.findByText("No tickets in this queue.")).toBeVisible();
  expect(screen.getByRole("heading", { name: "Collection Queue" })).toBeVisible();
});

test("runs route checks with an empty CSRF token when no session is present", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(jsonResponse(queueWith([baseTicket])))
    .mockResolvedValueOnce(jsonResponse(reviewedTicket));
  stubRoutingFetch(fetchMock);

  renderWithProviders(<RoutingQueuePage route="rfa" />, "/rfa/queue", null);

  await userEvent.click(await screen.findByRole("button", { name: "Run capability checks" }));

  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
  expect(fetchMock).toHaveBeenNthCalledWith(
    2,
    "http://127.0.0.1:8001/api/v1/routing/ticket-1/run",
    {
      credentials: "include",
      headers: { "X-CSRF-Token": "" },
      method: "POST",
    },
  );
});

test("rejects an RFA route with a manager reason", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(jsonResponse(queueWith([reviewedTicket])))
    .mockResolvedValueOnce(jsonResponse({ ...reviewedTicket, state: "INFO_REQUIRED" }));
  stubRoutingFetch(fetchMock);

  renderWithProviders(<RoutingQueuePage route="rfa" />, "/rfa/queue");

  await screen.findByText("Recommended route: RFA");
  await userEvent.click(screen.getByText("Query or reject this route"));
  await userEvent.type(screen.getByLabelText("Rejection reason"), "Assessment route is too broad.");
  await userEvent.click(screen.getByRole("button", { name: "Reject route" }));

  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
  expect(fetchMock).toHaveBeenNthCalledWith(
    2,
    "http://127.0.0.1:8001/api/v1/routing/ticket-1/reject",
    {
      body: JSON.stringify({ route: "rfa", reason: "Assessment route is too broad." }),
      credentials: "include",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": "test-csrf-token" },
      method: "POST",
    },
  );
  // Once the rejected ticket leaves the queue the detail panel must clear rather
  // than silently fall back to an unrelated ticket.
  expect(await screen.findByText("No ticket selected")).toBeVisible();
});

test("approves collection manager fallback routes", async () => {
  const cmTicket: RoutingTicket = {
    ...reviewedTicket,
    state: "CM_MANAGER_REVIEW",
    recommendation: {
      ...reviewedTicket.recommendation!,
      recommendedRoute: "cm",
      reasoningSummary: "CM route selected because collection can satisfy the request.",
    },
  };
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(jsonResponse(queueWith([cmTicket])))
    .mockResolvedValueOnce(jsonResponse({ ...cmTicket, state: "ANALYST_ASSIGNMENT" }))
    .mockResolvedValue(jsonResponse({ analysts: [] }));
  stubRoutingFetch(fetchMock);

  renderWithProviders(<RoutingQueuePage route="cm" />, "/collection/queue");

  expect(await screen.findByText("Recommended route: CM")).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Approve route" }));

  expect(await screen.findByLabelText("Assign analyst")).toBeVisible();
  expect(fetchMock).toHaveBeenNthCalledWith(
    2,
    "http://127.0.0.1:8001/api/v1/routing/ticket-1/approve",
    {
      body: JSON.stringify({ route: "cm" }),
      credentials: "include",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": "test-csrf-token" },
      method: "POST",
    },
  );
});

test("assigns an analyst after route approval and clears the ticket from the queue", async () => {
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
        ],
      }),
    )
    .mockResolvedValueOnce(jsonResponse({ ticketId: "ticket-1", state: "ANALYST_IN_PROGRESS" }));
  stubRoutingFetch(fetchMock);

  renderWithProviders(<RoutingQueuePage route="rfa" />, "/rfa/queue");

  await userEvent.click(await screen.findByRole("button", { name: /TCK-0001/ }));
  await screen.findByRole("option", { name: "Intelligence Analyst" });
  await userEvent.selectOptions(screen.getByLabelText("Analyst"), "analyst-1");
  await userEvent.click(screen.getByRole("button", { name: "Assign analyst" }));

  expect(await screen.findByText("No tickets in this queue.")).toBeVisible();
  expect(screen.getByText("No ticket selected")).toBeVisible();
  expect(fetchMock).toHaveBeenNthCalledWith(
    3,
    "http://127.0.0.1:8001/api/v1/analyst/tasks/ticket-1/assign",
    expect.objectContaining({ method: "POST" }),
  );
});

test("renders a queue error state with retry", async () => {
  const failure = {
    ok: false,
    status: 500,
    json: () => Promise.resolve({ error: { code: "server_error", message: "Failed." } }),
  };
  stubRoutingFetch(vi.fn().mockResolvedValue(failure));

  renderWithProviders(<RoutingQueuePage route="rfa" />, "/rfa/queue");

  expect(
    await screen.findByText("Unable to load data", undefined, { timeout: 5000 }),
  ).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Retry" }));
});

function queueWith(tickets: RoutingTicket[]): RoutingQueue {
  return {
    tickets,
    stats: {
      routeAssessmentCount: 1,
      rfaReviewCount: tickets.filter((ticket) => ticket.state === "RFA_MANAGER_REVIEW").length,
      cmReviewCount: tickets.filter((ticket) => ticket.state === "CM_MANAGER_REVIEW").length,
      clarificationCount: 0,
      analystAssignmentCount: 0,
      rfaAcceptanceRate: 0,
      cmFallbackRate: 0,
    },
  };
}

type MockResponse = ReturnType<typeof jsonResponse>;

function stubRoutingFetch(
  sequential: ReturnType<typeof vi.fn<(url: string, init?: RequestInit) => Promise<MockResponse>>>,
) {
  const fetchMock = vi.fn((url: string, init?: RequestInit) => {
    if (url.includes("release-queue")) {
      return Promise.resolve(jsonResponse(queueWith([])));
    }
    return sequential(url, init);
  });
  vi.stubGlobal("fetch", fetchMock);
  return sequential;
}
function jsonResponse(payload: unknown) {
  return { ok: true, json: () => Promise.resolve(payload) };
}
