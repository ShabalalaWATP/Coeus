import { GitFork } from "lucide-react";

import type { SplitImpact, SplitRequest } from "../../lib/api-client/organisation-admin";
import type { SplitMoveKind } from "./organisation-split-plan";

export function SplitAssessment({
  assessed,
  onReset,
  onReview,
  pending,
  setTargets,
  targets,
}: {
  assessed: { impact: SplitImpact; request: SplitRequest };
  onReset: () => void;
  onReview: () => void;
  pending: boolean;
  setTargets: (value: Partial<Record<SplitMoveKind, string>>) => void;
  targets: Partial<Record<SplitMoveKind, string>>;
}) {
  const movable = (["child_unit", "membership", "task"] as const).filter((kind) =>
    assessed.impact.records.some((record) => record.kind === kind),
  );
  return (
    <div className="organisation-restructure-panel__assessment">
      <div>
        <GitFork aria-hidden="true" size={18} />
        <strong>Dependencies assessed</strong>
      </div>
      <p>
        Choose the successor for each movable record group. Grants are revoked, pending transfers
        are cancelled, and delivery profiles and capabilities end.
      </p>
      {movable.map((kind) => (
        <label key={kind}>
          {kind.replaceAll("_", " ")} destination
          <select
            onChange={(event) => setTargets({ ...targets, [kind]: event.target.value })}
            value={targets[kind]}
          >
            {assessed.request.successors.map((item) => (
              <option key={item.unitId} value={item.unitId}>
                {item.shortName}
              </option>
            ))}
          </select>
        </label>
      ))}
      <div>
        <button onClick={onReset} type="button">
          Change definition
        </button>
        <button disabled={pending} onClick={onReview} type="button">
          Review split plan
        </button>
      </div>
    </div>
  );
}

export function OrganisationGrantSelect({
  disabled,
  grants,
  onChange,
  value,
}: {
  disabled: boolean;
  grants: { id: string; includeDescendants: boolean }[];
  onChange: (value: string) => void;
  value: string;
}) {
  return (
    <select
      disabled={disabled}
      onChange={(event) => onChange(event.target.value)}
      required
      value={value}
    >
      <option value="">Select restructure authority</option>
      {grants.map((grant) => (
        <option key={grant.id} value={grant.id}>
          {grant.includeDescendants ? "Descendant scope" : "Direct scope"}
        </option>
      ))}
    </select>
  );
}
