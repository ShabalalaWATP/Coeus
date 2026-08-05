import {
  acknowledgeWorkUpdate,
  deletePackageTemplate,
  deleteStoreLink,
  deleteView,
  getPackageTemplates,
  getSavedViews,
  getStoreLinks,
  getWorkUpdatePreferences,
  getWorkUpdates,
  savePackageTemplate,
  saveStoreLink,
  saveView,
  saveWorkUpdatePreferences,
  type PackageTemplate,
  type SavedView,
  type StoreLink,
} from "./workspace-productivity";

afterEach(() => vi.restoreAllMocks());

test("uses actor-scoped productivity routes and protects every mutation", async () => {
  const fetchMock = vi.fn((...args: [RequestInfo | URL, RequestInit?]) => {
    void args;
    return Promise.resolve({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ items: [], nextCursor: null }),
    });
  });
  vi.stubGlobal("fetch", fetchMock);
  vi.spyOn(crypto, "randomUUID").mockReturnValue("00000000-0000-4000-8000-000000000001");
  const view = { viewId: "view/1", version: 2 } as SavedView;
  const template = { templateId: "template/1", version: 3 } as PackageTemplate;
  const link = { linkId: "link/1", version: 4 } as StoreLink;

  await getSavedViews();
  await saveView(
    "unit/1",
    "Blocked",
    { scope: "direct", includeCompleted: false, columns: [], unitIds: [] },
    "csrf",
  );
  await deleteView("unit/1", view, "csrf");
  await getPackageTemplates("unit/1");
  await savePackageTemplate(
    "unit/1",
    { name: "Assessment", packageTitles: ["Research"], estimatedMinutes: 60 },
    { id: "grant-1", version: 2 },
    "csrf",
  );
  await deletePackageTemplate("unit/1", template, { id: "grant-1", version: 2 }, "csrf");
  await getWorkUpdates();
  await acknowledgeWorkUpdate("update/1", "csrf");
  await getWorkUpdatePreferences();
  await saveWorkUpdatePreferences({ mode: "digest", dueReminders: false, version: 1 }, "csrf");
  await getStoreLinks("unit/1", "ticket", "ticket/1");
  await saveStoreLink(
    "unit/1",
    {
      sourceType: "ticket",
      sourceId: "ticket-1",
      targetType: "product",
      targetId: "product-1",
    },
    "csrf",
  );
  await deleteStoreLink("unit/1", link, "csrf");

  expect(fetchMock).toHaveBeenCalledTimes(13);
  const calls = fetchMock.mock.calls.map(([input, init]) => ({
    url: typeof input === "string" ? input : input instanceof URL ? input.href : input.url,
    init,
  }));
  expect(calls[1]?.url).toContain("unit%2F1/saved-board-views");
  expect(calls[2]?.url).toContain("view%2F1");
  expect(calls[7]?.url).toContain("update%2F1/acknowledgements");
  expect(calls[10]?.url).toContain("sourceType=ticket&sourceId=ticket%2F1&limit=100");
  expect(calls[12]?.url).toContain("link%2F1");
  for (const { init } of calls.filter(({ init }) => init?.method !== "GET")) {
    expect(new Headers(init?.headers).get("X-CSRF-Token")).toBe("csrf");
  }
});
