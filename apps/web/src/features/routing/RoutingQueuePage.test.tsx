import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import RoutingQueuePage from "./RoutingQueuePage";
import {
  baseTicket,
  jsonResponse,
  queueWith,
  reviewedTicket,
  stubRoutingFetch,
} from "./routing-test-fixtures";
import { resetQueryClientForTests } from "../../app/query-client";
import { renderWithProviders } from "../../test/test-utils";
import type { RoutingTicket } from "../../lib/api-client/routing";

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

  renderWithProviders(<RoutingQueuePage queue="jioc" />, "/rfa/queue");

  await userEvent.click(await screen.findByText("Capability teams"));
  expect(await screen.findByText("Maritime Assessment Cell")).toBeVisible();
  // The internal priority tier badge and its reason breakdown are visible.
  expect(screen.getAllByText("P2").length).toBeGreaterThan(0);
  expect(screen.getByText("Internal priority score 0.77")).toBeVisible();
  expect(screen.getByText("Region tier 1 arctic")).toBeVisible();
  await userEvent.click(await screen.findByRole("button", { name: "Run capability checks" }));
  expect(await screen.findByText("Recommended route: RFA")).toBeVisible();
  // Top candidate teams from the recommendation scorer are listed.
  expect(screen.getByText("Candidate teams")).toBeVisible();
  expect(screen.getByText("Geospatial Assessment Cell")).toBeVisible();
  expect(screen.getByText("score 0.79")).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Approve route" }));

  // The approved ticket belongs to the team manager now, so it leaves JIOC.
  expect(await screen.findByText("No tickets in this queue.")).toBeVisible();
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

  renderWithProviders(<RoutingQueuePage queue="jioc" />, "/rfa/queue");

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

test("JIOC closes a referred re-analysis dispute with full decision context", async () => {
  const adjudicationTicket: RoutingTicket = {
    ...reviewedTicket,
    state: "JIOC_REANALYSIS_ADJUDICATION",
    reanalysisContext: {
      productId: "product-1",
      customerReason: "The July coverage was incomplete.",
      unmetCriteria: ["July coverage"],
      managerRationale: "The manager considers the agreed scope complete.",
    },
  };
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(jsonResponse(queueWith([adjudicationTicket])))
    .mockResolvedValueOnce(
      jsonResponse({ ...adjudicationTicket, state: "CLOSED_REANALYSIS_DECLINED" }),
    );
  stubRoutingFetch(fetchMock);

  renderWithProviders(<RoutingQueuePage queue="jioc" />, "/jioc/queue");

  expect(await screen.findByText("The July coverage was incomplete.")).toBeVisible();
  expect(screen.getByText("The manager considers the agreed scope complete.")).toBeVisible();
  await userEvent.type(
    screen.getByLabelText("Decision rationale"),
    "The released product meets the approved requirement.",
  );
  await userEvent.click(screen.getByRole("button", { name: "Close without re-analysis" }));

  expect(await screen.findByText("No tickets in this queue.")).toBeVisible();
  expect(fetchMock).toHaveBeenNthCalledWith(
    2,
    "http://127.0.0.1:8001/api/v1/routing/ticket-1/jioc-reanalysis-decision",
    expect.objectContaining({
      body: JSON.stringify({
        decision: "close",
        rationale: "The released product meets the approved requirement.",
      }),
      method: "POST",
    }),
  );
});

test("renders an empty JIOC queue with the full capability catalogue", async () => {
  stubRoutingFetch(vi.fn().mockResolvedValueOnce(jsonResponse(queueWith([]))));

  renderWithProviders(<RoutingQueuePage queue="jioc" />, "/jioc/queue");

  expect(await screen.findByText("No tickets in this queue.")).toBeVisible();
  expect(screen.getByRole("heading", { name: "JIOC Queue" })).toBeVisible();
  await userEvent.click(screen.getByText("Capability teams"));
  expect(await screen.findByText("Cyber Sensor Coordination Cell")).toBeVisible();
});

test("runs route checks with an empty CSRF token when no session is present", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(jsonResponse(queueWith([baseTicket])))
    .mockResolvedValueOnce(jsonResponse(reviewedTicket));
  stubRoutingFetch(fetchMock);

  renderWithProviders(<RoutingQueuePage queue="jioc" />, "/rfa/queue", null);

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

  renderWithProviders(<RoutingQueuePage queue="jioc" />, "/rfa/queue");

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
  expect(await screen.findByText("No ticket selected")).toBeVisible();
});

test("approves a collection route which pauses for the customer's collect choice", async () => {
  const cmTicket: RoutingTicket = {
    ...reviewedTicket,
    recommendation: {
      ...reviewedTicket.recommendation!,
      recommendedRoute: "cm",
      reasoningSummary: "CM route selected because collection can satisfy the request.",
    },
  };
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(jsonResponse(queueWith([cmTicket])))
    .mockResolvedValueOnce(jsonResponse({ ...cmTicket, state: "COLLECT_CHOICE" }))
    .mockResolvedValue(jsonResponse({ analysts: [] }));
  stubRoutingFetch(fetchMock);

  renderWithProviders(<RoutingQueuePage queue="jioc" />, "/jioc/queue");

  expect(await screen.findByText("Recommended route: CM")).toBeVisible();
  await userEvent.click(screen.getByLabelText("Collection required: route to CM"));
  await userEvent.click(screen.getByRole("button", { name: "Approve route" }));

  // Awaiting the customer's collect choice keeps the ticket visible to JIOC.
  expect((await screen.findAllByText("Collect choice")).length).toBeGreaterThan(0);
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

test("shows an action error when the route approval fails", async () => {
  const failure = {
    ok: false,
    status: 500,
    json: () => Promise.resolve({ error: { code: "server_error", message: "Failed." } }),
  };
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(jsonResponse(queueWith([reviewedTicket])))
    .mockResolvedValueOnce(failure);
  stubRoutingFetch(fetchMock);

  renderWithProviders(<RoutingQueuePage queue="jioc" />, "/jioc/queue");

  await screen.findByText("Recommended route: RFA");
  await userEvent.click(screen.getByRole("button", { name: "Approve route" }));

  // Deliberate backend rejections surface their own message in the alert.
  expect(await screen.findByRole("alert")).toHaveTextContent("Failed.");
});

test("loads older tickets through cursor pagination without duplicates", async () => {
  const olderTicket: RoutingTicket = {
    ...reviewedTicket,
    ticketId: "ticket-2",
    reference: "TCK-0002",
    title: "Older mock request",
  };
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(jsonResponse({ ...queueWith([baseTicket]), nextCursor: "cursor-2" }))
    .mockResolvedValueOnce(
      jsonResponse({ ...queueWith([baseTicket, olderTicket]), nextCursor: null }),
    );
  stubRoutingFetch(fetchMock);

  renderWithProviders(<RoutingQueuePage queue="jioc" />, "/jioc/queue");

  await userEvent.click(await screen.findByRole("button", { name: "Load more tickets" }));

  expect(await screen.findByText("2 tickets in this queue.")).toBeVisible();
  expect(screen.getByRole("button", { name: /TCK-0002/ })).toBeVisible();
  expect(screen.queryByRole("button", { name: "Load more tickets" })).not.toBeInTheDocument();
  expect(fetchMock).toHaveBeenNthCalledWith(
    2,
    "http://127.0.0.1:8001/api/v1/routing/jioc/queue?cursor=cursor-2",
    { credentials: "include", method: "GET" },
  );
});

test("renders a queue error state with retry", async () => {
  const failure = {
    ok: false,
    status: 500,
    json: () => Promise.resolve({ error: { code: "server_error", message: "Failed." } }),
  };
  stubRoutingFetch(vi.fn().mockResolvedValue(failure));

  renderWithProviders(<RoutingQueuePage queue="jioc" />, "/rfa/queue");

  expect(
    await screen.findByText("Unable to load data", undefined, { timeout: 5000 }),
  ).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Retry" }));
});
