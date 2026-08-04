import {
  createWorkspaceExport,
  downloadWorkspaceExport,
  getWorkspaceAnalytics,
  getWorkspaceCapabilities,
  getWorkspaceOverview,
  getWorkspacePeople,
  getWorkspacePolicy,
  saveWorkspacePolicy,
  searchWorkspace,
  type WorkspacePolicy,
} from "./workspace-operations";

afterEach(() => vi.restoreAllMocks());

function stubFetch() {
  const fetchMock = vi.fn(() =>
    Promise.resolve({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ items: [] }),
      blob: () => Promise.resolve(new Blob(["scope,metric"], { type: "text/csv" })),
    }),
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function urls(fetchMock: ReturnType<typeof stubFetch>) {
  return (fetchMock.mock.calls as unknown as [string, RequestInit?][]).map(([url]) => url);
}

/** These requests always send a JSON string body; read it without stringifying. */
function jsonBody(init: RequestInit | undefined): unknown {
  const body = init?.body;
  return typeof body === "string" ? JSON.parse(body) : undefined;
}

test("scopes every read to a unit and encodes identifiers", async () => {
  const fetchMock = stubFetch();

  await getWorkspaceOverview("unit/1", "direct");
  await getWorkspacePeople("unit/1", "descendants");
  await getWorkspacePeople("unit/1", "direct", "  Sy  ");
  await getWorkspacePeople("unit/1", "direct", " a ");
  await getWorkspaceCapabilities("unit/1", "descendants");
  await getWorkspaceAnalytics("unit/1", "direct");
  await getWorkspacePolicy("unit/1");
  await searchWorkspace("unit/1", "direct", "  Project  ");
  await searchWorkspace("unit/1", "direct", "Project", true);

  const requested = urls(fetchMock);
  expect(requested.every((url) => url.includes("/workspaces/unit%2F1/"))).toBe(true);
  expect(requested[0]).toContain("/overview?scope=direct");
  expect(requested[1]).toContain("/people?scope=descendants&limit=100");
  // A trimmed query of at least two characters is forwarded; a shorter one is not.
  expect(requested[2]).toContain("query=Sy");
  expect(requested[3]).not.toContain("query=");
  expect(requested[4]).toContain("/capabilities?scope=descendants");
  expect(requested[5]).toContain("/analytics?scope=direct");
  expect(requested[6]).toContain("/policy");
  expect(requested[7]).toContain("query=Project");
  expect(requested[7]).not.toContain("store_only");
  expect(requested[8]).toContain("store_only=true");
});

test("protects mutations with CSRF, an idempotency key and the authorising grant", async () => {
  const fetchMock = stubFetch();
  vi.spyOn(crypto, "randomUUID").mockReturnValue("00000000-0000-4000-8000-000000000001");
  const policy = {
    version: 4,
    deliveryPolicyVersion: 2,
    wipLimit: 8,
    serviceTargetHours: 72,
    planningCadence: "weekly",
    planningWeekday: 0,
    planningLocalTime: "09:00",
    planningDurationMinutes: 60,
  } as WorkspacePolicy;

  await saveWorkspacePolicy("unit/1", policy, { id: "grant-1", version: 3 }, "csrf");
  await createWorkspaceExport("unit/1", true, { id: "grant-1", version: 3 }, "csrf");

  const calls = fetchMock.mock.calls as unknown as [string, RequestInit][];
  expect(calls).toHaveLength(2);
  for (const [, init] of calls) {
    expect(new Headers(init.headers).get("X-CSRF-Token")).toBe("csrf");
  }
  expect(calls[0]?.[1].method).toBe("PUT");
  expect(jsonBody(calls[0]?.[1])).toMatchObject({
    authorisingGrantId: "grant-1",
    expectedGrantVersion: 3,
    expectedVersion: 4,
    expectedDeliveryPolicyVersion: 2,
    idempotencyKey: "workspace-policy-00000000-0000-4000-8000-000000000001",
    wipLimit: 8,
  });
  expect(calls[1]?.[1].method).toBe("POST");
  expect(jsonBody(calls[1]?.[1])).toMatchObject({
    format: "csv",
    includeDescendants: true,
    authorisingGrantId: "grant-1",
    idempotencyKey: "workspace-export-00000000-0000-4000-8000-000000000001",
  });
});

test("downloads an export as an opaque blob from the encoded export route", async () => {
  const fetchMock = stubFetch();

  const content = await downloadWorkspaceExport("export/1");

  expect(content).toBeInstanceOf(Blob);
  expect(urls(fetchMock)[0]).toContain("/workspaces/exports/export%2F1/download");
});
