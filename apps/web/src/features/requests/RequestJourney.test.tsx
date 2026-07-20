import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";

import { stageIndexForState } from "./journey-stages";
import { RequestJourney } from "./RequestJourney";

test("maps workflow states onto journey stages with a safe fallback", () => {
  expect(stageIndexForState("DRAFT_INTAKE")).toBe(0);
  expect(stageIndexForState("RFI_NO_MATCH")).toBe(1);
  expect(stageIndexForState("RFI_SEARCH_INCOMPLETE")).toBe(1);
  expect(stageIndexForState("NEW_TASKING_CONSENT")).toBe(1);
  expect(stageIndexForState("JIOC_ROUTING_PENDING")).toBe(2);
  expect(stageIndexForState("MANAGER_APPROVAL")).toBe(4);
  expect(stageIndexForState("QC_REVIEW")).toBe(5);
  expect(stageIndexForState("CLOSED_DELIVERED")).toBe(6);
  expect(stageIndexForState("CANCELLED")).toBe(0);
});

test("marks the delivered stage for confirmed deliveries", () => {
  render(<RequestJourney onClose={vi.fn()} state="CLOSED_DELIVERED" />);

  expect(screen.getByText("Delivered").closest("li")).toHaveClass("journey-step--current");
});

test("marks the current stage and closes on escape", async () => {
  const onClose = vi.fn();
  render(<RequestJourney onClose={onClose} state="JIOC_REVIEW" />);

  const current = screen.getByText("JIOC routing").closest("li");
  expect(current).toHaveClass("journey-step--current");
  expect(screen.getByText("You are here")).toBeVisible();
  expect(screen.getByText("Describe the need").closest("li")).toHaveClass("journey-step--done");
  expect(screen.getByText("Delivered").closest("li")).toHaveClass("journey-step--next");

  await userEvent.keyboard("{Escape}");
  expect(onClose).toHaveBeenCalledTimes(1);
});

test("closes on overlay click but not on dialog click", async () => {
  const onClose = vi.fn();
  render(<RequestJourney onClose={onClose} state="DRAFT_INTAKE" />);

  await userEvent.click(screen.getByRole("dialog"));
  expect(onClose).not.toHaveBeenCalled();

  await userEvent.click(screen.getByRole("presentation"));
  expect(onClose).toHaveBeenCalledTimes(1);
});

test("keeps keyboard focus inside the journey dialog", async () => {
  render(<RequestJourney onClose={vi.fn()} state="DRAFT_INTAKE" />);
  const close = screen.getByRole("button", { name: "Close journey" });
  expect(close).toHaveFocus();

  await userEvent.keyboard("{Tab}");
  expect(close).toHaveFocus();
  await userEvent.keyboard("{Shift>}{Tab}{/Shift}");
  expect(close).toHaveFocus();
});

test("explains when an existing product satisfied the request", () => {
  render(<RequestJourney onClose={vi.fn()} state="CLOSED_EXISTING_PRODUCT_ACCEPTED" />);

  expect(screen.getByText(/existing product satisfied this request/)).toBeVisible();
  expect(screen.getByText("Delivered").closest("li")).toHaveClass("journey-step--current");
});

test("explains a cancelled request without marking a current stage", () => {
  render(<RequestJourney onClose={vi.fn()} state="CANCELLED" />);

  expect(screen.getByText(/this request was cancelled/i)).toBeVisible();
  expect(screen.queryByText("You are here")).not.toBeInTheDocument();
  expect(screen.getByText("Describe the need").closest("li")).toHaveClass("journey-step--next");
});

test("closes from the header close button", async () => {
  const onClose = vi.fn();
  render(<RequestJourney onClose={onClose} state="ANALYST_IN_PROGRESS" />);

  await userEvent.click(screen.getByRole("button", { name: "Close journey" }));
  expect(onClose).toHaveBeenCalledTimes(1);
});

test("renders server-projected complete, current and not-required stages", () => {
  render(
    <RequestJourney
      journey={[
        { code: "intake", label: "Intake checked", status: "complete" },
        { code: "routing", label: "Routing now", status: "current" },
        { code: "collection", label: "Collection skipped", status: "not_required" },
      ]}
      onClose={vi.fn()}
      state="JIOC_REVIEW"
    />,
  );

  expect(screen.getByText("Intake checked").closest("li")).toHaveClass("journey-step--done");
  expect(screen.getByText("Routing now").closest("li")).toHaveClass("journey-step--current");
  expect(screen.getByText("Collection skipped").closest("li")).toHaveClass("journey-step--next");
  expect(screen.getAllByText("Tracked by the workflow service.")).toHaveLength(3);
});
