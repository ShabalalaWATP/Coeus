import {
  getAnalyticsDashboard,
  listFeedbackRequests,
  submitFeedback,
  type AnalyticsDashboard,
  type FeedbackRequest,
} from "./analytics";

const feedbackRequest: FeedbackRequest = {
  id: "feedback-1",
  ticketId: "ticket-1",
  ticketReference: "TCK-0001",
  productId: "product-1",
  productTitle: "Arctic feedback product",
  status: "requested",
  createdAt: "2026-07-05T00:00:00Z",
  submission: null,
};

const dashboard: AnalyticsDashboard = {
  audience: "admin",
  metrics: {
    totalTickets: 1,
    activeTickets: 1,
    disseminations: 1,
    feedbackRequested: 1,
    feedbackSubmitted: 1,
    averageRating: 5,
    averageSearchCandidates: 2,
    rfaRoutes: 1,
    collectionRoutes: 0,
  },
  productReuse: [],
  trends: [],
};

afterEach(() => {
  vi.restoreAllMocks();
});

test("lists feedback requests and submits feedback", async () => {
  const submitted = {
    ...feedbackRequest,
    status: "submitted" as const,
    submission: {
      id: "submission-1",
      requestId: "feedback-1",
      rating: 5,
      comment: "Useful.",
      followUpRequested: true,
      createdAt: "2026-07-05T00:01:00Z",
    },
  };
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(jsonResponse({ requests: [feedbackRequest] }))
    .mockResolvedValueOnce(jsonResponse(submitted));
  vi.stubGlobal("fetch", fetchMock);

  await expect(listFeedbackRequests()).resolves.toEqual([feedbackRequest]);
  await expect(
    submitFeedback(
      "feedback-1",
      { rating: 5, comment: "Useful.", followUpRequested: true },
      "csrf-token",
    ),
  ).resolves.toEqual(submitted);

  expect(fetchMock).toHaveBeenNthCalledWith(1, "http://127.0.0.1:8001/api/v1/feedback/requests", {
    credentials: "include",
    method: "GET",
  });
  expect(fetchMock).toHaveBeenNthCalledWith(
    2,
    "http://127.0.0.1:8001/api/v1/feedback/requests/feedback-1/submit",
    {
      body: JSON.stringify({ rating: 5, comment: "Useful.", followUpRequested: true }),
      credentials: "include",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": "csrf-token" },
      method: "POST",
    },
  );
});

test("loads analytics dashboards", async () => {
  const fetchMock = vi.fn().mockResolvedValue(jsonResponse(dashboard));
  vi.stubGlobal("fetch", fetchMock);

  await expect(getAnalyticsDashboard("admin")).resolves.toEqual(dashboard);

  expect(fetchMock).toHaveBeenCalledWith("http://127.0.0.1:8001/api/v1/analytics/admin", {
    credentials: "include",
    method: "GET",
  });
});

test("raises API errors for analytics requests", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      status: 403,
      json: () => Promise.resolve({ error: { code: "forbidden", message: "Denied." } }),
    }),
  );

  await expect(getAnalyticsDashboard("rfa")).rejects.toMatchObject({
    status: 403,
    code: "forbidden",
  });
});

function jsonResponse(payload: unknown) {
  return { ok: true, json: () => Promise.resolve(payload) };
}
