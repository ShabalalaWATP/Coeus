import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { FeedbackPanel } from "./FeedbackPanel";
import { resetQueryClientForTests } from "../../app/query-client";
import type { AuthSession } from "../../lib/api-client/auth";
import { previewProfile } from "../../lib/permissions/route-access";
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

test("submits customer feedback for a pending request", async () => {
  const fetchMock = vi.fn(fetchByUrl());
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(
    <FeedbackPanel csrfToken="test-csrf-token" />,
    "/app/requests",
    feedbackSession,
  );

  expect(await screen.findByText("Arctic feedback product")).toBeVisible();
  await userEvent.selectOptions(screen.getByLabelText("Rating"), "4");
  await userEvent.type(screen.getByLabelText("Comment"), "Clear and useful mock output.");
  await userEvent.click(screen.getByLabelText("Request follow-up"));
  await userEvent.click(screen.getByRole("button", { name: /Submit feedback/ }));

  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8001/api/v1/feedback/requests/feedback-1/submit",
      {
        body: JSON.stringify({
          rating: 4,
          comment: "Clear and useful mock output.",
          followUpRequested: true,
        }),
        credentials: "include",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": "test-csrf-token" },
        method: "POST",
      },
    ),
  );
  expect(await screen.findByText("submitted")).toBeVisible();
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
  await userEvent.type(screen.getByLabelText("Comment"), "Clear and useful mock output.");
  await userEvent.click(screen.getByRole("button", { name: /Submit feedback/ }));

  expect(await screen.findByRole("alert")).toHaveTextContent("Already submitted.");
});

test("does not render feedback controls without feedback permission", () => {
  const fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<FeedbackPanel csrfToken="test-csrf-token" />);

  expect(screen.queryByText("Feedback")).not.toBeInTheDocument();
  expect(fetchMock).not.toHaveBeenCalled();
});

test("renders empty feedback state for permitted users", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ requests: [] })));

  renderWithProviders(
    <FeedbackPanel csrfToken="test-csrf-token" />,
    "/app/requests",
    feedbackSession,
  );

  expect(await screen.findByText("No feedback requests yet.")).toBeVisible();
  expect(screen.queryByRole("button", { name: /Submit feedback/ })).not.toBeInTheDocument();
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

test("renders submitted feedback without the submission form", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(jsonResponse({ requests: [{ ...request, status: "submitted" }] })),
  );

  renderWithProviders(
    <FeedbackPanel csrfToken="test-csrf-token" />,
    "/app/requests",
    feedbackSession,
  );

  expect(await screen.findByText("submitted")).toBeVisible();
  expect(screen.queryByRole("button", { name: /Submit feedback/ })).not.toBeInTheDocument();
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
          rating: 4,
          comment: "Clear and useful mock output.",
          followUpRequested: true,
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
