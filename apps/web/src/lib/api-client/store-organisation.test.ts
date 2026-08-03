import {
  addStoreProjectEntry,
  addStoreProjectMember,
  addStoreProjectProduct,
  createStoreProject,
  createStoreSubscription,
  deleteStoreSubscription,
  getStoreProject,
  getStoreProjects,
  getStoreSubscriptionScopes,
  getStoreSubscriptions,
  removeStoreProjectMember,
  removeStoreProjectProduct,
  setStoreProjectArchived,
  updateStoreSubscription,
} from "./store-organisation";

afterEach(() => vi.restoreAllMocks());

test("uses encoded project paths, JSON bodies and CSRF protection", async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({}) });
  vi.stubGlobal("fetch", fetchMock);

  await getStoreProjects();
  await getStoreProject("project/one");
  await createStoreProject(
    { name: "Watch", purpose: "Track reporting", region: null, dateFrom: null, dateTo: null },
    "csrf",
  );
  await addStoreProjectMember("project/one", "member@example.test", "csrf");
  await removeStoreProjectMember("project/one", "member/two", "csrf");
  await setStoreProjectArchived("project/one", true, "csrf");
  await addStoreProjectProduct("project/one", "product/two", "csrf");
  await removeStoreProjectProduct("project/one", "product/two", "csrf");
  await addStoreProjectEntry("project/one", "question", "What changed?", "csrf");

  expect(fetchMock).toHaveBeenCalledWith(
    "http://127.0.0.1:8001/api/v1/store/projects/project%2Fone/members/member%2Ftwo",
    expect.objectContaining({ headers: { "X-CSRF-Token": "csrf" }, method: "DELETE" }),
  );
  expect(fetchMock).toHaveBeenCalledWith(
    "http://127.0.0.1:8001/api/v1/store/projects/project%2Fone/entries",
    expect.objectContaining({
      body: JSON.stringify({ kind: "question", body: "What changed?" }),
      method: "POST",
    }),
  );
});

test("creates, updates, lists and deletes private subscriptions", async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve([]) });
  vi.stubGlobal("fetch", fetchMock);
  const payload = {
    cadence: "daily" as const,
    criteria: { query: "missile activity" },
    enabled: true,
    name: "Daily missile reporting",
  };

  await getStoreSubscriptions();
  await getStoreSubscriptionScopes();
  await createStoreSubscription(payload, "csrf");
  await updateStoreSubscription("subscription/one", { ...payload, enabled: false }, "csrf");
  await deleteStoreSubscription("subscription/one", "csrf");

  expect(fetchMock).toHaveBeenCalledWith(
    "http://127.0.0.1:8001/api/v1/store/subscriptions/subscription%2Fone",
    expect.objectContaining({ headers: { "X-CSRF-Token": "csrf" }, method: "DELETE" }),
  );
  expect(fetchMock).toHaveBeenCalledWith(
    "http://127.0.0.1:8001/api/v1/store/subscription-scopes",
    expect.objectContaining({ method: "GET" }),
  );
});
