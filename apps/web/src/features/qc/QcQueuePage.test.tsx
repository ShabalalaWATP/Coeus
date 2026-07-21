import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import QcQueuePage from "./QcQueuePage";
import {
  approvedProduct,
  baseProduct,
  defaultAcgs,
  fetchByUrl,
  jsonResponse,
  renderQcRoutes,
} from "./qc-test-fixtures";
import { resetQueryClientForTests } from "../../app/query-client";
import type { QcProduct } from "../../lib/api-client/qc";
import { renderWithProviders } from "../../test/test-utils";

beforeEach(() => {
  resetQueryClientForTests();
});

afterEach(() => {
  vi.restoreAllMocks();
});

async function completeQcReview() {
  for (const key of baseProduct.checklistKeys) {
    await userEvent.click(screen.getByLabelText(key.replaceAll("_", " ")));
  }
  await userEvent.selectOptions(screen.getByLabelText("ACG"), "acg-1");
  await userEvent.type(screen.getByLabelText("Approval reason"), "Reviewed every QC control.");
}

test("approves a QC product and confirms ingestion", async () => {
  const fetchMock = vi.fn(fetchByUrl({ approve: approvedProduct }));
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<QcQueuePage />, "/qc/queue");

  expect(await screen.findByRole("link", { name: /TCK-0001/ })).toBeVisible();
  expect(screen.getByText("MOCK DATA ONLY assessment content.")).toBeVisible();
  expect(screen.queryByRole("button", { name: /Mark all complete/ })).not.toBeInTheDocument();
  await completeQcReview();
  await userEvent.click(screen.getByRole("button", { name: /Approve and disseminate/ }));

  expect(await screen.findByText("Released to customer")).toBeVisible();
  expect(screen.getByText("PROD-1004: Arctic QC product")).toBeVisible();
  expect(screen.getByText("indexed in Intelligence Store indexing.")).toBeVisible();
  expect(screen.getByText("1 feedback request created.")).toBeVisible();
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
          reason: "Reviewed every QC control.",
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
    await within(screen.getByLabelText("QC product detail")).findByText("Rework required"),
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
    disseminations: [{ id: "dis-1", productId: "product-1", recipientUserId: "user-1" }],
    feedbackRequests: [],
  };
  const fetchMock = vi.fn(fetchByUrl({ queueProducts: [detailProduct] }));
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<QcQueuePage />, "/qc/queue");

  expect(await screen.findByText("No draft product is attached.")).toBeVisible();
  expect(screen.getAllByText("Not set")).toHaveLength(2);
  expect(screen.getByText("Released to customer")).toBeVisible();
  expect(screen.getByText("queued in Intelligence Store indexing.")).toBeVisible();
  expect(screen.getByText("0 feedback request created.")).toBeVisible();

  await userEvent.click(screen.getByRole("link", { name: /TCK-/ }));
  expect(await screen.findByText("No draft product is attached.")).toBeVisible();
});

test("keeps approval disabled until access control groups are available", async () => {
  const fetchMock = vi.fn(fetchByUrl({ acgs: [] }));
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<QcQueuePage />, "/qc/queue");

  await screen.findByRole("link", { name: /TCK-0001/ });
  for (const key of baseProduct.checklistKeys) {
    await userEvent.click(screen.getByLabelText(key.replaceAll("_", " ")));
  }
  await userEvent.type(screen.getByLabelText("Approval reason"), "Reviewed every QC control.");

  expect(screen.getByRole("button", { name: /Approve and disseminate/ })).toBeDisabled();
});

test("blocks release when the QC Agent preflight finds a problem", async () => {
  const blocked: QcProduct = {
    ...baseProduct,
    agentPreflight: {
      ...baseProduct.agentPreflight!,
      status: "blocked",
      blockers: ["evidence_review_ready"],
      checks: [
        {
          key: "evidence_review_ready",
          passed: false,
          detail: "The evidence narrative is not ready for human review.",
        },
      ],
    },
  };
  vi.stubGlobal("fetch", vi.fn(fetchByUrl({ queueProducts: [blocked] })));

  renderWithProviders(<QcQueuePage />, "/qc/queue");

  expect(await screen.findByText("Blocked.")).toBeVisible();
  await completeQcReview();
  expect(screen.getByRole("button", { name: /Approve and disseminate/ })).toBeDisabled();
  expect(screen.getByText(/Human QC and the release checklist remain mandatory/)).toBeVisible();
});

test("shows a retryable error when QC access control groups cannot load", async () => {
  let acgRequests = 0;
  const fetchMock = vi.fn((url: string) => {
    if (url.endsWith("/api/v1/acgs")) {
      acgRequests += 1;
      if (acgRequests === 1) {
        return Promise.resolve({
          ok: false,
          status: 500,
          json: () => Promise.resolve({ error: { code: "server_error", message: "Failed." } }),
        });
      }
      return Promise.resolve(jsonResponse({ acgs: defaultAcgs }));
    }
    return fetchByUrl({})(url);
  });
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<QcQueuePage />, "/qc/queue");

  await screen.findByRole("link", { name: /TCK-0001/ });
  expect(
    await screen.findByText("Access groups could not be loaded. Refresh and try again."),
  ).toBeVisible();
  expect(screen.getByLabelText("ACG")).toBeDisabled();
  for (const key of baseProduct.checklistKeys) {
    await userEvent.click(screen.getByLabelText(key.replaceAll("_", " ")));
  }
  await userEvent.type(screen.getByLabelText("Approval reason"), "Reviewed every QC control.");
  expect(screen.getByRole("button", { name: /Approve and disseminate/ })).toBeDisabled();

  await userEvent.click(screen.getByRole("button", { name: "Retry access groups" }));

  expect(await screen.findByRole("option", { name: "ACG-ALPHA-REGIONAL" })).toBeVisible();
  await waitFor(() => expect(screen.getByLabelText("ACG")).not.toBeDisabled());
  await userEvent.selectOptions(screen.getByLabelText("ACG"), "acg-1");
  expect(screen.getByRole("button", { name: /Approve and disseminate/ })).not.toBeDisabled();
});

test("resets the checklist and release form when the selected product changes", async () => {
  const secondProduct: QcProduct = {
    ...baseProduct,
    ticketId: "ticket-2",
    reference: "TCK-0002",
    title: "Baltic QC product",
  };
  const fetchMock = vi.fn((url: string) => {
    if (url.endsWith("/api/v1/qc/products/ticket-2")) {
      return Promise.resolve(jsonResponse(secondProduct));
    }
    return fetchByUrl({ queueProducts: [baseProduct, secondProduct] })(url);
  });
  vi.stubGlobal("fetch", fetchMock);

  renderQcRoutes("/qc/queue");

  await screen.findByRole("link", { name: /TCK-0001/ });
  await userEvent.click(screen.getByLabelText("answers customer question"));
  await userEvent.type(screen.getByLabelText("Rejection reason"), "Needs new sources.");
  expect(screen.getByLabelText("answers customer question")).toBeChecked();

  await userEvent.click(screen.getByRole("link", { name: /TCK-0002/ }));

  await waitFor(() => expect(screen.getByLabelText("answers customer question")).not.toBeChecked());
  expect(screen.getByLabelText("Rejection reason")).toHaveValue("");
});

test("notes when the requested QC product cannot be found", async () => {
  const fetchMock = vi.fn(fetchByUrl({}));
  vi.stubGlobal("fetch", fetchMock);

  renderQcRoutes("/qc/products/ticket-404");

  expect(
    await screen.findByText(
      "The requested product was not found or is no longer in the QC queue.",
      undefined,
      { timeout: 5000 },
    ),
  ).toBeVisible();
  expect(screen.getByRole("link", { name: "Back to the QC queue" })).toHaveAttribute(
    "href",
    "/qc/queue",
  );
  expect(
    within(screen.getByLabelText("QC product detail")).getByText("No QC product selected."),
  ).toBeVisible();
  expect(screen.getByText("Assigned to you")).toBeVisible();
});

test("shows QC action failures inline", async () => {
  const fetchMock = vi.fn((url: string) => {
    if (url.endsWith("/reject")) {
      return Promise.resolve({
        ok: false,
        status: 409,
        json: () =>
          Promise.resolve({
            error: { code: "invalid_state", message: "Product already left QC." },
          }),
      });
    }
    return fetchByUrl({})(url);
  });
  vi.stubGlobal("fetch", fetchMock);

  renderWithProviders(<QcQueuePage />, "/qc/queue");

  await screen.findByRole("link", { name: /TCK-0001/ });
  await userEvent.type(screen.getByLabelText("Rejection reason"), "Needs new sources.");
  await userEvent.click(screen.getByRole("button", { name: /Return to analyst/ }));

  expect(await screen.findByRole("alert")).toHaveTextContent("Product already left QC.");
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

test("does not show a missing-product notice when a direct QC link fails to load", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: () => Promise.resolve({ error: { code: "server_error", message: "Failed." } }),
    }),
  );

  renderQcRoutes("/qc/products/ticket-1");

  expect(
    await screen.findByText("Unable to load data", undefined, { timeout: 5000 }),
  ).toBeVisible();
  expect(
    screen.queryByText("The requested product was not found or is no longer in the QC queue.", {
      exact: false,
    }),
  ).not.toBeInTheDocument();
});
