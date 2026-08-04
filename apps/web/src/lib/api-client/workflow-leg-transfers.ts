import { apiRequestJson, pathSegment } from "./client";

type PackageTransferPlan = {
  packageId: string;
  disposition: "transfer" | "complete" | "cancel" | "retain";
  expectedVersion: number;
  reservationId?: string;
  reservationIdempotencyKey?: string;
  startsAt?: string;
  endsAt?: string;
  reservedMinutes?: number;
};

export type WorkflowLegTransferProposal = {
  transferId: string;
  ticketId: string;
  workflowLeg: "rfa" | "cm_collection" | "cm_analysis" | "qc";
  targetUnitId: string;
  targetUserId: string;
  expectedOwnershipVersion: number;
  expectedTicketVersion: number;
  expectedTicketSourceHash: string;
  authorisingGrantId: string;
  expectedGrantVersion: number;
  expiresAt: string;
  packages: PackageTransferPlan[];
  reason: string;
};

export type WorkflowLegTransferPreview = {
  previewHash: string;
  transferId: string;
  ticketId: string;
  sourceUnitId: string;
  targetUnitId: string;
  packageCount: number;
  transferCount: number;
  expiresAt: string;
};

export type WorkflowLegTransferResult = {
  transferId: string;
  state: "proposed" | "accepted" | "rejected" | "cancelled" | "expired";
  version: number;
  replayed: boolean;
};

type TransferCommand = {
  expectedTransferVersion: number;
  action: "accept" | "reject" | "cancel" | "expire";
  previewHash?: string;
  grantId: string;
  expectedGrantVersion: number;
  targetMembershipId?: string;
  expectedTargetMembershipVersion?: number;
  expectedTargetAccountCredentialVersion?: number;
  expectedTargetAccountSourceHash?: string;
  assignmentGrantId?: string;
  expectedAssignmentGrantVersion?: number;
  reason?: string;
};

const headers = (csrfToken: string) => ({
  "Content-Type": "application/json",
  "X-CSRF-Token": csrfToken,
});

export function previewWorkflowLegTransfer(
  sourceUnitId: string,
  proposal: WorkflowLegTransferProposal,
  csrfToken: string,
): Promise<WorkflowLegTransferPreview> {
  return apiRequestJson(
    `/api/v1/organisation/workflow-leg-transfers/sources/${pathSegment(sourceUnitId)}/previews`,
    {
      method: "POST",
      headers: headers(csrfToken),
      body: JSON.stringify(proposal),
    },
  );
}

export function proposeWorkflowLegTransfer(
  sourceUnitId: string,
  proposal: WorkflowLegTransferProposal,
  previewHash: string,
  csrfToken: string,
): Promise<WorkflowLegTransferResult> {
  return apiRequestJson(
    `/api/v1/organisation/workflow-leg-transfers/sources/${pathSegment(sourceUnitId)}/proposals`,
    {
      method: "POST",
      headers: headers(csrfToken),
      body: JSON.stringify({
        commandId: crypto.randomUUID(),
        idempotencyKey: `workflow-transfer-propose-${crypto.randomUUID()}`,
        proposal,
        previewHash,
      }),
    },
  );
}

export function decideWorkflowLegTransfer(
  transferId: string,
  command: TransferCommand,
  csrfToken: string,
): Promise<WorkflowLegTransferResult> {
  return apiRequestJson(
    `/api/v1/organisation/workflow-leg-transfers/${pathSegment(transferId)}/commands`,
    {
      method: "POST",
      headers: headers(csrfToken),
      body: JSON.stringify({
        commandId: crypto.randomUUID(),
        idempotencyKey: `workflow-transfer-${command.action}-${crypto.randomUUID()}`,
        ...command,
      }),
    },
  );
}
