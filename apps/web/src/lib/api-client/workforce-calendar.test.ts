import { listMyCommitments, respondToCommitment } from "./workforce-calendar";

afterEach(() => vi.restoreAllMocks());

test("lists and responds to manager commitments with CSRF protection", async () => {
  const fetchMock = vi.fn((input: RequestInfo | URL, _init?: RequestInit) => {
    void _init;
    const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
    return Promise.resolve({
      ok: true,
      status: 200,
      json: () =>
        Promise.resolve(
          url.endsWith("/commitments/me")
            ? { commitments: [] }
            : {
                event: { eventId: "event-1" },
                responseState: "disputed",
                responseVersion: 2,
              },
        ),
    });
  });
  vi.stubGlobal("fetch", fetchMock);
  await expect(listMyCommitments()).resolves.toEqual({ commitments: [] });
  await respondToCommitment(
    "event-1",
    { state: "disputed", expectedVersion: 1, reason: "Synthetic conflict." },
    "csrf",
  );
  const call = fetchMock.mock.lastCall;
  if (!call) throw new Error("Expected a fetch call");
  const [input, init] = call;
  const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
  expect(url.endsWith("/api/v1/calendar/commitments/event-1/responses")).toBe(true);
  expect(init?.method).toBe("POST");
  expect(new Headers(init?.headers).get("X-CSRF-Token")).toBe("csrf");
});
