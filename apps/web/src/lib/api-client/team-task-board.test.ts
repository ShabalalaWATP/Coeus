import { getTeamTaskBoard } from "./team-task-board";

afterEach(() => vi.restoreAllMocks());

function stubFetch() {
  const fetchMock = vi.fn(() =>
    Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({ cards: [] }) }),
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function requestedUrl(fetchMock: ReturnType<typeof stubFetch>, index = 0) {
  return (fetchMock.mock.calls as unknown as [string, RequestInit?][])[index]?.[0] ?? "";
}

test("defaults to the current, bounded board for the encoded unit", async () => {
  const fetchMock = stubFetch();

  await getTeamTaskBoard("unit/1");

  const url = requestedUrl(fetchMock);
  expect(url).toContain("/workspaces/unit%2F1/board?");
  expect(url).toContain("includeCompleted=false");
  expect(url).toContain("limit=100");
  expect(url).not.toContain("scope=");
});

test("accepts the legacy boolean argument as include-completed", async () => {
  const fetchMock = stubFetch();

  await getTeamTaskBoard("unit-1", true);

  expect(requestedUrl(fetchMock)).toContain("includeCompleted=true");
});

test("forwards every optional filter and repeats multi-valued ones", async () => {
  const fetchMock = stubFetch();

  await getTeamTaskBoard("unit-1", {
    includeCompleted: true,
    scope: "descendants",
    columns: ["in_progress", "blocked"] as never,
    unitIds: ["unit-1", "unit-2"],
    priority: "high",
    dueFrom: "2026-08-01",
    dueTo: "2026-08-31",
    completedAfter: "2026-07-01",
    cursor: "cursor-1",
    limit: 25,
  });

  const url = requestedUrl(fetchMock);
  expect(url).toContain("limit=25");
  expect(url).toContain("scope=descendants");
  expect(url).toContain("column=in_progress&column=blocked");
  expect(url).toContain("unitId=unit-1&unitId=unit-2");
  expect(url).toContain("priority=high");
  expect(url).toContain("dueFrom=2026-08-01");
  expect(url).toContain("dueTo=2026-08-31");
  expect(url).toContain("completedAfter=2026-07-01");
  expect(url).toContain("cursor=cursor-1");
});

test("omits a null cursor so the first page is requested", async () => {
  const fetchMock = stubFetch();

  await getTeamTaskBoard("unit-1", { cursor: null });

  expect(requestedUrl(fetchMock)).not.toContain("cursor=");
});
