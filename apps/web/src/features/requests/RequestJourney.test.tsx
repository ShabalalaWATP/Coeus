import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";

import { stageIndexForState } from "./journey-stages";
import { RequestJourney } from "./RequestJourney";

test("maps workflow states onto journey stages with a safe fallback", () => {
  expect(stageIndexForState("DRAFT_INTAKE")).toBe(0);
  expect(stageIndexForState("QC_REVIEW")).toBe(4);
  expect(stageIndexForState("MANAGER_RELEASE")).toBe(5);
  expect(stageIndexForState("CANCELLED")).toBe(0);
});

test("marks the current stage and closes on escape", async () => {
  const onClose = vi.fn();
  render(<RequestJourney onClose={onClose} state="ROUTE_ASSESSMENT" />);

  const current = screen.getByText("Route review").closest("li");
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

test("explains when an existing product satisfied the request", () => {
  render(<RequestJourney onClose={vi.fn()} state="CLOSED_EXISTING_PRODUCT_ACCEPTED" />);

  expect(screen.getByText(/existing product satisfied this request/)).toBeVisible();
  expect(screen.getByText("Delivered").closest("li")).toHaveClass("journey-step--current");
});

test("closes from the header close button", async () => {
  const onClose = vi.fn();
  render(<RequestJourney onClose={onClose} state="ANALYST_IN_PROGRESS" />);

  await userEvent.click(screen.getByRole("button", { name: "Close journey" }));
  expect(onClose).toHaveBeenCalledTimes(1);
});
