import { render, screen } from "@testing-library/react";

import { AnalystTaskContext } from "./AnalystTaskContext";
import type { AnalystTask } from "../../lib/api-client/analyst";

const baseTask: AnalystTask = {
  ticketId: "ticket-1",
  reference: "TCK-0001",
  state: "ANALYST_IN_PROGRESS",
  title: "Arctic Fisheries Assessment",
  description: "Assess mock fisheries activity.",
  operationalQuestion: "What activity needs command attention?",
  areaOrRegion: "Arctic fisheries",
  priority: "high",
  requiredOutputFormat: "assessment report",
  chatSummary: [],
  managerNotes: [],
  assignments: [],
  workPackages: [],
  notes: [],
  linkedProducts: [],
  drafts: [],
};

test("falls back to sensible labels when nothing is assigned yet", () => {
  render(<AnalystTaskContext task={{ ...baseTask, areaOrRegion: null }} />);

  expect(screen.getByText("Not assigned")).toBeVisible();
  expect(screen.getByText("Not set")).toBeVisible();
});

test("shows the first active assignment's team", () => {
  render(
    <AnalystTaskContext
      task={{
        ...baseTask,
        assignments: [
          {
            id: "assignment-1",
            analystUserId: "analyst-1",
            assignedByUserId: "manager-1",
            route: "rfa",
            createdAt: "2026-07-05T00:00:00Z",
            teamName: "Maritime Assessment Cell",
          },
        ],
      }}
    />,
  );

  expect(screen.getByText("Maritime Assessment Cell")).toBeVisible();
});

test("shows missing context fallbacks and supplied requester and manager context", () => {
  render(
    <AnalystTaskContext
      task={{
        ...baseTask,
        description: null,
        operationalQuestion: null,
        priority: null,
        requiredOutputFormat: null,
        chatSummary: ["Requester needs a decision-ready summary."],
        managerNotes: ["Separate evidence from assessment."],
      }}
    />,
  );

  expect(screen.getByText("No operational question was supplied.")).toBeVisible();
  expect(screen.getByText("No background description was supplied.")).toBeVisible();
  expect(screen.getByText("Requester needs a decision-ready summary.")).toBeVisible();
  expect(screen.getByText("Separate evidence from assessment.")).toBeVisible();
});
