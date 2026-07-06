import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import QcQueuePage from "./QcQueuePage";
import { resetQueryClientForTests } from "../../app/query-client";
import type { QcProduct } from "../../lib/api-client/qc";
import { renderWithProviders } from "../../test/test-utils";

const baseProduct: QcProduct = {
  ticketId: "ticket-1",
  reference: "TCK-0001",
  requesterUserId: "user-1",
  state: "QC_REVIEW",
  title: "Arctic QC product",
  operationalQuestion: "What activity needs command attention?",
  areaOrRegion: "Arctic fisheries",
  priority: "high",
  requiredOutputFormat: "assessment report",
  checklistKeys: [
    "answers_customer_question",
    "sources_are_sufficient",
    "metadata_complete",
    "classification_checked",
    "releasability_checked",
    "acg_assignment_checked",
    "format_correct",
    "handling_caveats_applied",
    "manager_comments_resolved",
  ],
  latestDraft: {
    id: "draft-1",
    versionNumber: 1,
    title: "Arctic QC product",
    summary: "MOCK DATA ONLY draft.",
    productType: "finished_output",
    content: "MOCK DATA ONLY assessment content.",
    createdByUserId: "analyst-1",
    createdAt: "2026-07-05T00:00:00Z",
    assets: [
      {
        id: "asset-1",
        name: "assessment-draft.pdf",
        assetType: "pdf",
        mimeType: "application/pdf",
        sizeBytes: 512,
        sha256: "d".repeat(64),
      },
    ],
  },
  managerNotes: ["Approved for analyst assignment."],
  decisions: [],
  indexRecords: [],
  disseminations: [],
  feedbackRequests: [],
  ingestedProduct: null,
};

const approvedProduct: QcProduct = {
  ...baseProduct,
  state: "DISSEMINATION_READY",
  decisions: [
    {
      id: "decision-1",
      status: "approved",
      reason: "QC checklist complete.",
      reviewerUserId: "qc-1",
      checklist: baseProduct.checklistKeys.map((key) => ({ key, passed: true })),
      createdAt: "2026-07-05T00:05:00Z",
    },
  ],
  indexRecords: [
    { id: "index-1", productId: "product-1", status: "queued", summary: "Queued." },
    { id: "index-2", productId: "product-1", status: "indexed", summary: "Indexed." },
  ],
  disseminations: [{ id: "dis-1", productId: "product-1", recipientUserId: "user-1" }],
  feedbackRequests: [
    { id: "feedback-1", productId: "product-1", requesterUserId: "user-1", status: "requested" },
  ],
  ingestedProduct: {
    id: "product-1",
    reference: "PROD-1004",
    title: "Arctic QC product",
    status: "published",
    acgIds: ["acg-1"],
  },
};

beforeEach(() => {
  resetQueryClientForTests();
});

afterEach(() => {
  vi.restoreAllMocks();
});

test("approves a QC product and confirms ingestion", async () => {
  const fetchMock = vi.fn(fetchByUrl({ approve: approvedProduct }));
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<QcQueuePage />, "/qc/queue");

  expect(await screen.findByRole("link", { name: /TCK-0001/ })).toBeVisible();
  expect(screen.getByText("MOCK DATA ONLY assessment content.")).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: /Mark all complete/ }));
  await userEvent.click(screen.getByRole("button", { name: /Approve and disseminate/ }));

  expect(await screen.findByText("Ingestion confirmed")).toBeVisible();
  expect(screen.getByText("PROD-1004: Arctic QC product")).toBeVisible();
  expect(screen.getByText("indexed in Intelligence Store indexing.")).toBeVisible();
  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8001/api/v1/qc/products/ticket-1/approve",
      {
        body: JSON.stringify({
          checklist: Object.fromEntries(baseProduct.checklistKeys.map((key) => [key, true])),
          classificationLevel: 2,
          releasability: ["MOCK"],
          handlingCaveats: ["MOCK DATA ONLY"],
          acgIds: ["acg-1"],
          reason: "QC checklist complete.",
        }),
        credentials: "include",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": "test-csrf-token" },
        method: "POST",
      },
    ),
  );
});

test("returns a QC product to the analyst for rework", async () => {
  const rejectedProduct = {
    ...baseProduct,
    state: "REWORK_REQUIRED" as const,
    decisions: [
      {
        id: "decision-2",
        status: "rejected" as const,
        reason: "Sources need clearer mock provenance.",
        reviewerUserId: "qc-1",
        checklist: [],
        createdAt: "2026-07-05T00:06:00Z",
      },
    ],
  };
  const fetchMock = vi.fn(fetchByUrl({ reject: rejectedProduct }));
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<QcQueuePage />, "/qc/queue");

  await screen.findByRole("link", { name: /TCK-0001/ });
  await userEvent.type(
    screen.getByLabelText("Rejection reason"),
    "Sources need clearer mock provenance.",
  );
  await userEvent.click(screen.getByRole("button", { name: /Return to analyst/ }));

  expect(
    await within(screen.getByLabelText("QC product detail")).findByText("REWORK REQUIRED"),
  ).toBeVisible();
  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8001/api/v1/qc/products/ticket-1/reject",
      {
        body: JSON.stringify({ reason: "Sources need clearer mock provenance." }),
        credentials: "include",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": "test-csrf-token" },
        method: "POST",
      },
    ),
  );
});

test("renders queued ingestion status for a QC product without a draft", async () => {
  const detailProduct: QcProduct = {
    ...approvedProduct,
    areaOrRegion: null,
    latestDraft: null,
    operationalQuestion: null,
    requiredOutputFormat: null,
    indexRecords: [],
    feedbackRequests: [],
  };
  const fetchMock = vi.fn(fetchByUrl({ queueProducts: [detailProduct] }));
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<QcQueuePage />, "/qc/queue");

  expect(await screen.findByText("No draft product is attached.")).toBeVisible();
  expect(screen.getAllByText("Not set")).toHaveLength(2);
  expect(screen.getByText("queued in Intelligence Store indexing.")).toBeVisible();
  expect(screen.getByText("0 feedback request created.")).toBeVisible();

  await userEvent.click(screen.getByRole("link", { name: /TCK-/ }));
  expect(await screen.findByText("No draft product is attached.")).toBeVisible();
});

test("renders an empty QC queue", async () => {
  const fetchMock = vi.fn(fetchByUrl({ queueProducts: [] }));
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<QcQueuePage />, "/qc/queue");

  expect(await screen.findByText("No products are awaiting QC.")).toBeVisible();
  expect(screen.getByText("No QC product selected.")).toBeVisible();
});

test("renders a QC queue error state", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: () => Promise.resolve({ error: { code: "server_error", message: "Failed." } }),
    }),
  );

  renderWithProviders(<QcQueuePage />, "/qc/queue");

  expect(
    await screen.findByText("Unable to load data", undefined, { timeout: 5000 }),
  ).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Retry" }));
});

function fetchByUrl({
  approve = approvedProduct,
  detail = baseProduct,
  queueProducts = [baseProduct],
  reject = baseProduct,
}: {
  approve?: QcProduct;
  detail?: QcProduct;
  queueProducts?: QcProduct[];
  reject?: QcProduct;
}) {
  return (input: RequestInfo | URL) => {
    const url = requestUrl(input);
    if (url.endsWith("/api/v1/qc/queue")) {
      return Promise.resolve(jsonResponse({ products: queueProducts }));
    }
    if (url.endsWith("/api/v1/qc/products/ticket-1")) {
      return Promise.resolve(jsonResponse(detail));
    }
    if (url.endsWith("/api/v1/acgs")) {
      return Promise.resolve(
        jsonResponse({
          acgs: [
            {
              id: "acg-1",
              code: "ACG-ALPHA-REGIONAL",
              name: "Alpha Regional",
              description: "Regional mock access group.",
              ownerUserId: "admin-1",
              isActive: true,
              memberUserIds: ["user-1"],
            },
          ],
        }),
      );
    }
    if (url.endsWith("/approve")) {
      return Promise.resolve(jsonResponse(approve));
    }
    if (url.endsWith("/reject")) {
      return Promise.resolve(jsonResponse(reject));
    }
    return Promise.resolve(jsonResponse(baseProduct));
  };
}

function requestUrl(input: RequestInfo | URL) {
  if (input instanceof URL) {
    return input.toString();
  }
  if (typeof input === "string") {
    return input;
  }
  return input.url;
}

function jsonResponse(payload: unknown) {
  return { ok: true, json: () => Promise.resolve(payload) };
}
