import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import RoutingQueuePage from "./RoutingQueuePage";
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
        body: JSON.stringify({ route: "rfa", overrideReason: "abc and RFA has capacity." }),
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
