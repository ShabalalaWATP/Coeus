import { afterEach, describe, expect, it, vi } from "vitest";

import {
  decideWorkflowLegTransfer,
  previewWorkflowLegTransfer,
  proposeWorkflowLegTransfer,
  type WorkflowLegTransferProposal,
} from "./workflow-leg-transfers";

const proposal: WorkflowLegTransferProposal = {
  transferId: "transfer-1",
  ticketId: "ticket-1",
  workflowLeg: "rfa",
  targetUnitId: "target-unit",
  targetUserId: "target-user",
  expectedOwnershipVersion: 2,
  expectedTicketVersion: 3,
  expectedTicketSourceHash: "a".repeat(64),
  authorisingGrantId: "source-grant",
  expectedGrantVersion: 1,
  expiresAt: "2026-08-06T12:00:00Z",
  packages: [{ packageId: "package-1", disposition: "retain", expectedVersion: 1 }],
  reason: "Balance work",
};

describe("workflow-leg transfer client", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("previews and proposes using the source-team boundary", async () => {
    const fetch = vi
      .fn()
      .mockResolvedValueOnce(response({ previewHash: "b".repeat(64) }))
      .mockResolvedValueOnce(response({ state: "proposed" }));
    vi.stubGlobal("fetch", fetch);
    vi.stubGlobal("crypto", { randomUUID: () => "generated-id" });

    await previewWorkflowLegTransfer("source/unit", proposal, "csrf");
    await proposeWorkflowLegTransfer("source/unit", proposal, "b".repeat(64), "csrf");

    expect(fetch.mock.calls[0][0]).toContain("sources/source%2Funit/previews");
    expect(fetch.mock.calls[1][0]).toContain("sources/source%2Funit/proposals");
    expect(requestBody(fetch, 1)).toMatchObject({
      commandId: "generated-id",
      previewHash: "b".repeat(64),
    });
  });

  it("sends receiving-manager decision evidence", async () => {
    const fetch = vi.fn().mockResolvedValue(response({ state: "accepted" }));
    vi.stubGlobal("fetch", fetch);
    vi.stubGlobal("crypto", { randomUUID: () => "decision-id" });

    await decideWorkflowLegTransfer(
      "transfer/id",
      {
        action: "accept",
        expectedTransferVersion: 1,
        grantId: "transfer-grant",
        expectedGrantVersion: 2,
        assignmentGrantId: "assignment-grant",
        expectedAssignmentGrantVersion: 3,
      },
      "csrf",
    );

    expect(fetch.mock.calls[0][0]).toContain("transfer%2Fid/commands");
    expect(requestBody(fetch, 0)).toMatchObject({
      action: "accept",
      assignmentGrantId: "assignment-grant",
    });
  });
});

/** Read one recorded request body without losing its type through `any`. */
function requestBody(fetch: ReturnType<typeof vi.fn>, call: number): unknown {
  const calls = fetch.mock.calls as [string, { body: string }][];
  return JSON.parse(calls[call][1].body);
}

function response(body: object) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}
