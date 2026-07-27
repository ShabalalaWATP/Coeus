import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import RoutingQueuePage from "./RoutingQueuePage";
import { JiocAgentDecisionSummary } from "./routing-sections";
import { jsonResponse, queueWith, reviewedTicket, stubRoutingFetch } from "./routing-test-fixtures";
import { resetQueryClientForTests } from "../../app/query-client";
import type { RoutingTicket } from "../../lib/api-client/routing";
import { renderWithProviders } from "../../test/test-utils";

beforeEach(() => {
  resetQueryClientForTests();
});

afterEach(() => {
  vi.restoreAllMocks();
});

test("requires an override reason when approving against the recommendation", async () => {
  const overrideTicket: RoutingTicket = {
    ...reviewedTicket,
    recommendation: {
      ...reviewedTicket.recommendation!,
      recommendedRoute: "cm",
      reasoningSummary: "CM route recommended for collection-backed work.",
    },
  };
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(jsonResponse(queueWith([overrideTicket])))
    .mockResolvedValueOnce(jsonResponse({ ...overrideTicket, state: "ANALYST_ASSIGNMENT" }))
    .mockResolvedValue(jsonResponse({ analysts: [] }));
  stubRoutingFetch(fetchMock);

  renderWithProviders(<RoutingQueuePage queue="jioc" />, "/rfa/queue");

  expect(await screen.findByText("Recommended route: CM")).toBeVisible();
  const approve = screen.getByRole("button", { name: "Approve route" });
  expect(approve).toBeDisabled();

  await userEvent.type(screen.getByLabelText("Override reason"), "ab");
  expect(approve).toBeDisabled();
  await userEvent.type(screen.getByLabelText("Override reason"), "c and RFA has capacity.");
  expect(approve).toBeEnabled();
  await userEvent.click(approve);

  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8001/api/v1/routing/ticket-1/approve",
      expect.objectContaining({
        body: JSON.stringify({
          route: "rfa",
          overrideReason: "abc and RFA has capacity.",
          expectedUpdatedAt: "2026-07-05T00:00:00Z",
        }),
        method: "POST",
      }),
    ),
  );
});

test("keeps clarification disabled until a question is provided", async () => {
  stubRoutingFetch(vi.fn().mockResolvedValueOnce(jsonResponse(queueWith([reviewedTicket]))));

  renderWithProviders(<RoutingQueuePage queue="jioc" />, "/rfa/queue");

  await screen.findByText("Recommended route: RFA");
  await userEvent.click(screen.getByText("Query or reject this route"));
  await userEvent.type(screen.getByLabelText("Clarification reason"), "Need tighter scope.");

  expect(screen.getByRole("button", { name: "Request clarification" })).toBeDisabled();
  await userEvent.type(screen.getByLabelText("Clarification question"), "Which region?");
  expect(screen.getByRole("button", { name: "Request clarification" })).toBeEnabled();
});

test("shows route action failures inline", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(jsonResponse(queueWith([reviewedTicket])))
    .mockResolvedValueOnce({
      ok: false,
      status: 409,
      json: () =>
        Promise.resolve({ error: { code: "invalid_state", message: "Route already decided." } }),
    });
  stubRoutingFetch(fetchMock);

  renderWithProviders(<RoutingQueuePage queue="jioc" />, "/rfa/queue");

  await screen.findByText("Recommended route: RFA");
  await userEvent.click(screen.getByRole("button", { name: "Approve route" }));

  expect(await screen.findByRole("alert")).toHaveTextContent("Route already decided.");
});

test("clears decision text areas after a successful rejection", async () => {
  const secondTicket: RoutingTicket = {
    ...reviewedTicket,
    ticketId: "ticket-2",
    reference: "TCK-0002",
  };
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(jsonResponse(queueWith([reviewedTicket, secondTicket])))
    .mockResolvedValueOnce(jsonResponse({ ...reviewedTicket, state: "INFO_REQUIRED" }));
  stubRoutingFetch(fetchMock);

  renderWithProviders(<RoutingQueuePage queue="jioc" />, "/rfa/queue");

  await screen.findByText("Recommended route: RFA");
  await userEvent.click(screen.getByText("Query or reject this route"));
  await userEvent.type(screen.getByLabelText("Rejection reason"), "Route is too broad.");
  await userEvent.click(screen.getByRole("button", { name: "Reject route" }));

  // Selecting the next ticket must not pre-fill the previous decision text.
  await userEvent.click(await screen.findByRole("button", { name: /TCK-0002/ }));
  await userEvent.click(screen.getByText("Query or reject this route"));
  expect(screen.getByLabelText("Rejection reason")).toHaveValue("");
});

test("shows the deterministic JIOC Agent decision without presenting its score as probability", () => {
  renderWithProviders(
    <JiocAgentDecisionSummary
      decision={{
        id: "decision-1",
        recommendedRoute: "rfa",
        disposition: "manager_review",
        confidence: 0.42,
        rationaleCodes: ["risk_review_required"],
        policyVersion: "jioc-routing-policy-v2",
        createdAt: "2026-07-23T08:30:00Z",
      }}
    />,
  );

  expect(screen.getByRole("heading", { name: "Human JIOC review: RFA" })).toBeVisible();
  expect(screen.getByText("Risk review required")).toBeVisible();
  expect(screen.getByText(/Policy jioc-routing-policy-v2/)).toBeVisible();
  expect(screen.getByText("0.42")).toBeVisible();
  expect(screen.queryByText("42%")).not.toBeInTheDocument();
});

test("opens the task selected by an oversight deep link", async () => {
  const secondTicket: RoutingTicket = {
    ...reviewedTicket,
    ticketId: "ticket-2",
    reference: "TCK-0002",
    title: "Selected oversight exception",
  };
  stubRoutingFetch(
    vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(queueWith([reviewedTicket])))
      .mockResolvedValueOnce(jsonResponse(secondTicket)),
  );

  renderWithProviders(<RoutingQueuePage queue="jioc" />, "/jioc/queue?ticket=ticket-2");

  expect(await screen.findByRole("heading", { name: "TCK-0002" })).toBeVisible();
  expect(screen.getByText("Selected oversight exception")).toBeVisible();
});
