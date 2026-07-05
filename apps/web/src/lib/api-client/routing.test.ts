import {
  approveRoute,
  listRoutingQueue,
  rejectRoute,
  requestRouteClarification,
  runRoutingReviews,
} from "./routing";

afterEach(() => {
  vi.restoreAllMocks();
});

test("calls routing queue and manager action endpoints", async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: () =>
      Promise.resolve({
        tickets: [],
        stats: {
          routeAssessmentCount: 0,
          rfaReviewCount: 0,
          cmReviewCount: 0,
          clarificationCount: 0,
          analystAssignmentCount: 0,
          rfaAcceptanceRate: 0,
          cmFallbackRate: 0,
        },
      }),
  });
  vi.stubGlobal("fetch", fetchMock);

  await listRoutingQueue("rfa");
  await listRoutingQueue("cm");

  expect(fetchMock).toHaveBeenNthCalledWith(1, "http://127.0.0.1:8001/api/v1/routing/rfa/queue", {
    credentials: "include",
    method: "GET",
  });
  expect(fetchMock).toHaveBeenNthCalledWith(2, "http://127.0.0.1:8001/api/v1/routing/cm/queue", {
    credentials: "include",
    method: "GET",
  });
});

test("posts routing review, approval, rejection and clarification payloads", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValue({ ok: true, json: () => Promise.resolve({ ticketId: "ticket-1" }) });
  vi.stubGlobal("fetch", fetchMock);

  await runRoutingReviews("ticket-1", "csrf");
  await approveRoute("ticket-1", "rfa", "csrf", "Override.");
  await rejectRoute("ticket-1", "cm", "Not viable.", "csrf");
  await requestRouteClarification("ticket-1", "rfa", "Need detail.", ["What region?"], "csrf");

  expect(fetchMock).toHaveBeenNthCalledWith(
    1,
    "http://127.0.0.1:8001/api/v1/routing/ticket-1/run",
    {
      credentials: "include",
      headers: { "X-CSRF-Token": "csrf" },
      method: "POST",
    },
  );
  expect(fetchMock).toHaveBeenNthCalledWith(
    2,
    "http://127.0.0.1:8001/api/v1/routing/ticket-1/approve",
    {
      body: JSON.stringify({ route: "rfa", overrideReason: "Override." }),
      credentials: "include",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": "csrf" },
      method: "POST",
    },
  );
  expect(fetchMock).toHaveBeenNthCalledWith(
    3,
    "http://127.0.0.1:8001/api/v1/routing/ticket-1/reject",
    {
      body: JSON.stringify({ route: "cm", reason: "Not viable." }),
      credentials: "include",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": "csrf" },
      method: "POST",
    },
  );
  expect(fetchMock).toHaveBeenNthCalledWith(
    4,
    "http://127.0.0.1:8001/api/v1/routing/ticket-1/clarification",
    {
      body: JSON.stringify({
        route: "rfa",
        reason: "Need detail.",
        questions: ["What region?"],
      }),
      credentials: "include",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": "csrf" },
      method: "POST",
    },
  );
});

test("converts failed routing responses into API errors", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: () =>
        Promise.resolve({ error: { code: "routing_failed", message: "Routing failed." } }),
    }),
  );

  await expect(listRoutingQueue("rfa")).rejects.toMatchObject({
    status: 500,
    code: "routing_failed",
    message: "Routing failed.",
  });
});
