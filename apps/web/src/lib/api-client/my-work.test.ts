import { listMyWork } from "./my-work";

afterEach(() => vi.restoreAllMocks());

function stubFetch() {
  const fetchMock = vi.fn(() =>
    Promise.resolve({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ cards: [], asOf: "2026-08-03T12:00:00Z", nextCursor: null }),
    }),
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function requestedUrl(fetchMock: ReturnType<typeof stubFetch>) {
  return String((fetchMock.mock.calls as unknown as [string][])[0]?.[0] ?? "");
}

test("accepts the dashboard's numeric limit", async () => {
  const fetchMock = stubFetch();

  await listMyWork(5);

  const url = requestedUrl(fetchMock);
  expect(url).toContain("/workspaces/my-work?");
  expect(url).toContain("limit=5");
  expect(url).toContain("includeCompleted=false");
  expect(url).not.toContain("column=");
});

test("defaults to a bounded page of active work", async () => {
  const fetchMock = stubFetch();

  await listMyWork({});

  expect(requestedUrl(fetchMock)).toContain("limit=25");
});

test("forwards the column, cursor and completed window when asked", async () => {
  const fetchMock = stubFetch();

  await listMyWork({ includeCompleted: true, column: "completed", cursor: "page-2", limit: 50 });

  const url = requestedUrl(fetchMock);
  expect(url).toContain("includeCompleted=true");
  expect(url).toContain("limit=50");
  expect(url).toContain("column=completed");
  expect(url).toContain("cursor=page-2");
});

test("omits an empty column and a null cursor", async () => {
  const fetchMock = stubFetch();

  await listMyWork({ column: "", cursor: null });

  const url = requestedUrl(fetchMock);
  expect(url).not.toContain("column=");
  expect(url).not.toContain("cursor=");
});
