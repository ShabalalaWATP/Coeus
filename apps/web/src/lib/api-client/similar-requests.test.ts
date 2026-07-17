import { ApiError } from "./client";
import {
  getSimilarRequestNotice,
  joinSimilarRequest,
  linkRoutingSimilarRequest,
  listRoutingSimilarRequests,
  markRoutingDuplicate,
} from "./similar-requests";

const notice = {
  matches: [
    {
      ticketId: "related-1",
      reference: "TCK-0002",
      title: "Similar maritime request",
      state: "RFI_SEARCHING",
      score: 0.71,
      reasons: ["similarity:vector:0.82"],
      alreadyLinked: false,
      alreadyMarkedDuplicate: false,
      requestKind: "RFI",
      approvedRoute: null,
      assignedTeam: null,
      requestingUnit: null,
      supportedOperation: null,
      timePeriodStart: null,
      timePeriodEnd: null,
    },
  ],
};

afterEach(() => {
  vi.restoreAllMocks();
});

test("calls similar request endpoints with encoded path segments and CSRF headers", async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve(notice) });
  vi.stubGlobal("fetch", fetchMock);

  await getSimilarRequestNotice("ticket/1");
  await joinSimilarRequest("ticket/1", "related/1", "csrf-token");
  await listRoutingSimilarRequests("ticket/1");
  await linkRoutingSimilarRequest("ticket/1", "related/1", "csrf-token");
  await markRoutingDuplicate("ticket/1", "related/1", true, "csrf-token");

  expect(fetchMock).toHaveBeenNthCalledWith(
    1,
    "http://127.0.0.1:8001/api/v1/similar-requests/tickets/ticket%2F1",
    { credentials: "include", method: "GET" },
  );
  expect(fetchMock).toHaveBeenNthCalledWith(
    5,
    "http://127.0.0.1:8001/api/v1/similar-requests/routing/ticket%2F1/duplicate/related%2F1",
    {
      body: JSON.stringify({ withdrawSource: true }),
      credentials: "include",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": "csrf-token" },
      method: "POST",
    },
  );
  expect(fetchMock).toHaveBeenNthCalledWith(
    2,
    "http://127.0.0.1:8001/api/v1/similar-requests/tickets/ticket%2F1/join/related%2F1",
    {
      credentials: "include",
      headers: { "X-CSRF-Token": "csrf-token" },
      method: "POST",
    },
  );
  expect(fetchMock).toHaveBeenNthCalledWith(
    3,
    "http://127.0.0.1:8001/api/v1/similar-requests/routing/ticket%2F1",
    { credentials: "include", method: "GET" },
  );
  expect(fetchMock).toHaveBeenNthCalledWith(
    4,
    "http://127.0.0.1:8001/api/v1/similar-requests/routing/ticket%2F1/link/related%2F1",
    {
      credentials: "include",
      headers: { "X-CSRF-Token": "csrf-token" },
      method: "POST",
    },
  );
});

test("throws parsed errors for similar request failures", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      json: () =>
        Promise.resolve({
          error: { code: "similar_request_not_found", message: "Similar request not found." },
        }),
    }),
  );

  await expect(joinSimilarRequest("ticket-1", "related-1", "csrf-token")).rejects.toEqual(
    new ApiError(404, "similar_request_not_found", "Similar request not found."),
  );
});
