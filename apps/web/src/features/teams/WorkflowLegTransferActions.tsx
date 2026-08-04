import { useState } from "react";

import {
  decideWorkflowLegTransfer,
  previewWorkflowLegTransfer,
  proposeWorkflowLegTransfer,
  type WorkflowLegTransferProposal,
  type WorkflowLegTransferResult,
} from "../../lib/api-client/workflow-leg-transfers";

type DecisionEvidence = {
  grantId: string;
  expectedGrantVersion: number;
  assignmentGrantId?: string;
  expectedAssignmentGrantVersion?: number;
  targetMembershipId?: string;
  expectedTargetMembershipVersion?: number;
  expectedTargetAccountCredentialVersion?: number;
  expectedTargetAccountSourceHash?: string;
};

type Props = {
  sourceUnitId: string;
  proposal: WorkflowLegTransferProposal;
  csrfToken: string;
  decisionEvidence: DecisionEvidence;
  pendingTransfer?: { transferId: string; version: number; previewHash: string };
  onChanged?: (result: WorkflowLegTransferResult) => void;
};

export function WorkflowLegTransferActions({
  sourceUnitId,
  proposal,
  csrfToken,
  decisionEvidence,
  pendingTransfer,
  onChanged,
}: Props) {
  const [previewHash, setPreviewHash] = useState<string>();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  async function preview() {
    await run(async () => {
      const result = await previewWorkflowLegTransfer(sourceUnitId, proposal, csrfToken);
      setPreviewHash(result.previewHash);
      setMessage(
        `Review ready: ${result.transferCount} of ${result.packageCount} packages will move.`,
      );
    });
  }

  async function submitProposal(reviewedPreviewHash: string) {
    await run(async () => {
      const result = await proposeWorkflowLegTransfer(
        sourceUnitId,
        proposal,
        reviewedPreviewHash,
        csrfToken,
      );
      setMessage("Transfer proposed to the receiving manager.");
      onChanged?.(result);
    });
  }

  async function decide(
    action: "accept" | "reject" | "cancel" | "expire",
    transfer: NonNullable<Props["pendingTransfer"]>,
  ) {
    await run(async () => {
      const result = await decideWorkflowLegTransfer(
        transfer.transferId,
        {
          expectedTransferVersion: transfer.version,
          action,
          previewHash: action === "accept" ? transfer.previewHash : undefined,
          ...decisionEvidence,
        },
        csrfToken,
      );
      setMessage(`Transfer ${result.state}.`);
      onChanged?.(result);
    });
  }

  async function run(operation: () => Promise<void>) {
    setBusy(true);
    setMessage("");
    try {
      await operation();
    } catch {
      setMessage("The transfer could not be completed. Refresh the work and try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-labelledby="workflow-transfer-title">
      <h3 id="workflow-transfer-title">Move work to another team</h3>
      <p>Both teams must approve. Personnel remain in their current home teams.</p>
      {!pendingTransfer ? (
        <div>
          <button disabled={busy} onClick={() => void preview()} type="button">
            Review transfer
          </button>
          {previewHash ? (
            <button disabled={busy} onClick={() => void submitProposal(previewHash)} type="button">
              Send proposal
            </button>
          ) : null}
        </div>
      ) : (
        <div aria-label="Transfer decision">
          <button
            disabled={busy}
            onClick={() => void decide("accept", pendingTransfer)}
            type="button"
          >
            Accept work
          </button>
          <button
            disabled={busy}
            onClick={() => void decide("reject", pendingTransfer)}
            type="button"
          >
            Reject
          </button>
          <button
            disabled={busy}
            onClick={() => void decide("cancel", pendingTransfer)}
            type="button"
          >
            Cancel proposal
          </button>
          <button
            disabled={busy}
            onClick={() => void decide("expire", pendingTransfer)}
            type="button"
          >
            Mark expired
          </button>
        </div>
      )}
      <p aria-live="polite">{message}</p>
    </section>
  );
}
