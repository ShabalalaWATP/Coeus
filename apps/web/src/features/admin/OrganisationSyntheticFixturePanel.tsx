import { useMutation, useQueryClient } from "@tanstack/react-query";
import { DatabaseZap, ShieldAlert, X } from "lucide-react";
import type { FormEvent } from "react";
import { useState } from "react";

import {
  applySyntheticOrganisationFixture,
  previewSyntheticOrganisationFixture,
  reconcileSyntheticOrganisationFixture,
  type SyntheticFixturePreview,
} from "../../lib/api-client/organisation-admin";
import { useAuth } from "../../lib/auth/auth-context";

type FixturePanelProps = {
  onClose: () => void;
};

export function OrganisationSyntheticFixturePanel({ onClose }: FixturePanelProps) {
  const { session } = useAuth();
  const queryClient = useQueryClient();
  const [preview, setPreview] = useState<SyntheticFixturePreview>();
  const [currentPassword, setCurrentPassword] = useState("");
  const previewMutation = useMutation({
    mutationFn: () => previewSyntheticOrganisationFixture(session?.csrfToken ?? ""),
    onSuccess: setPreview,
  });
  const applyMutation = useMutation({
    mutationFn: (reconcile: boolean) =>
      (reconcile ? reconcileSyntheticOrganisationFixture : applySyntheticOrganisationFixture)(
        preview?.previewHash ?? "",
        currentPassword,
        session?.csrfToken ?? "",
      ),
    onSuccess: async () => {
      setCurrentPassword("");
      await queryClient.invalidateQueries({ queryKey: ["organisation-units"] });
      setPreview(await previewSyntheticOrganisationFixture(session?.csrfToken ?? ""));
    },
  });

  const canReconcile =
    preview?.findings.length !== 0 &&
    preview?.findings.every(
      (item) =>
        item.code === "fixture_row_changed" &&
        ["unit", "delivery_profile", "membership", "working_pattern"].includes(item.entityType),
    );

  const submit = (event: FormEvent) => {
    event.preventDefault();
    applyMutation.mutate(Boolean(canReconcile));
  };

  return (
    <section className="organisation-mutation" aria-labelledby="synthetic-fixture-title">
      <header>
        <div>
          <span className="eyebrow">Local exercise data</span>
          <h2 id="synthetic-fixture-title">Build the demonstration organisation</h2>
        </div>
        <button aria-label="Close exercise data" onClick={onClose} type="button">
          <X aria-hidden="true" size={18} />
        </button>
      </header>
      <p className="organisation-bootstrap__notice">
        <DatabaseZap aria-hidden="true" size={18} />
        Preview the exact fictional hierarchy, 53 single-home personnel postings and analyst working
        patterns. Local additions are preserved. Reviewed drift in exact fixture rows can be
        restored separately; unsafe changes are only reported.
      </p>

      {!preview ? (
        <button
          disabled={previewMutation.isPending}
          onClick={() => previewMutation.mutate()}
          type="button"
        >
          {previewMutation.isPending ? "Checking exercise data…" : "Check exercise data"}
        </button>
      ) : (
        <FixturePreview preview={preview} />
      )}

      {(preview?.canApply && preview.creates.total > 0) || canReconcile ? (
        <form onSubmit={submit}>
          <label className="organisation-mutation__wide">
            Current password
            <input
              autoComplete="current-password"
              onChange={(event) => setCurrentPassword(event.target.value)}
              required
              type="password"
              value={currentPassword}
            />
          </label>
          <button disabled={applyMutation.isPending} type="submit">
            {applyMutation.isPending
              ? canReconcile
                ? "Restoring exercise data…"
                : "Building organisation…"
              : canReconcile
                ? "Restore reviewed exercise data"
                : "Build exercise organisation"}
          </button>
        </form>
      ) : null}
      {previewMutation.isError ? <p role="alert">{previewMutation.error.message}</p> : null}
      {applyMutation.isError ? <p role="alert">{applyMutation.error.message}</p> : null}
    </section>
  );
}

function FixturePreview({ preview }: { preview: SyntheticFixturePreview }) {
  if (preview.findings.length > 0) {
    return (
      <div className="organisation-fixture__conflicts" role="status">
        <h3>
          <ShieldAlert aria-hidden="true" size={18} /> Review required
        </h3>
        <p>Unsafe conflicts are report-only. Exact mutable fixture drift may be restored.</p>
        <ul>
          {preview.findings.map((item) => (
            <li key={`${item.code}:${item.entityType}:${item.entityKey}`}>
              <strong>{item.entityKey}</strong>: {item.message}
            </li>
          ))}
        </ul>
      </div>
    );
  }
  if (preview.creates.total === 0) {
    return <p role="status">Exercise organisation is up to date.</p>;
  }
  return (
    <div className="organisation-fixture__summary" role="status">
      <h3>Ready to build</h3>
      <dl>
        <div>
          <dt>Units</dt>
          <dd>{preview.creates.units}</dd>
        </div>
        <div>
          <dt>Personnel postings</dt>
          <dd>{preview.creates.memberships}</dd>
        </div>
        <div>
          <dt>Working patterns</dt>
          <dd>{preview.creates.workingPatterns}</dd>
        </div>
        <div>
          <dt>Delivery teams</dt>
          <dd>{preview.creates.deliveryProfiles}</dd>
        </div>
        <div>
          <dt>Team capabilities</dt>
          <dd>{preview.creates.teamCapabilities}</dd>
        </div>
        <div>
          <dt>Analyst competencies</dt>
          <dd>{preview.creates.competencies}</dd>
        </div>
        <div>
          <dt>Calendar scenarios</dt>
          <dd>{preview.creates.calendarEvents}</dd>
        </div>
        <div>
          <dt>Operational tasks</dt>
          <dd>{preview.creates.tasks}</dd>
        </div>
        <div>
          <dt>Work packages</dt>
          <dd>{preview.creates.workPackages}</dd>
        </div>
        <div>
          <dt>Capacity reservations</dt>
          <dd>{preview.creates.capacityReservations}</dd>
        </div>
      </dl>
      <p>Your password is checked again immediately before the atomic change.</p>
    </div>
  );
}
