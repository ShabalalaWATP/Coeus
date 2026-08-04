import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Plus, X } from "lucide-react";
import { useMemo, useState, type FormEvent } from "react";

import {
  assessSplit,
  executeSplit,
  getOrganisationUnit,
  listManagementGrants,
  previewSplit,
  type OrganisationUnit,
  type SplitImpact,
  type SplitPlan,
  type SplitPreview,
  type SplitRequest,
} from "../../lib/api-client/organisation-admin";
import { useAuth } from "../../lib/auth/auth-context";
import { OrganisationGrantSelect, SplitAssessment } from "./organisation-split-helpers";
import {
  buildSplitPlan,
  blankSuccessor,
  updateSuccessor,
  type SplitMoveKind,
  type SplitSuccessor,
} from "./organisation-split-plan";

type Props = { onClose: () => void; source: OrganisationUnit };

export function OrganisationSplitPanel({ onClose, source }: Props) {
  const { session } = useAuth();
  const queryClient = useQueryClient();
  const [successors, setSuccessors] = useState<SplitSuccessor[]>(() => [
    blankSuccessor(source),
    blankSuccessor(source),
  ]);
  const [sourceGrantId, setSourceGrantId] = useState("");
  const [parentGrantId, setParentGrantId] = useState("");
  const [reason, setReason] = useState("");
  const [assessed, setAssessed] = useState<{ impact: SplitImpact; request: SplitRequest }>();
  const [targets, setTargets] = useState<Partial<Record<SplitMoveKind, string>>>({});
  const [reviewed, setReviewed] = useState<{ plan: SplitPlan; preview: SplitPreview }>();
  const [message, setMessage] = useState<string>();
  const csrf = session?.csrfToken ?? "";
  const parent = useQuery({
    enabled: source.parentId !== null,
    queryKey: ["organisation-unit", source.parentId],
    queryFn: () => getOrganisationUnit(source.parentId ?? ""),
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
  const assess = useMutation({
    mutationFn: (request: SplitRequest) => assessSplit(request, csrf),
    onError: () => setMessage("The split could not be assessed. Check authority and dependencies."),
    onSuccess: (impact, request) => {
      setAssessed({ impact, request });
      const first = request.successors[0].unitId;
      setTargets({ child_unit: first, membership: first, task: first });
      setMessage(undefined);
    },
  });
  const preview = useMutation({
    mutationFn: (plan: SplitPlan) => previewSplit(plan, csrf),
    onError: () => setMessage("The split plan changed or is not safe to apply."),
    onSuccess: (result, plan) => setReviewed({ plan, preview: result }),
  });
  const execute = useMutation({
    mutationFn: (value: { plan: SplitPlan; previewHash: string }) =>
      executeSplit(value.plan, value.previewHash, csrf),
    onError: () => setMessage("The split could not be completed. Refresh and reassess it."),
    onSuccess: () => {
      setMessage("Unit split successfully.");
      void queryClient.invalidateQueries({ queryKey: ["organisation-units"] });
    },
  });
  const locked = assessed !== undefined;
  const validSuccessors = successors.every((item) => item.name.trim() && item.shortName.trim());

  const requestAssessment = (event: FormEvent) => {
    event.preventDefault();
    if (!parent.data) return;
    assess.mutate({
      parent: { expectedVersion: parent.data.version, unitId: parent.data.id },
      parentAuthorisingGrantId: parentGrantId,
      reason: reason.trim(),
      source: { expectedVersion: source.version, unitId: source.id },
      sourceAuthorisingGrantId: sourceGrantId,
      successors,
    });
  };
  const requestPreview = () => {
    if (!assessed) return;
    preview.mutate(buildSplitPlan(assessed.request, assessed.impact, targets));
  };

  return (
    <section className="organisation-restructure-panel" aria-labelledby="split-title">
      <header>
        <div>
          <span className="eyebrow">Explicit-disposition split</span>
          <h2 id="split-title">Split {source.shortName}</h2>
        </div>
        <button aria-label="Close split" onClick={onClose} type="button">
          <X aria-hidden="true" size={18} />
        </button>
      </header>
      {source.parentId === null ? (
        <p role="alert">The organisation root cannot be split.</p>
      ) : (
        <form onSubmit={requestAssessment}>
          <fieldset disabled={locked}>
            <legend>Successor units</legend>
            {successors.map((item, index) => (
              <div className="organisation-restructure-panel__successor" key={item.unitId}>
                <label>
                  Name
                  <input
                    maxLength={120}
                    onChange={(event) =>
                      updateSuccessor(successors, setSuccessors, index, "name", event.target.value)
                    }
                    required
                    value={item.name}
                  />
                </label>
                <label>
                  Short name
                  <input
                    maxLength={32}
                    onChange={(event) =>
                      updateSuccessor(
                        successors,
                        setSuccessors,
                        index,
                        "shortName",
                        event.target.value,
                      )
                    }
                    required
                    value={item.shortName}
                  />
                </label>
                {successors.length > 2 ? (
                  <button
                    onClick={() =>
                      setSuccessors((current) =>
                        current.filter((_, itemIndex) => itemIndex !== index),
                      )
                    }
                    type="button"
                  >
                    Remove
                  </button>
                ) : null}
              </div>
            ))}
          </fieldset>
          <button
            disabled={locked || successors.length >= 10}
            onClick={() => setSuccessors((current) => [...current, blankSuccessor(source)])}
            type="button"
          >
            <Plus aria-hidden="true" size={16} /> Add successor
          </button>
          <label>
            Source authority
            <OrganisationGrantSelect
              disabled={locked}
              grants={authorities}
              onChange={setSourceGrantId}
              value={sourceGrantId}
            />
          </label>
          <label>
            Parent authority
            <OrganisationGrantSelect
              disabled={locked}
              grants={authorities}
              onChange={setParentGrantId}
              value={parentGrantId}
            />
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
              !validSuccessors ||
              !sourceGrantId ||
              !parentGrantId ||
              !reason.trim() ||
              locked ||
              assess.isPending ||
              !parent.data
            }
            type="submit"
          >
            Assess dependencies
          </button>
        </form>
      )}
      {assessed ? (
        <SplitAssessment
          assessed={assessed}
          onReset={() => {
            setAssessed(undefined);
            setReviewed(undefined);
          }}
          onReview={requestPreview}
          pending={preview.isPending}
          setTargets={setTargets}
          targets={targets}
        />
      ) : null}
      {reviewed ? (
        <div className="organisation-restructure-panel__confirm" role="status">
          <Check aria-hidden="true" size={18} />
          <div>
            <strong>Plan checked</strong>
            <p>The successor definitions and every record disposition are locked.</p>
          </div>
          <button
            disabled={execute.isPending}
            onClick={() =>
              execute.mutate({ plan: reviewed.plan, previewHash: reviewed.preview.previewHash })
            }
            type="button"
          >
            Confirm split
          </button>
        </div>
      ) : null}
      {message ? <p role="status">{message}</p> : null}
    </section>
  );
}
