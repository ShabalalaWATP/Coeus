import type { AnalystTask } from "./analyst";
import { apiRequestJson, pathSegment } from "./client";

type AssignmentRecommendationCandidate = {
  unitId: string;
  analystUserId: string;
  displayName: string;
  rank: number;
  assignableMinutes: number;
  activeWip: number;
  explanationCodes: string[];
};

export type AssignmentRecommendation = {
  recommendationId: string;
  estimateId: string;
  estimateVersion: number;
  holdId: string;
  previewHash: string;
  expiresAt: string;
  candidates: AssignmentRecommendationCandidate[];
  exclusionCounts: Record<string, number>;
};

export type AssignmentDemandInput = {
  effortMinMinutes: number;
  effortMaxMinutes: number;
  deadline: string;
  capabilityIds: string[];
  unitId: string | null;
};

export function previewAssignmentRecommendation(
  ticketId: string,
  demand: AssignmentDemandInput,
  csrfToken: string,
): Promise<AssignmentRecommendation> {
  return apiRequestJson(
    `/api/v1/analyst/tasks/${pathSegment(ticketId)}/assignment-recommendations/preview`,
    {
      body: JSON.stringify(demand),
      headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
      method: "POST",
    },
  );
}

export function acceptAssignmentRecommendation(
  ticketId: string,
  recommendation: AssignmentRecommendation,
  selectedUnitId: string,
  selectedAnalystUserId: string,
  overrideReason: string,
  csrfToken: string,
): Promise<AnalystTask> {
  return apiRequestJson(
    `/api/v1/analyst/tasks/${pathSegment(ticketId)}/assignment-recommendations/accept`,
    {
      body: JSON.stringify({
        recommendationId: recommendation.recommendationId,
        previewHash: recommendation.previewHash,
        selectedUnitId,
        selectedAnalystUserId,
        overrideReason,
        workPackages: [],
      }),
      headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
      method: "POST",
    },
  );
}
