import { ApiError } from "./client";
import {
  acceptProductOffer,
  getRfiSearchResults,
  rejectProductOffer,
  runRfiSearch,
} from "./rfi-search";

const result = {
  ticketId: "ticket-1",
  ticketState: "RFI_MATCH_OFFERED",
  offers: [],
  metrics: null,
};

afterEach(() => {
  vi.restoreAllMocks();
});

test("calls RFI search endpoints with CSRF where needed", async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve(result) });
  vi.stubGlobal("fetch", fetchMock);

  await getRfiSearchResults("ticket-1");
  await runRfiSearch("ticket-1", "csrf-token");
  await acceptProductOffer("ticket-1", "product-1", "csrf-token");
  await rejectProductOffer("ticket-1", "product-1", "Not current enough.", "csrf-token");

  expect(fetchMock).toHaveBeenNthCalledWith(
    1,
    "http://127.0.0.1:8001/api/v1/rfi-search/ticket-1/results",
    {
      credentials: "include",
      method: "GET",
    },
  );
  expect(fetchMock).toHaveBeenNthCalledWith(
    2,
    "http://127.0.0.1:8001/api/v1/rfi-search/ticket-1/run",
    {
      credentials: "include",
      headers: { "X-CSRF-Token": "csrf-token" },
      method: "POST",
    },
  );
  expect(fetchMock).toHaveBeenNthCalledWith(
    3,
    "http://127.0.0.1:8001/api/v1/rfi-search/ticket-1/offers/product-1/accept",
    {
      credentials: "include",
      headers: { "X-CSRF-Token": "csrf-token" },
      method: "POST",
    },
  );
  expect(fetchMock).toHaveBeenNthCalledWith(
    4,
    "http://127.0.0.1:8001/api/v1/rfi-search/ticket-1/offers/product-1/reject",
    {
      body: JSON.stringify({ reason: "Not current enough." }),
      credentials: "include",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": "csrf-token" },
      method: "POST",
    },
  );
});

test("throws parsed RFI search errors", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      status: 409,
      json: () =>
        Promise.resolve({
          error: { code: "invalid_ticket_state", message: "Ticket cannot be searched." },
        }),
    }),
  );

  await expect(runRfiSearch("ticket-1", "csrf-token")).rejects.toEqual(
    new ApiError(409, "invalid_ticket_state", "Ticket cannot be searched."),
  );
});
