import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import type { TeamTaskCard, TeamTaskPackage } from "../../lib/api-client/team-task-board";
import {
  executeWorkPackagePlan,
  previewWorkPackagePlan,
  type WorkPackagePlan,
  type WorkPackagePlanningPreview,
} from "../../lib/api-client/work-package-planning";
import { useAuth } from "../../lib/auth/auth-context";

type Props = {
  card: TeamTaskCard;
  packageItem: TeamTaskPackage;
  planningGrantId: string;
  unitId: string;
  onClose: () => void;
};

function localInput(value: Date) {
  const local = new Date(value.getTime() - value.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 16);
}

function defaults(packageItem: TeamTaskPackage) {
  const start = new Date();
  start.setDate(start.getDate() + 1);
  start.setHours(9, 0, 0, 0);
  const end = new Date(start.getTime() + 4 * 60 * 60_000);
  const due = packageItem.dueAt ? new Date(packageItem.dueAt) : new Date(end);
  if (!packageItem.dueAt) due.setDate(due.getDate() + 1);
  return { start: localInput(start), end: localInput(end), due: localInput(due) };
}

export function WorkPackagePlanningForm({
  card,
  packageItem,
  planningGrantId,
  unitId,
  onClose,
}: Props) {
  const { session } = useAuth();
  const queryClient = useQueryClient();
  const initial = useMemo(() => defaults(packageItem), [packageItem]);
  const [estimatedHours, setEstimatedHours] = useState(
    String((packageItem.estimatedMinutes ?? 240) / 60),
  );
  const [remainingHours, setRemainingHours] = useState(
    String((packageItem.remainingMinutes ?? packageItem.estimatedMinutes ?? 240) / 60),
  );
  const [reservedHours, setReservedHours] = useState("1");
  const [startsAt, setStartsAt] = useState(initial.start);
  const [endsAt, setEndsAt] = useState(initial.end);
  const [dueAt, setDueAt] = useState(initial.due);
  const [priority, setPriority] = useState(String(packageItem.priority ?? 3));
  const [reason, setReason] = useState("");
  const [preview, setPreview] = useState<WorkPackagePlanningPreview | null>(null);
  const [reviewedRequest, setReviewedRequest] = useState<WorkPackagePlan | null>(null);

  const previewMutation = useMutation({
    mutationFn: (request: WorkPackagePlan) =>
      previewWorkPackagePlan(unitId, packageItem.packageId, request, session?.csrfToken ?? ""),
    onSuccess: (value, request) => {
      setPreview(value);
      setReviewedRequest(request);
    },
  });
  const executeMutation = useMutation({
    mutationFn: () =>
      executeWorkPackagePlan(
        unitId,
        packageItem.packageId,
        reviewedRequest!,
        preview!.previewHash,
        session?.csrfToken ?? "",
      ),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["team-task-board", unitId] });
      onClose();
    },
  });

  function request(): WorkPackagePlan {
    return {
      expectedPackageVersion: packageItem.version,
      expectedOwnershipVersion: card.ownershipVersion,
      accountableUserId: packageItem.accountableUserId!,
      estimatedMinutes: Math.round(Number(estimatedHours) * 60),
      remainingMinutes: Math.round(Number(remainingHours) * 60),
      dueAt: new Date(dueAt).toISOString(),
      priority: Number(priority),
      priorityOverrideReason: reason.trim(),
      reservationId: crypto.randomUUID(),
      startsAt: new Date(startsAt).toISOString(),
      endsAt: new Date(endsAt).toISOString(),
      reservedMinutes: Math.round(Number(reservedHours) * 60),
      authorisingGrantId: planningGrantId,
    };
  }

  const error = previewMutation.error ?? executeMutation.error;
  return (
    <form
      className="work-package-plan"
      onSubmit={(event) => {
        event.preventDefault();
        setPreview(null);
        setReviewedRequest(null);
        previewMutation.mutate(request());
      }}
    >
      <header>
        <div>
          <small>{card.reference}</small>
          <h6>Plan {packageItem.title}</h6>
        </div>
        <button onClick={onClose} type="button">
          Close
        </button>
      </header>
      <div className="work-package-plan__grid">
        <NumberField label="Estimated hours" value={estimatedHours} onChange={setEstimatedHours} />
        <NumberField label="Remaining hours" value={remainingHours} onChange={setRemainingHours} />
        <NumberField
          label="Reserve now (hours)"
          value={reservedHours}
          onChange={setReservedHours}
        />
        <label>
          Priority
          <select value={priority} onChange={(event) => setPriority(event.target.value)}>
            {[1, 2, 3, 4, 5].map((value) => (
              <option key={value}>{value}</option>
            ))}
          </select>
        </label>
        <DateField label="Work starts" value={startsAt} onChange={setStartsAt} />
        <DateField label="Work ends" value={endsAt} onChange={setEndsAt} />
        <DateField label="Due by" value={dueAt} onChange={setDueAt} />
        <label>
          Priority reason
          <input
            maxLength={500}
            onChange={(event) => setReason(event.target.value)}
            value={reason}
          />
        </label>
      </div>
      {error ? (
        <p role="alert">The plan could not be saved. Refresh the board and try again.</p>
      ) : null}
      {preview && reviewedRequest ? (
        <div className="work-package-plan__review">
          <p>
            Review: reserve {reviewedRequest.reservedMinutes / 60} hours before{" "}
            {new Date(reviewedRequest.dueAt).toLocaleString("en-GB")}.
          </p>
          <button
            disabled={executeMutation.isPending}
            onClick={() => executeMutation.mutate()}
            type="button"
          >
            {executeMutation.isPending ? "Saving plan…" : "Confirm plan and reserve capacity"}
          </button>
        </div>
      ) : (
        <button disabled={!session || previewMutation.isPending} type="submit">
          {previewMutation.isPending ? "Checking capacity…" : "Review plan"}
        </button>
      )}
    </form>
  );
}

function NumberField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label>
      {label}
      <input
        min="0.25"
        onChange={(event) => onChange(event.target.value)}
        required
        step="0.25"
        type="number"
        value={value}
      />
    </label>
  );
}

function DateField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label>
      {label}
      <input
        onChange={(event) => onChange(event.target.value)}
        required
        type="datetime-local"
        value={value}
      />
    </label>
  );
}
