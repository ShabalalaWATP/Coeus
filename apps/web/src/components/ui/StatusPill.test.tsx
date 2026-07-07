import { render, screen } from "@testing-library/react";

import { StatusPill } from "./StatusPill";
import { formatWorkflowState, toneForState } from "../../lib/workflow/state-format";

test("renders a formatted workflow state", () => {
  render(<StatusPill state="RFA_MANAGER_REVIEW" />);

  const pill = screen.getByText("RFA MANAGER REVIEW");
  expect(pill).toBeVisible();
  expect(pill).toHaveClass("status-pill--info");
});

test("formats workflow states for display", () => {
  expect(formatWorkflowState("ANALYST_IN_PROGRESS")).toBe("ANALYST IN PROGRESS");
});

test.each([
  ["QC_REJECTED", "critical"],
  ["ACCESS_DENIED", "critical"],
  ["INFO_REQUIRED", "warning"],
  ["DRAFT_INTAKE", "warning"],
  ["DISSEMINATION_READY", "success"],
  ["COMPLETE", "success"],
  ["CLOSED_DELIVERED", "success"],
  ["RFI_SEARCHING", "info"],
] as const)("maps %s to the %s tone", (state, tone) => {
  expect(toneForState(state)).toBe(tone);
});
