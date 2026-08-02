import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { FeedbackPanel } from "./FeedbackPanel";
import { resetQueryClientForTests } from "../../app/query-client";
import type { AuthSession } from "../../lib/api-client/auth";
import { previewProfile } from "../../test/test-utils";
import { renderWithProviders } from "../../test/test-utils";

const feedbackSession: AuthSession = {
  csrfToken: "test-csrf-token",
  user: {
    ...previewProfile,
    permissions: [...previewProfile.permissions, "feedback:create"],
  },
};

const request = {
  id: "feedback-1",
  ticketId: "ticket-1",
  ticketReference: "TCK-0001",
  productId: "product-1",
  productTitle: "Arctic feedback product",
  status: "requested",
  createdAt: "2026-07-05T00:00:00Z",
  submission: null,
};

beforeEach(() => {
  resetQueryClientForTests();
});

afterEach(() => {
  vi.restoreAllMocks();
});

test("submits simple outcome feedback for a closed request", async () => {
  const fetchMock = vi.fn(fetchByUrl());
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(
    <FeedbackPanel csrfToken="test-csrf-token" />,
    "/app/requests",
    feedbackSession,
  );

  expect(await screen.findByText("Arctic feedback product")).toBeVisible();
  await userEvent.click(screen.getByRole("radio", { name: /Partly/ }));
  await userEvent.type(screen.getByLabelText(/Add context/), "Clear and useful mock output.");
  await userEvent.click(screen.getByRole("button", { name: "Send feedback" }));

  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8001/api/v1/feedback/requests/feedback-1/submit",
      {
        body: JSON.stringify({
          rating: 3,
          comment: "Clear and useful mock output.",
          followUpRequested: false,
        }),
        credentials: "include",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": "test-csrf-token" },
        method: "POST",
      },
    ),
  );
  expect(await screen.findByText("Feedback sent for Arctic feedback product.")).toBeVisible();
  expect(screen.queryByLabelText("Request follow-up")).not.toBeInTheDocument();
});

test("presents pending feedback one closed request at a time", async () => {
  const secondRequest = {
    ...request,
    id: "feedback-2",
    ticketId: "ticket-2",
    ticketReference: "TCK-0002",
    productId: "product-2",
    productTitle: "Maritime pattern report",
  };
  const fetchMock = vi.fn((input: RequestInfo | URL) => {
    const url = requestUrl(input);
    if (url.endsWith("/api/v1/feedback/requests")) {
      return Promise.resolve(jsonResponse({ requests: [request, secondRequest] }));
    }
    return Promise.resolve(jsonResponse({ ...request, status: "submitted" }));
  });
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(
    <FeedbackPanel csrfToken="test-csrf-token" />,
    "/app/requests",
    feedbackSession,
  );

  expect(await screen.findByText("Arctic feedback product")).toBeVisible();
  expect(screen.queryByText("Maritime pattern report")).not.toBeInTheDocument();
  expect(screen.getByText("2 completed requests awaiting feedback")).toBeVisible();
  await userEvent.click(screen.getByRole("radio", { name: /Yes, fully/ }));
  await userEvent.click(screen.getByRole("button", { name: "Send feedback" }));

  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8001/api/v1/feedback/requests/feedback-1/submit",
      expect.objectContaining({
        body: JSON.stringify({
          rating: 5,
          comment: "",
          followUpRequested: false,
        }),
      }),
    ),
  );
  expect(await screen.findByText("Maritime pattern report")).toBeVisible();
});

test("shows an inline error when feedback submission fails", async () => {
  const fetchMock = vi.fn((input: RequestInfo | URL) => {
    const url = requestUrl(input);
    if (url.endsWith("/api/v1/feedback/requests")) {
      return Promise.resolve(jsonResponse({ requests: [request] }));
    }
    return Promise.resolve({
      ok: false,
      status: 409,
      json: () =>
        Promise.resolve({ error: { code: "already_submitted", message: "Already submitted." } }),
    });
  });
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(
    <FeedbackPanel csrfToken="test-csrf-token" />,
    "/app/requests",
    feedbackSession,
  );

  await screen.findByText("Arctic feedback product");
  await userEvent.click(screen.getByRole("radio", { name: /^No/ }));
  await userEvent.click(screen.getByRole("button", { name: "Send feedback" }));

  expect(await screen.findByRole("alert")).toHaveTextContent("Already submitted.");
});

test("does not render feedback controls without feedback permission", () => {
  const fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<FeedbackPanel csrfToken="test-csrf-token" />);

  expect(screen.queryByText("Feedback")).not.toBeInTheDocument();
  expect(fetchMock).not.toHaveBeenCalled();
});

test("does not add a permanent panel when no closed request needs feedback", async () => {
  const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ requests: [] }));
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(
    <FeedbackPanel csrfToken="test-csrf-token" />,
    "/app/requests",
    feedbackSession,
  );

  await waitFor(() => expect(fetchMock).toHaveBeenCalled());
  expect(
    screen.queryByRole("heading", { name: "Feedback on a closed request" }),
  ).not.toBeInTheDocument();
});

test("shows a retryable error when feedback requests cannot load", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce({
      ok: false,
      status: 500,
      json: () => Promise.resolve({ error: { code: "server_error", message: "Failed." } }),
    })
    .mockResolvedValueOnce(jsonResponse({ requests: [request] }));
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(
    <FeedbackPanel csrfToken="test-csrf-token" />,
    "/app/requests",
    feedbackSession,
  );

  expect(await screen.findByText("Feedback requests could not be loaded.")).toBeVisible();
  expect(screen.queryByText("No feedback requests yet.")).not.toBeInTheDocument();

  await userEvent.click(screen.getByRole("button", { name: "Retry feedback" }));

  expect(await screen.findByText("Arctic feedback product")).toBeVisible();
});

test("does not repeat previously submitted feedback", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValue(jsonResponse({ requests: [{ ...request, status: "submitted" }] }));
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(
    <FeedbackPanel csrfToken="test-csrf-token" />,
    "/app/requests",
    feedbackSession,
  );

  await waitFor(() => expect(fetchMock).toHaveBeenCalled());
  expect(screen.queryByText("Arctic feedback product")).not.toBeInTheDocument();
});

function fetchByUrl() {
  return (input: RequestInfo | URL) => {
    const url = requestUrl(input);
    if (url.endsWith("/api/v1/feedback/requests")) {
      return Promise.resolve(jsonResponse({ requests: [request] }));
    }
    return Promise.resolve(
      jsonResponse({
        ...request,
        status: "submitted",
        submission: {
          id: "submission-1",
          requestId: "feedback-1",
          rating: 3,
          comment: "Clear and useful mock output.",
          followUpRequested: false,
          createdAt: "2026-07-05T00:01:00Z",
        },
      }),
    );
  };
}

function requestUrl(input: RequestInfo | URL) {
  if (input instanceof URL) {
    return input.toString();
  }
  if (typeof input === "string") {
    return input;
  }
  return input.url;
}

function jsonResponse(payload: unknown) {
  return { ok: true, json: () => Promise.resolve(payload) };
}
