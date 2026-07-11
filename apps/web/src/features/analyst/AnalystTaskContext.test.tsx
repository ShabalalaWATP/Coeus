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
