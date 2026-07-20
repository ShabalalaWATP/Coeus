import type { FlowState } from "./full-workflow-data";

const now = "2026-07-06T12:00:00Z";

export function draftProduct() {
  return {
    acgIds: ["acg-alpha"],
    areaOrRegion: "North Atlantic",
    assets: [
      {
        assetType: "pdf",
        id: "asset-1",
        mimeType: "application/pdf",
        name: "assessment-draft.pdf",
        previewAvailable: false,
        previewKind: "pdf",
        processingStatus: "ready",
        sha256: "e".repeat(64),
        sizeBytes: 512,
      },
    ],
    classificationLevel: 0,
    content: "Synthetic assessment content for QC review.",
    createdAt: now,
    description: "Synthetic assessment content for QC review.",
    handlingCaveats: ["MOCK DATA ONLY"],
    id: "draft-1",
    manifestHash: "f".repeat(64),
    ownerTeam: "RFA",
    productType: "assessment_report",
    releasability: ["MOCK"],
    sourceType: "analyst_submission",
    summary: "Synthetic assessment summary.",
    tags: ["mock"],
    title: "North Atlantic Assessment",
    versionNumber: 1,
  };
}

export function qcProduct(flow: FlowState) {
  return {
    agentPreflight: {
      blockers: [],
      checks: [
        {
          detail: "The uploaded product contains reviewable content.",
          key: "draft_complete",
          passed: true,
        },
        {
          detail: "Human QC and release controls remain mandatory.",
          key: "human_release_controls_pending",
          passed: true,
        },
      ],
      createdAt: now,
      draftVersionId: "draft-1",
      findings: [],
      id: "preflight-1",
      policyVersion: "qc-preflight-v1",
      status: "passed",
    },
    areaOrRegion: "North Atlantic",
    checklistKeys: ["source_checked", "classification_checked"],
    decisions: [],
    disseminations: flow.released
      ? [{ id: "dissemination-1", productId: "product-1", recipientUserId: "e2e-user" }]
      : [],
    feedbackRequests: flow.released
      ? [
          {
            id: "feedback-1",
            productId: "product-1",
            requesterUserId: "e2e-user",
            status: "requested",
          },
        ]
      : [],
    ingestedProduct:
      flow.stage === "release"
        ? {
            acgIds: ["acg-alpha"],
            id: "product-1",
            reference: "PROD-E2E",
            status: "published",
            title: "North Atlantic Assessment",
          }
        : null,
    indexRecords:
      flow.stage === "release"
        ? [{ id: "index-1", productId: "product-1", status: "indexed", summary: "Indexed." }]
        : [],
    latestDraft: draftProduct(),
    managerNotes: [],
    operationalQuestion: "What activity matters?",
    priority: "routine",
    reference: "TCK-E2E",
    requesterUserId: "e2e-user",
    requiredOutputFormat: "Assessment",
    state: flow.stage === "release" ? "DISSEMINATION_READY" : "QC_REVIEW",
    ticketId: "ticket-e2e",
    title: "North Atlantic Activity",
  };
}
