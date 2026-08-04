import { apiRequestJson } from "./client";

export type TeamCapacityForecast = {
  unitId: string;
  windowStart: string;
  windowEnd: string;
  status: "ready" | "partial" | "unknown";
  peopleConsidered: number;
  peopleIncluded: number;
  peopleUnknown: number;
  physicalMinutes: number;
  unavailableMinutes: number;
  reservationMinutes: number;
  capacityReductionMinutes: number;
  policyBufferMinutes: number;
  assignableMinutes: number;
  asOf: string;
};

export function getTeamCapacityForecast(
  unitId: string,
  grantId: string,
  windowStart: string,
  windowEnd: string,
): Promise<TeamCapacityForecast> {
  const query = new URLSearchParams({
    authorisingGrantId: grantId,
    windowStart,
    windowEnd,
  });
  return apiRequestJson(
    `/api/v1/organisation/workspaces/${encodeURIComponent(unitId)}/capacity?${query.toString()}`,
    { method: "GET" },
  );
}
