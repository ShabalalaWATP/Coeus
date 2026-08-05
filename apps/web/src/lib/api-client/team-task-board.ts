import { apiRequestJson } from "./client";
import type { components } from "./generated/openapi";

type ApiSchemas = components["schemas"];

export type TeamTaskBoard = ApiSchemas["TeamTaskBoardResponse"];
export type TeamTaskCard = ApiSchemas["TeamTaskCardResponse"];
export type TeamTaskPackage = ApiSchemas["TeamTaskPackageResponse"];

export type TeamBoardColumn = TeamTaskCard["column"];
export type TeamBoardQuery = {
  includeCompleted?: boolean;
  scope?: "direct" | "descendants";
  columns?: TeamBoardColumn[];
  unitIds?: string[];
  priority?: string;
  dueFrom?: string;
  dueTo?: string;
  completedAfter?: string;
  cursor?: string | null;
  limit?: number;
};

export function getTeamTaskBoard(
  unitId: string,
  options: boolean | TeamBoardQuery = false,
): Promise<TeamTaskBoard> {
  const resolved = typeof options === "boolean" ? { includeCompleted: options } : options;
  const query = new URLSearchParams({
    includeCompleted: String(resolved.includeCompleted ?? false),
    limit: String(resolved.limit ?? 100),
  });
  if (resolved.scope) query.set("scope", resolved.scope);
  resolved.columns?.forEach((value) => query.append("column", value));
  resolved.unitIds?.forEach((value) => query.append("unitId", value));
  if (resolved.priority) query.set("priority", resolved.priority);
  if (resolved.dueFrom) query.set("dueFrom", resolved.dueFrom);
  if (resolved.dueTo) query.set("dueTo", resolved.dueTo);
  if (resolved.completedAfter) query.set("completedAfter", resolved.completedAfter);
  if (resolved.cursor) query.set("cursor", resolved.cursor);
  return apiRequestJson(
    `/api/v1/organisation/workspaces/${encodeURIComponent(unitId)}/board?${query}`,
    {
      method: "GET",
    },
  );
}
