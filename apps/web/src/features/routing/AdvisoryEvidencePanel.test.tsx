import { render, screen } from "@testing-library/react";

import { AdvisoryEvidencePanel } from "./AdvisoryEvidencePanel";
import type { AdvisoryAgentRun } from "../../lib/api-client/routing";

function run(
  id: string,
  agent: AdvisoryAgentRun["advice"]["agent"],
  detail: string,
): AdvisoryAgentRun {
  return {
    id,
    agentName: `${agent}-agent`,
    status: "completed",
    summary: "Bounded advice completed.",
    safetyFlags: [],
    createdAt: "2026-07-20T10:00:00Z",
    advice: {
      agent,
      outcome: "provider_succeeded",
      verdict: agent === "routing_critic" ? "challenges" : null,
      shadowOnly: agent === "routing_critic",
      contextReferences: [],
      items: [
        {
          kind: agent === "routing_critic" ? "route_challenge" : "ambiguity",
          code: `${agent}.example`,
          detail,
          references: [],
        },
      ],
      providerAttempted: true,
    },
  };
}

test("presents each bounded role as non-authoritative staff evidence", () => {
  render(
    <AdvisoryEvidencePanel
      runs={[
        run("intake", "intake_planner", "Clarify which reporting period applies."),
        run("search", "search_planner", "Consider the alternative term maritime traffic."),
        run("critic", "routing_critic", "The route lacks current capability evidence."),
      ]}
    />,
  );

  expect(screen.getByRole("heading", { name: "Intake planner" })).toBeVisible();
  expect(screen.getByRole("heading", { name: "Search planner" })).toBeVisible();
  expect(screen.getByRole("heading", { name: "Routing critic" })).toBeVisible();
  expect(screen.getByText(/Deterministic controllers retain every permission/)).toBeVisible();
  expect(
    screen.getByText(
      "Advisory evidence only. The routing critic is shadow-only and cannot route or change workflow.",
    ),
  ).toBeVisible();
  expect(screen.getByText(/The route lacks current capability evidence/)).toBeVisible();
});

test("does not add an empty evidence section", () => {
  const { container } = render(<AdvisoryEvidencePanel runs={[]} />);
  expect(container).toBeEmptyDOMElement();
});
