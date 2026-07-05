import { approveQcProduct, getQcProduct, listQcQueue, rejectQcProduct, type QcProduct } from "./qc";

const product: QcProduct = {
  ticketId: "ticket-1",
  reference: "TCK-0001",
  requesterUserId: "user-1",
  state: "QC_REVIEW",
  title: "Arctic QC product",
  operationalQuestion: "What activity needs command attention?",
  areaOrRegion: "Arctic fisheries",
  priority: "high",
  requiredOutputFormat: "assessment report",
  checklistKeys: ["answers_customer_question"],
  latestDraft: null,
  managerNotes: [],
  decisions: [],
  indexRecords: [],
  disseminations: [],
  feedbackRequests: [],
  ingestedProduct: null,
};

afterEach(() => {
  vi.restoreAllMocks();
});

test("calls QC queue and detail endpoints", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(jsonResponse({ products: [product] }))
    .mockResolvedValueOnce(jsonResponse(product));
  vi.stubGlobal("fetch", fetchMock);

  await expect(listQcQueue()).resolves.toEqual({ products: [product] });
  await expect(getQcProduct("ticket-1")).resolves.toEqual(product);

  expect(fetchMock).toHaveBeenNthCalledWith(1, "http://127.0.0.1:8001/api/v1/qc/queue", {
    credentials: "include",
    method: "GET",
  });
  expect(fetchMock).toHaveBeenNthCalledWith(
    2,
    "http://127.0.0.1:8001/api/v1/qc/products/ticket-1",
    {
      credentials: "include",
      method: "GET",
    },
  );
});

test("submits approve and reject actions with CSRF protection", async () => {
  const fetchMock = vi.fn().mockResolvedValue(jsonResponse(product));
  vi.stubGlobal("fetch", fetchMock);

  await approveQcProduct(
    "ticket-1",
    {
      checklist: { answers_customer_question: true },
      classificationLevel: 2,
      releasability: ["MOCK"],
      handlingCaveats: ["MOCK DATA ONLY"],
      acgIds: ["acg-1"],
      reason: "Complete.",
    },
    "csrf-token",
  );
  await rejectQcProduct("ticket-1", "Needs rework.", "csrf-token");

  expect(fetchMock).toHaveBeenNthCalledWith(
    1,
    "http://127.0.0.1:8001/api/v1/qc/products/ticket-1/approve",
    {
      body: JSON.stringify({
        checklist: { answers_customer_question: true },
        classificationLevel: 2,
        releasability: ["MOCK"],
        handlingCaveats: ["MOCK DATA ONLY"],
        acgIds: ["acg-1"],
        reason: "Complete.",
      }),
      credentials: "include",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": "csrf-token" },
      method: "POST",
    },
  );
  expect(fetchMock).toHaveBeenNthCalledWith(
    2,
    "http://127.0.0.1:8001/api/v1/qc/products/ticket-1/reject",
    {
      body: JSON.stringify({ reason: "Needs rework." }),
      credentials: "include",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": "csrf-token" },
      method: "POST",
    },
  );
});

test("raises API errors from QC requests", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      status: 409,
      json: () =>
        Promise.resolve({ error: { code: "qc_checklist_incomplete", message: "Incomplete." } }),
    }),
  );

  await expect(listQcQueue()).rejects.toMatchObject({
    status: 409,
    code: "qc_checklist_incomplete",
  });
});

function jsonResponse(payload: unknown) {
  return { ok: true, json: () => Promise.resolve(payload) };
}
