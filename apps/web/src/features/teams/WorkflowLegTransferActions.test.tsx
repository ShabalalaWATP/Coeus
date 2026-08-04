import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";

import { renderWithProviders } from "../../test/test-utils";
import { WorkflowLegTransferActions } from "./WorkflowLegTransferActions";

const api = vi.hoisted(() => ({
  preview: vi.fn(),
  propose: vi.fn(),
  decide: vi.fn(),
}));

vi.mock("../../lib/api-client/workflow-leg-transfers", () => ({
  previewWorkflowLegTransfer: api.preview,
  proposeWorkflowLegTransfer: api.propose,
  decideWorkflowLegTransfer: api.decide,
}));

const props = {
  sourceUnitId: "source",
  csrfToken: "csrf",
  proposal: {
    transferId: "transfer",
    ticketId: "ticket",
    workflowLeg: "rfa" as const,
    targetUnitId: "target",
    targetUserId: "analyst",
    expectedOwnershipVersion: 1,
    expectedTicketVersion: 1,
    expectedTicketSourceHash: "a".repeat(64),
    authorisingGrantId: "grant",
    expectedGrantVersion: 1,
    expiresAt: "2026-08-06T12:00:00Z",
    packages: [{ packageId: "package", disposition: "transfer" as const, expectedVersion: 1 }],
    reason: "Balance work",
  },
  decisionEvidence: { grantId: "grant", expectedGrantVersion: 1 },
};

beforeEach(() => {
  vi.clearAllMocks();
  api.preview.mockResolvedValue({ previewHash: "b".repeat(64), transferCount: 1, packageCount: 2 });
  api.propose.mockResolvedValue({ transferId: "transfer", state: "proposed", version: 1 });
  api.decide.mockResolvedValue({ transferId: "transfer", state: "accepted", version: 2 });
});

it("reviews before sending a source proposal", async () => {
  const changed = vi.fn();
  renderWithProviders(<WorkflowLegTransferActions {...props} onChanged={changed} />);
  await userEvent.click(screen.getByRole("button", { name: "Review transfer" }));
  expect(await screen.findByText(/1 of 2 packages/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Send proposal" }));
  expect(api.propose).toHaveBeenCalledWith("source", props.proposal, "b".repeat(64), "csrf");
  expect(changed).toHaveBeenCalled();
});

it.each(["Accept work", "Reject", "Cancel proposal", "Mark expired"])(
  "submits the %s decision",
  async (label) => {
    renderWithProviders(
      <WorkflowLegTransferActions
        {...props}
        onChanged={label === "Accept work" ? vi.fn() : undefined}
        pendingTransfer={{
          transferId: "transfer",
          version: 1,
          previewHash: "b".repeat(64),
        }}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: label }));
    expect(api.decide).toHaveBeenCalled();
  },
);

it("uses a generic failure message", async () => {
  api.preview.mockRejectedValue(new Error("private detail"));
  renderWithProviders(<WorkflowLegTransferActions {...props} />);
  await userEvent.click(screen.getByRole("button", { name: "Review transfer" }));
  expect(await screen.findByText(/could not be completed/)).toBeInTheDocument();
  expect(screen.queryByText("private detail")).not.toBeInTheDocument();
});
