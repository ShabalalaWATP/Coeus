import type { RoutingQueueKind } from "../../lib/api-client/routing";

export const TEAM_QUEUE_STATES = new Set([
  "ANALYST_ASSIGNMENT",
  "ANALYST_IN_PROGRESS",
  "MANAGER_APPROVAL",
  "MANAGER_REANALYSIS_REVIEW",
]);

export const QUEUE_LABELS: Record<
  RoutingQueueKind,
  { title: string; shortName: string; description: string; listTitle: string }
> = {
  jioc: {
    title: "JIOC Queue",
    shortName: "JIOC",
    description: "Decide whether progressed requests need collection, assessment or adjudication.",
    listTitle: "Route decisions",
  },
  rfa: {
    title: "RFA Queue",
    shortName: "RFA",
    description: "Assign analysts and manage the RFA team's active requests.",
    listTitle: "Team queue",
  },
  cm: {
    title: "Collection Queue",
    shortName: "Collection",
    description: "Assign analysts and manage the collection team's active requests.",
    listTitle: "Team queue",
  },
};
