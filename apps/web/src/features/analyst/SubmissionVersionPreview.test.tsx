import { render, screen } from "@testing-library/react";

import { SubmissionVersionPreview } from "./SubmissionVersionPreview";
import type { AnalystTask } from "../../lib/api-client/analyst";

const task: AnalystTask = {
  ticketId: "ticket-1",
  reference: "TCK-1",
  state: "ANALYST_IN_PROGRESS",
  title: "Synthetic assessment",
  description: null,
  operationalQuestion: null,
  areaOrRegion: null,
  priority: null,
  requiredOutputFormat: null,
  chatSummary: [],
  managerNotes: [],
  assignments: [],
  workPackages: [],
  notes: [],
  linkedProducts: [],
  drafts: [],
};

test("explains when no product version has been uploaded", () => {
  render(<SubmissionVersionPreview task={task} />);

  expect(screen.getByText("No product version has been uploaded.")).toBeVisible();
});

test("shows legacy content when a draft has no controlled preview", () => {
  render(
    <SubmissionVersionPreview
      task={{
        ...task,
        drafts: [
          {
            id: "draft-1",
            versionNumber: 1,
            title: "Legacy assessment",
            summary: "MOCK DATA ONLY summary.",
            productType: "assessment",
            content: "MOCK DATA ONLY legacy content.",
            createdAt: "2026-07-18T00:00:00Z",
            assets: [],
            description: "Synthetic description",
            sourceType: "legacy",
            ownerTeam: "RFA",
            areaOrRegion: "Test region",
            classificationLevel: 0,
            releasability: ["MOCK"],
            handlingCaveats: ["MOCK DATA ONLY"],
            tags: [],
            acgIds: [],
            manifestHash: "",
          },
        ],
      }}
    />,
  );

  expect(screen.getByText("Legacy draft")).toBeVisible();
  expect(screen.getByText("No file")).toBeVisible();
  expect(screen.getByText("MOCK DATA ONLY legacy content.")).toBeVisible();
});
