import { useMutation } from "@tanstack/react-query";
import { Sparkles } from "lucide-react";
import { useState } from "react";

import type { AnalystTask } from "../../lib/api-client/analyst";
import {
  acceptAssignmentRecommendation,
  previewAssignmentRecommendation,
  type AssignmentRecommendation,
} from "../../lib/api-client/assignment-recommendations";
import { ApiError } from "../../lib/api-client/client";

type Props = {
  csrfToken: string;
  onAssigned: (task: AnalystTask) => void;
  teamId: string;
  ticketId: string;
};

export function AssignmentRecommendationPanel({ csrfToken, onAssigned, teamId, ticketId }: Props) {
  const [minimumMinutes, setMinimumMinutes] = useState(120);
  const [maximumMinutes, setMaximumMinutes] = useState(240);
  const [deadline, setDeadline] = useState(defaultDeadline());
  const [capabilities, setCapabilities] = useState("");
  const [preview, setPreview] = useState<AssignmentRecommendation | null>(null);
  const [selectedId, setSelectedId] = useState("");
  const [overrideReason, setOverrideReason] = useState("");
  const previewMutation = useMutation({
    mutationFn: () =>
      previewAssignmentRecommendation(
        ticketId,
        {
          effortMinMinutes: minimumMinutes,
          effortMaxMinutes: maximumMinutes,
          deadline: new Date(deadline).toISOString(),
          capabilityIds: capabilityList(capabilities),
          unitId: teamId || null,
        },
        csrfToken,
      ),
    onSuccess: (result) => {
      setPreview(result);
      setSelectedId(result.candidates[0]?.analystUserId ?? "");
      setOverrideReason("");
    },
  });
  const selected = preview?.candidates.find((candidate) => candidate.analystUserId === selectedId);
  const acceptMutation = useMutation({
    mutationFn: () => {
      if (!preview || !selected) throw new Error("Select a recommendation candidate.");
      return acceptAssignmentRecommendation(
        ticketId,
        preview,
        selected.unitId,
        selected.analystUserId,
        selected.rank === 1 ? "" : overrideReason,
        csrfToken,
      );
    },
    onSuccess: (task) => onAssigned(task),
  });

  return (
    <details className="workspace-details routing-assign__recommendation">
      <summary>
        <Sparkles aria-hidden="true" size={17} /> Get capacity-aware advice
      </summary>
      <p>
        Istari checks current skills, workload and capacity. This is advice only: a manager makes
        the named assignment.
      </p>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          previewMutation.mutate();
        }}
      >
        <div className="form-grid form-grid--two">
          <label>
            Minimum effort (minutes)
            <input
              min={15}
              onChange={(event) => setMinimumMinutes(event.currentTarget.valueAsNumber)}
              step={15}
              type="number"
              value={minimumMinutes}
            />
          </label>
          <label>
            Maximum effort (minutes)
            <input
              min={15}
              onChange={(event) => setMaximumMinutes(event.currentTarget.valueAsNumber)}
              step={15}
              type="number"
              value={maximumMinutes}
            />
          </label>
        </div>
        <label>
          Needed by
          <input
            onChange={(event) => setDeadline(event.currentTarget.value)}
            required
            type="datetime-local"
            value={deadline}
          />
        </label>
        <label>
          Required capability codes
          <input
            onChange={(event) => setCapabilities(event.currentTarget.value)}
            placeholder="For example, RFA-REGIONAL-ANALYSIS"
            required
            value={capabilities}
          />
        </label>
        <button
          disabled={
            previewMutation.isPending ||
            capabilityList(capabilities).length === 0 ||
            maximumMinutes < minimumMinutes
          }
          type="submit"
        >
          Review recommendation
        </button>
      </form>
      {previewMutation.isError ? <p role="alert">{previewError(previewMutation.error)}</p> : null}
      {preview ? (
        <section aria-label="Assignment recommendation">
          <p>
            Estimate version {preview.estimateVersion}. Held for review until{" "}
            {formatTime(preview.expiresAt)}.
          </p>
          <fieldset>
            <legend>Eligible analysts</legend>
            {preview.candidates.map((candidate) => (
              <label key={candidate.analystUserId}>
                <input
                  checked={selectedId === candidate.analystUserId}
                  name="recommended-analyst"
                  onChange={() => {
                    setSelectedId(candidate.analystUserId);
                    setOverrideReason("");
                  }}
                  type="radio"
                />
                {candidate.displayName} {candidate.rank === 1 ? "(recommended)" : ""},{" "}
                {candidate.activeWip} active work items
              </label>
            ))}
          </fieldset>
          {selected && selected.rank !== 1 ? (
            <label>
              Reason for choosing another eligible analyst
              <textarea
                minLength={10}
                onChange={(event) => setOverrideReason(event.currentTarget.value)}
                required
                value={overrideReason}
              />
            </label>
          ) : null}
          <button
            disabled={
              acceptMutation.isPending ||
              !selected ||
              (selected.rank !== 1 && overrideReason.trim().length < 10)
            }
            onClick={() => acceptMutation.mutate()}
            type="button"
          >
            Accept and assign
          </button>
          {acceptMutation.isError ? (
            <p role="alert">The recommendation changed. Review a new recommendation.</p>
          ) : null}
        </section>
      ) : null}
    </details>
  );
}

function capabilityList(raw: string) {
  return [
    ...new Set(
      raw
        .split(/[,;\n]/)
        .map((value) => value.trim())
        .filter(Boolean),
    ),
  ];
}

function defaultDeadline() {
  const value = new Date(Date.now() + 7 * 24 * 60 * 60 * 1000);
  value.setSeconds(0, 0);
  return new Date(value.getTime() - value.getTimezoneOffset() * 60_000).toISOString().slice(0, 16);
}

function formatTime(raw: string) {
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(
    new Date(raw),
  );
}

function previewError(error: Error | null) {
  if (error instanceof ApiError && error.code === "assignment_recommendation_unavailable") {
    return "No safe recommendation is available for this demand. Adjust the demand or assign manually.";
  }
  return "The recommendation could not be prepared. Try again.";
}
