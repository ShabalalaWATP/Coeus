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
    label: "Route review",
    detail: "Capability agents advise and an RFA or Collection manager approves the path.",
    icon: Route,
    states: ["ROUTE_ASSESSMENT", "RFA_MANAGER_REVIEW", "CM_MANAGER_REVIEW"],
  },
  {
    label: "Analyst production",
    detail: "An assigned analyst produces the draft product.",
    icon: PenLine,
    states: ["ANALYST_ASSIGNMENT", "ANALYST_IN_PROGRESS", "REWORK_REQUIRED"],
  },
  {
    label: "Quality control",
    detail: "QC checks quality, classification and releasability.",
    icon: FileCheck2,
    states: ["QC_REVIEW"],
  },
  {
    label: "Manager release",
    detail: "The owning RFA or Collection manager performs the final release.",
    icon: Send,
    states: ["MANAGER_RELEASE"],
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
