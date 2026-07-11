import {
  FileCheck2,
  MessageSquareText,
  PackageOpen,
  PenLine,
  Radar,
  Route,
  Send,
  type LucideIcon,
} from "lucide-react";

import type { TicketState } from "../../lib/api-client/tickets";

export type JourneyStage = {
  detail: string;
  icon: LucideIcon;
  label: string;
  states: TicketState[];
};

export const JOURNEY_STAGES: JourneyStage[] = [
  {
    label: "Describe the need",
    detail: "The customer chatbot captures the requirement in chat.",
    icon: MessageSquareText,
    states: ["DRAFT_INTAKE", "INFO_REQUIRED"],
  },
  {
    label: "Search existing intelligence",
    detail: "The RFI agent offers matching products before new tasking.",
    icon: Radar,
    states: ["RFI_SEARCHING", "RFI_MATCH_OFFERED", "RFI_NO_MATCH"],
  },
  {
    label: "JIOC route review",
    detail:
      "Capability agents advise and a JIOC team member decides whether collection is required.",
    icon: Route,
    states: ["JIOC_REVIEW", "COLLECT_CHOICE"],
  },
  {
    label: "Team production",
    detail: "The team manager assigns analysts who produce the draft product.",
    icon: PenLine,
    states: ["ANALYST_ASSIGNMENT", "ANALYST_IN_PROGRESS", "REWORK_REQUIRED"],
  },
  {
    label: "Manager approval",
    detail: "The team manager reviews the analysts' work before Quality Control.",
    icon: Send,
    states: ["MANAGER_APPROVAL"],
  },
  {
    label: "Quality control release",
    detail: "QC checks quality, classification and releasability, then releases the product.",
    icon: FileCheck2,
    states: ["QC_REVIEW"],
  },
  {
    label: "Delivered",
    detail: "The product reaches your dashboard, notifications and the store.",
    icon: PackageOpen,
    states: ["DISSEMINATION_READY", "CLOSED_DELIVERED", "CLOSED_EXISTING_PRODUCT_ACCEPTED"],
  },
];

export function stageIndexForState(state: TicketState) {
  const index = JOURNEY_STAGES.findIndex((stage) => stage.states.includes(state));
  return index === -1 ? 0 : index;
}
