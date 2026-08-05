import { apiRequestJson } from "./client";

export type MyWorkColumn =
  "ready" | "in_progress" | "blocked" | "review" | "rework" | "on_hold" | "completed";

export type MyWorkCard = {
  ticketId: string;
  workflowLeg: "rfa" | "cm_collection" | "cm_analysis" | "qc";
  packageId: string;
  reference: string;
  ticketTitle: string;
  packageTitle: string;
  column: MyWorkColumn;
  priority: number | null;
  targetDate: string | null;
  dueAt: string | null;
  blockedCode: string | null;
  reviewAt: string | null;
  ticketVersion: number;
  ownershipVersion: number;
  packageVersion: number;
};

export type MyWorkPage = {
  cards: MyWorkCard[];
  asOf: string;
  nextCursor: string | null;
};

export type MyWorkQuery = {
  includeCompleted?: boolean;
  column?: MyWorkColumn | "";
  cursor?: string | null;
  limit?: number;
};

export function listMyWork(options: number | MyWorkQuery = 5): Promise<MyWorkPage> {
  const resolved = typeof options === "number" ? { limit: options } : options;
  const query = new URLSearchParams({
    includeCompleted: String(resolved.includeCompleted ?? false),
    limit: String(resolved.limit ?? 25),
  });
  if (resolved.column) query.set("column", resolved.column);
  if (resolved.cursor) query.set("cursor", resolved.cursor);
  return apiRequestJson(`/api/v1/organisation/workspaces/my-work?${query.toString()}`, {
    method: "GET",
  });
}
