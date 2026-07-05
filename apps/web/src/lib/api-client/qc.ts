import { apiRequestJson } from "./client";
import type { TicketState } from "./tickets";

type QcDraft = {
  id: string;
  versionNumber: number;
  title: string;
  summary: string;
  productType: string;
  content: string;
  createdByUserId: string;
  createdAt: string;
  assets: {
    id: string;
    name: string;
    assetType: string;
    mimeType: string;
    sizeBytes: number;
    sha256: string;
  }[];
};

export type QcProduct = {
  ticketId: string;
  reference: string;
  requesterUserId: string;
  state: TicketState;
  title: string;
  operationalQuestion: string | null;
  areaOrRegion: string | null;
  priority: string | null;
  requiredOutputFormat: string | null;
  checklistKeys: string[];
  latestDraft: QcDraft | null;
  managerNotes: string[];
  decisions: {
    id: string;
    status: "approved" | "rejected";
    reason: string;
    reviewerUserId: string;
    checklist: { key: string; passed: boolean }[];
    createdAt: string;
  }[];
  indexRecords: { id: string; productId: string; status: string; summary: string }[];
  disseminations: { id: string; productId: string; recipientUserId: string }[];
  feedbackRequests: { id: string; productId: string; requesterUserId: string; status: string }[];
  ingestedProduct: {
    id: string;
    reference: string;
    title: string;
    status: string;
    acgIds: string[];
  } | null;
};

export type QcQueue = {
  products: QcProduct[];
};

export type QcApprovalInput = {
  checklist: Record<string, boolean>;
  classificationLevel: number;
  releasability: string[];
  handlingCaveats: string[];
  acgIds: string[];
  reason: string;
};

export async function listQcQueue(): Promise<QcQueue> {
  return apiRequestJson<QcQueue>("/api/v1/qc/queue", { method: "GET" });
}

export async function getQcProduct(ticketId: string): Promise<QcProduct> {
  return apiRequestJson<QcProduct>(`/api/v1/qc/products/${ticketId}`, { method: "GET" });
}

export async function approveQcProduct(
  ticketId: string,
  payload: QcApprovalInput,
  csrfToken: string,
): Promise<QcProduct> {
  return apiRequestJson<QcProduct>(`/api/v1/qc/products/${ticketId}/approve`, {
    body: JSON.stringify(payload),
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
    method: "POST",
  });
}

export async function rejectQcProduct(
  ticketId: string,
  reason: string,
  csrfToken: string,
): Promise<QcProduct> {
  return apiRequestJson<QcProduct>(`/api/v1/qc/products/${ticketId}/reject`, {
    body: JSON.stringify({ reason }),
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
    method: "POST",
  });
}
