import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, GitMerge, X } from "lucide-react";
import { useMemo, useState, type FormEvent } from "react";

import {
  assessMerge,
  executeMerge,
  listManagementGrants,
  listOrganisationUnits,
  previewMerge,
  type MergeImpact,
  type MergePlan,
  type MergePreview,
  type MergeRequest,
  type OrganisationUnit,
} from "../../lib/api-client/organisation-admin";
import { useAuth } from "../../lib/auth/auth-context";

type Props = { onClose: () => void; successor: OrganisationUnit };
type Assessed = { impact: MergeImpact; plan: MergePlan };

export function OrganisationMergePanel({ onClose, successor }: Props) {
  const { session } = useAuth();
  const queryClient = useQueryClient();
  const [sourceIds, setSourceIds] = useState<string[]>([]);
  const [grantId, setGrantId] = useState("");
  const [reason, setReason] = useState("");
  const [assessed, setAssessed] = useState<Assessed>();
  const [reviewed, setReviewed] = useState<MergePreview>();
  const [message, setMessage] = useState<string>();
  const csrf = session?.csrfToken ?? "";
  const siblings = useQuery({
    enabled: successor.parentId !== null,
    queryKey: ["organisation-units", "children", successor.parentId],
    queryFn: () => listOrganisationUnits(successor.parentId ?? undefined),
  });
  const grants = useQuery({
    queryKey: ["organisation-grants", "all-active"],
    queryFn: () => listManagementGrants(),
  });
  const authorities = useMemo(
    () =>
      (grants.data ?? []).filter(
        (grant) =>
          grant.managerUserId === session?.user.id &&
          grant.action === "organisation:restructure" &&
          !grant.revokedAt,
      ),
    [grants.data, session?.user.id],
  );
  const sources = (siblings.data ?? []).filter((unit) => sourceIds.includes(unit.id));
  const assess = useMutation({
    mutationFn: (request: MergeRequest) => assessMerge(request, csrf),
    onError: () => setMessage("The merge could not be assessed. Check authority and dependencies."),
    onSuccess: (impact, request) => {
      setAssessed({ impact, plan: buildPlan(request, impact, successor.id) });
      setMessage(undefined);
    },
  });
  const preview = useMutation({
    mutationFn: (plan: MergePlan) => previewMerge(plan, csrf),
    onError: () => setMessage("The merge plan changed or is not safe to apply."),
    onSuccess: setReviewed,
  });
  const execute = useMutation({
    mutationFn: (input: { hash: string; plan: MergePlan }) =>
      executeMerge(input.plan, input.hash, csrf),
    onError: () => setMessage("The merge could not be completed. Refresh and reassess it."),
    onSuccess: () => {
      setMessage("Units merged successfully.");
      void queryClient.invalidateQueries({ queryKey: ["organisation-units"] });
    },
  });
  const locked = assessed !== undefined;

  const requestAssessment = (event: FormEvent) => {
    event.preventDefault();
    assess.mutate({
      authorities: [...sources, successor].map((unit) => ({ grantId, unitId: unit.id })),
      reason: reason.trim(),
      sources: sources.map((unit) => ({ expectedVersion: unit.version, unitId: unit.id })),
      successor: { expectedVersion: successor.version, unitId: successor.id },
    });
  };

  return (
    <section className="organisation-restructure-panel" aria-labelledby="merge-title">
      <header>
        <div>
          <span className="eyebrow">Explicit-disposition merge</span>
          <h2 id="merge-title">Merge into {successor.shortName}</h2>
        </div>
        <button aria-label="Close merge" onClick={onClose} type="button">
          <X aria-hidden="true" size={18} />
        </button>
      </header>
      {successor.parentId === null ? (
        <p role="alert">The organisation root cannot be a merge successor.</p>
      ) : (
        <form onSubmit={requestAssessment}>
          <fieldset disabled={locked}>
            <legend>Source units</legend>
            {(siblings.data ?? [])
              .filter((unit) => unit.id !== successor.id && unit.isActive)
              .map((unit) => (
                <label key={unit.id}>
                  <input
                    checked={sourceIds.includes(unit.id)}
                    onChange={(event) =>
                      setSourceIds((current) =>
                        event.target.checked
                          ? [...current, unit.id]
                          : current.filter((id) => id !== unit.id),
                      )
                    }
                    type="checkbox"
                  />
                  {unit.shortName}
                </label>
              ))}
          </fieldset>
          <label>
            Authorising grant
            <select
              disabled={locked}
              onChange={(event) => setGrantId(event.target.value)}
              required
              value={grantId}
            >
              <option value="">Select restructure authority</option>
              {authorities.map((grant) => (
                <option key={grant.id} value={grant.id}>
                  {grant.includeDescendants ? "Descendant scope" : "Direct scope"}
                </option>
              ))}
            </select>
          </label>
          <label>
            Reason
            <textarea
              disabled={locked}
              maxLength={500}
              onChange={(event) => setReason(event.target.value)}
              required
              value={reason}
            />
          </label>
          <button
            disabled={
              sourceIds.length < 2 || !grantId || !reason.trim() || locked || assess.isPending
            }
            type="submit"
          >
            Assess dependencies
          </button>
        </form>
      )}
      {assessed ? (
        <MergeAssessment
          assessed={assessed}
          onReset={() => {
            setAssessed(undefined);
            setReviewed(undefined);
          }}
          onReview={() => preview.mutate(assessed.plan)}
          pending={preview.isPending}
        />
      ) : null}
      {reviewed && assessed ? (
        <div className="organisation-restructure-panel__confirm" role="status">
          <Check aria-hidden="true" size={18} />
          <div>
            <strong>Plan checked</strong>
            <p>The reviewed versions and every record disposition are now locked.</p>
          </div>
          <button
            disabled={execute.isPending}
            onClick={() => execute.mutate({ hash: reviewed.previewHash, plan: assessed.plan })}
            type="button"
          >
            Confirm merge
          </button>
        </div>
      ) : null}
      {message ? <p role="status">{message}</p> : null}
    </section>
  );
}

function MergeAssessment({
  assessed,
  onReset,
  onReview,
  pending,
}: {
  assessed: Assessed;
  onReset: () => void;
  onReview: () => void;
  pending: boolean;
}) {
  const counts = new Map<string, number>();
  for (const record of assessed.impact.records)
    counts.set(record.kind, (counts.get(record.kind) ?? 0) + 1);
  return (
    <div className="organisation-restructure-panel__assessment">
      <div>
        <GitMerge aria-hidden="true" size={18} />
        <strong>Dependencies assessed</strong>
      </div>
      <p>
        {assessed.impact.records.length} records require an explicit outcome. Children, memberships
        and tasks move to the successor; grants are revoked; pending transfers are cancelled;
        delivery profiles and capabilities end.
      </p>
      <ul>
        {[...counts].map(([kind, count]) => (
          <li key={kind}>
            <strong>{count}</strong> {kind.replaceAll("_", " ")}
          </li>
        ))}
      </ul>
      <div>
        <button onClick={onReset} type="button">
          Change selection
        </button>
        <button disabled={pending} onClick={onReview} type="button">
          Review merge plan
        </button>
      </div>
    </div>
  );
}

function buildPlan(request: MergeRequest, impact: MergeImpact, successorId: string): MergePlan {
  return {
    request,
    dispositions: impact.records.map((record) => {
      const action = dispositionAction(record.kind);
      return {
        action,
        expectedVersion: record.version,
        kind: record.kind,
        recordId: record.recordId,
        replacementId:
          record.kind === "membership" && action === "move" ? crypto.randomUUID() : null,
        targetUnitId: action === "move" ? successorId : null,
      };
    }),
  };
}

function dispositionAction(kind: MergeImpact["records"][number]["kind"]) {
  if (kind === "grant") return "revoke" as const;
  if (kind === "pending_transfer") return "cancel" as const;
  if (kind === "delivery_profile" || kind === "capability") return "end" as const;
  return "move" as const;
}
