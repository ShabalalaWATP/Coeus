import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Check, X } from "lucide-react";
import type { FormEvent } from "react";
import { useMemo, useState } from "react";

import { useAuth } from "../../lib/auth/auth-context";
import {
  executeDeactivation,
  executeReparent,
  listManagementGrants,
  previewDeactivation,
  previewReparent,
  type DeactivationPreview,
  type DeactivationRequest,
  type OrganisationUnit,
  type ReparentPreview,
  type ReparentRequest,
} from "../../lib/api-client/organisation-admin";

type StructureMode = "deactivate" | "reparent";
type Previewed =
  | { mode: "deactivate"; impact: DeactivationPreview; request: DeactivationRequest }
  | { mode: "reparent"; impact: ReparentPreview; request: ReparentRequest };

type StructurePanelProps = {
  mode: StructureMode;
  onClose: () => void;
  target?: OrganisationUnit;
  unit: OrganisationUnit;
};

export function OrganisationStructurePanel({ mode, onClose, target, unit }: StructurePanelProps) {
  const { session } = useAuth();
  const queryClient = useQueryClient();
  const [reason, setReason] = useState("");
  const [grantId, setGrantId] = useState("");
  const [previewed, setPreviewed] = useState<Previewed>();
  const grants = useQuery({
    queryKey: ["organisation-grants", "all-active"],
    queryFn: () => listManagementGrants(),
  });
  const action = mode === "reparent" ? "organisation:reparent" : "organisation:restructure";
  const applicableGrants = useMemo(
    () => grants.data?.filter((grant) => grant.revokedAt === null && grant.action === action) ?? [],
    [action, grants.data],
  );
  const operation = useMutation({
    mutationFn: async (input: { execute?: boolean; previewed?: Previewed }) => {
      const csrf = session?.csrfToken ?? "";
      if (input.execute && input.previewed) {
        return input.previewed.mode === "reparent"
          ? executeReparent(input.previewed.request, input.previewed.impact.previewHash, csrf)
          : executeDeactivation(input.previewed.request, input.previewed.impact.previewHash, csrf);
      }
      return mode === "reparent"
        ? buildReparentPreview(unit, target, grantId, reason, csrf)
        : buildDeactivationPreview(unit, grantId, reason, csrf);
    },
  });

  const requestPreview = (event: FormEvent) => {
    event.preventDefault();
    operation.mutate(
      {},
      {
        onSuccess: (result) => {
          if (!("preview" in result)) return;
          setPreviewed(toPreviewed(mode, result));
        },
      },
    );
  };

  const confirm = () => {
    if (!previewed) return;
    operation.mutate(
      { execute: true, previewed },
      {
        onSuccess: (result) => {
          if ("preview" in result) return;
          void queryClient.invalidateQueries({ queryKey: ["organisation-units"] });
          onClose();
        },
      },
    );
  };

  const blockingCount =
    previewed?.mode === "deactivate" ? previewed.impact.impact.blockingCount : 0;

  return (
    <section className="organisation-mutation" aria-labelledby="organisation-structure-title">
      <header>
        <div>
          <span className="eyebrow">Structural change</span>
          <h2 id="organisation-structure-title">
            {mode === "reparent" ? `Move ${unit.shortName}` : `Deactivate ${unit.shortName}`}
          </h2>
        </div>
        <button aria-label="Close structural change" onClick={onClose} type="button">
          <X aria-hidden="true" size={18} />
        </button>
      </header>
      {mode === "reparent" ? (
        <p>
          New parent: <strong>{target?.name}</strong>
        </p>
      ) : (
        <p className="organisation-mutation__warning">
          <AlertTriangle aria-hidden="true" size={17} />
          Deactivation is accepted only when all blocking dependencies have been resolved.
        </p>
      )}
      <form onSubmit={requestPreview}>
        <label>
          Authorising grant
          <select
            disabled={previewed !== undefined}
            onChange={(event) => setGrantId(event.target.value)}
            required
            value={grantId}
          >
            <option value="">Select a grant</option>
            {applicableGrants.map((grant) => (
              <option key={grant.id} value={grant.id}>
                {grant.includeDescendants ? "Descendant authority" : "Direct authority"} · granted{" "}
                {new Date(grant.validFrom).toLocaleDateString("en-GB")}
              </option>
            ))}
          </select>
        </label>
        <label>
          Reason
          <input
            disabled={previewed !== undefined}
            maxLength={500}
            onChange={(event) => setReason(event.target.value)}
            required
            value={reason}
          />
        </label>
        {grants.isSuccess && applicableGrants.length === 0 ? (
          <p className="organisation-mutation__warning" role="alert">
            No active {mode} grant is available to this account.
          </p>
        ) : null}
        {operation.isError ? <p role="alert">{operation.error.message}</p> : null}
        <button
          disabled={operation.isPending || applicableGrants.length === 0 || previewed !== undefined}
          type="submit"
        >
          Review impact
        </button>
      </form>
      {previewed ? (
        <div className="organisation-mutation__preview" role="status">
          <div>
            <Check aria-hidden="true" size={18} />
            <strong>Impact checked</strong>
          </div>
          <p>{impactSummary(previewed)}</p>
          <button
            disabled={operation.isPending || blockingCount > 0}
            onClick={confirm}
            type="button"
          >
            Confirm {mode === "reparent" ? "move" : "deactivation"}
          </button>
        </div>
      ) : null}
    </section>
  );
}

async function buildReparentPreview(
  unit: OrganisationUnit,
  target: OrganisationUnit | undefined,
  grantId: string,
  reason: string,
  csrf: string,
) {
  if (!target) throw new Error("Select a new parent unit.");
  const request: ReparentRequest = {
    unitId: unit.id,
    newParentId: target.id,
    expectedUnitVersion: unit.version,
    expectedParentVersion: target.version,
    authorisingGrantId: grantId,
    reason: reason.trim(),
  };
  return { preview: await previewReparent(request, csrf), request };
}

async function buildDeactivationPreview(
  unit: OrganisationUnit,
  grantId: string,
  reason: string,
  csrf: string,
) {
  const request: DeactivationRequest = {
    unitId: unit.id,
    expectedVersion: unit.version,
    authorisingGrantId: grantId,
    reason: reason.trim(),
  };
  return { preview: await previewDeactivation(request, csrf), request };
}

function toPreviewed(
  mode: StructureMode,
  result: {
    preview: DeactivationPreview | ReparentPreview;
    request: DeactivationRequest | ReparentRequest;
  },
): Previewed {
  return mode === "reparent"
    ? {
        mode,
        impact: result.preview as ReparentPreview,
        request: result.request as ReparentRequest,
      }
    : {
        mode,
        impact: result.preview as DeactivationPreview,
        request: result.request as DeactivationRequest,
      };
}

function impactSummary(previewed: Previewed) {
  if (previewed.mode === "reparent") {
    const impact = previewed.impact.impact;
    return `${impact.descendants} descendants, ${impact.memberships} memberships and ${impact.activeTaskLegs} active task legs move with this unit.`;
  }
  const impact = previewed.impact.impact;
  return impact.blockingCount > 0
    ? `${impact.blockingCount} blocking dependencies must be resolved before deactivation.`
    : "No blocking dependencies were found. The unit can be safely deactivated.";
}
