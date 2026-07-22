import { render, type RenderResult } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import QcQueuePage from "./QcQueuePage";
import { AppProviders } from "../../app/providers";
import type { QcProduct, QcQueueItem } from "../../lib/api-client/qc";
import { previewSession } from "../../test/test-utils";

export const baseProduct: QcProduct = {
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
    description: "MOCK DATA ONLY product description.",
    manifestHash: "e".repeat(64),
    createdByUserId: "analyst-1",
    createdAt: "2026-07-05T00:00:00Z",
    assets: [
      {
        id: "asset-1",
        name: "assessment-draft.pdf",
        assetType: "pdf",
        mimeType: "application/pdf",
        detectedMimeType: "application/pdf",
        sizeBytes: 512,
        sha256: "d".repeat(64),
        previewKind: "pdf",
        processingStatus: "ready",
        previewAvailable: true,
      },
    ],
  },
  managerNotes: ["Approved for analyst assignment."],
  decisions: [],
  agentPreflight: {
    id: "preflight-1",
    draftVersionId: "draft-1",
    status: "passed",
    checks: [
      { key: "draft_complete", passed: true, detail: "Draft content is present." },
      {
        key: "human_release_controls_pending",
        passed: true,
        detail: "Human release review remains mandatory.",
      },
    ],
    blockers: [],
    findings: [],
    policyVersion: "qc-preflight-v1",
    createdAt: "2026-07-05T00:02:00Z",
  },
  indexRecords: [],
  disseminations: [],
  feedbackRequests: [],
  ingestedProduct: null,
};

export const approvedProduct: QcProduct = {
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
  // QC approval now performs the final release to the customer.
  disseminations: [{ id: "dissemination-1", productId: "product-1", recipientUserId: "user-1" }],
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

export function renderQcRoutes(initialPath: string): RenderResult {
  window.history.pushState({}, "Test page", initialPath);
  return render(
    <AppProviders initialAuthSession={previewSession}>
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route path="/qc/queue" element={<QcQueuePage />} />
          <Route path="/qc/products/:productId" element={<QcQueuePage />} />
        </Routes>
      </MemoryRouter>
    </AppProviders>,
  );
}

export const defaultAcgs = [
  {
    id: "acg-1",
    code: "ACG-ALPHA-REGIONAL",
    name: "Alpha Regional",
    description: "Regional mock access group.",
    ownerUserId: "admin-1",
    isActive: true,
    memberUserIds: ["user-1"],
  },
];

export function fetchByUrl({
  acgs = defaultAcgs,
  approve = approvedProduct,
  detail = baseProduct,
  queueItems,
  queueProducts = [baseProduct],
  reject = baseProduct,
}: {
  acgs?: typeof defaultAcgs;
  approve?: QcProduct;
  detail?: QcProduct;
  queueItems?: QcQueueItem[];
  queueProducts?: QcProduct[];
  reject?: QcProduct;
}) {
  return (url: string) => {
    if (url.endsWith("/api/v1/qc/queue")) {
      return Promise.resolve(
        jsonResponse({
          items:
            queueItems ??
            queueProducts.map((product) => ({
              ticketId: product.ticketId,
              reference: product.reference,
              state: product.state,
              claimStatus: "claimed_by_you" as const,
            })),
          products: queueProducts,
        }),
      );
    }
    if (url.endsWith("/api/v1/qc/products/ticket-1")) {
      return Promise.resolve(jsonResponse(detail));
    }
    if (url.includes("/api/v1/qc/products/ticket-404")) {
      return Promise.resolve({
        ok: false,
        status: 404,
        json: () => Promise.resolve({ error: { code: "not_found", message: "Missing." } }),
      });
    }
    if (url.endsWith("/api/v1/acgs")) {
      return Promise.resolve(jsonResponse({ acgs }));
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

export function jsonResponse(payload: unknown) {
  return { ok: true, json: () => Promise.resolve(payload) };
}
