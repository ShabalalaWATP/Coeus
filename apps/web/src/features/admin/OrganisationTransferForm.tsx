import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Check, X } from "lucide-react";
import { useMemo, useState, type FormEvent } from "react";

import type { AdminUser } from "../../lib/api-client/admin";
import {
  executeTransfer,
  getOrganisationUnit,
  listUserMemberships,
  previewTransfer,
  type ManagementGrant,
  type TransferPreview,
  type TransferRequest,
  type OrganisationUnit,
} from "../../lib/api-client/organisation-admin";
import { useAuth } from "../../lib/auth/auth-context";

type Props = {
  grants: ManagementGrant[];
  onClose: () => void;
  target: OrganisationUnit;
  users: AdminUser[];
};

export function OrganisationTransferForm({ grants, onClose, target, users }: Props) {
  const { session } = useAuth();
  const queryClient = useQueryClient();
  const [userId, setUserId] = useState("");
  const [role, setRole] = useState<TransferRequest["targetRole"]>("member");
  const [eligible, setEligible] = useState(false);
  const [minimumBoundary] = useState(() => defaultBoundary());
  const [effectiveAt, setEffectiveAt] = useState(minimumBoundary);
  const [sourceGrantId, setSourceGrantId] = useState("");
  const [targetGrantId, setTargetGrantId] = useState("");
  const [reason, setReason] = useState("");
  const [review, setReview] = useState<{ preview: TransferPreview; request: TransferRequest }>();
  const [message, setMessage] = useState<string>();
  const history = useQuery({
    enabled: Boolean(userId),
    queryKey: ["organisation-memberships", "user", userId],
    queryFn: () => listUserMemberships(userId),
  });
  const source = useMemo(
    () => history.data?.find((item) => item.state === "active" && item.validUntil === null),
    [history.data],
  );
  const sourceUnit = useQuery({
    enabled: Boolean(source),
    queryKey: ["organisation-unit", source?.unitId],
    queryFn: () => getOrganisationUnit(source?.unitId ?? ""),
  });
  const previewMutation = useMutation({
    mutationFn: (request: TransferRequest) => previewTransfer(request, session?.csrfToken ?? ""),
    onError: () => setMessage("The transfer could not be reviewed. Check both scopes and retry."),
  });
  const executeMutation = useMutation({
    mutationFn: (input: { previewHash: string; request: TransferRequest }) =>
      executeTransfer(input.request, input.previewHash, session?.csrfToken ?? ""),
    onError: () => setMessage("The transfer could not be scheduled. Refresh and try again."),
    onSuccess: () => {
      setMessage("Transfer scheduled.");
      setReview(undefined);
      void queryClient.invalidateQueries({ queryKey: ["organisation-memberships"] });
    },
  });
  const locked = review !== undefined;
  const wrongTarget = source?.unitId === target.id;
  const canReview = Boolean(
    source && !wrongTarget && sourceGrantId && targetGrantId && reason.trim() && !locked,
  );

  const buildRequest = (): TransferRequest => ({
    sourceMembershipId: source?.membershipId ?? crypto.randomUUID(),
    targetMembershipId: crypto.randomUUID(),
    userId,
    sourceUnitId: source?.unitId ?? target.id,
    targetUnitId: target.id,
    expectedMembershipVersion: source?.version ?? 1,
    expectedTargetUnitVersion: target.version,
    targetRole: role,
    assignmentEligible: target.category === "delivery_team" && eligible,
    effectiveAt: new Date(effectiveAt).toISOString(),
    sourceAuthorisingGrantId: sourceGrantId,
    targetAuthorisingGrantId: targetGrantId,
    reason: reason.trim(),
  });
  const requestPreview = async (event: FormEvent) => {
    event.preventDefault();
    const request = buildRequest();
    const preview = await previewMutation.mutateAsync(request);
    setReview({ preview, request });
  };

  return (
    <section className="organisation-transfer-form" aria-labelledby="transfer-title">
      <header>
        <div>
          <span className="eyebrow">Exact-boundary transfer</span>
          <h3 id="transfer-title">Transfer into {target.shortName}</h3>
        </div>
        <button aria-label="Close transfer" onClick={onClose} type="button">
          <X aria-hidden="true" size={18} />
        </button>
      </header>
      <form onSubmit={(event) => void requestPreview(event)}>
        <label className="organisation-transfer-form__wide">
          Person
          <select
            disabled={locked}
            onChange={(event) => {
              setUserId(event.target.value);
              setReview(undefined);
            }}
            required
            value={userId}
          >
            <option value="">Select a person</option>
            {users
              .filter((user) => user.isActive)
              .map((user) => (
                <option key={user.id} value={user.id}>
                  {user.displayName}
                </option>
              ))}
          </select>
        </label>
        {userId && history.isLoading ? <p>Finding current home team…</p> : null}
        {userId && !history.isLoading && !source ? (
          <p role="alert">This person has no current home team. Use Add member instead.</p>
        ) : null}
        {wrongTarget ? <p role="alert">This person is already in {target.shortName}.</p> : null}
        {source && !wrongTarget ? (
          <div className="organisation-transfer-form__route">
            <strong>{sourceUnit.data?.shortName ?? "Current team"}</strong>
            <ArrowRight aria-hidden="true" size={18} />
            <strong>{target.shortName}</strong>
          </div>
        ) : null}
        <label>
          New team role
          <select
            disabled={locked}
            onChange={(event) => setRole(event.target.value as typeof role)}
            value={role}
          >
            <option value="member">Member</option>
            <option value="manager">Manager</option>
            <option value="deputy">Deputy</option>
            <option value="coordinator">Coordinator</option>
          </select>
        </label>
        <label>
          Effective at
          <input
            disabled={locked}
            min={minimumBoundary}
            onChange={(event) => setEffectiveAt(event.target.value)}
            required
            type="datetime-local"
            value={effectiveAt}
          />
        </label>
        <label className="organisation-transfer-form__check">
          <input
            checked={eligible}
            disabled={locked || target.category !== "delivery_team"}
            onChange={(event) => setEligible(event.target.checked)}
            type="checkbox"
          />
          Eligible for task assignment
        </label>
        <label>
          Source authority
          <select
            disabled={locked}
            onChange={(event) => setSourceGrantId(event.target.value)}
            required
            value={sourceGrantId}
          >
            <option value="">Select authority</option>
            {grants.map(grantOption)}
          </select>
        </label>
        <label>
          Target authority
          <select
            disabled={locked}
            onChange={(event) => setTargetGrantId(event.target.value)}
            required
            value={targetGrantId}
          >
            <option value="">Select authority</option>
            {grants.map(grantOption)}
          </select>
        </label>
        <label className="organisation-transfer-form__wide">
          Reason
          <textarea
            disabled={locked}
            maxLength={500}
            onChange={(event) => setReason(event.target.value)}
            required
            value={reason}
          />
        </label>
        <button disabled={!canReview || previewMutation.isPending} type="submit">
          Review transfer
        </button>
      </form>
      {review ? (
        <div className="organisation-transfer-form__review" role="status">
          <Check aria-hidden="true" size={18} />
          <div>
            <strong>Impact checked</strong>
            <p>{impactText(review.preview)}</p>
          </div>
          <button
            disabled={executeMutation.isPending}
            onClick={() =>
              executeMutation.mutate({
                request: review.request,
                previewHash: review.preview.previewHash,
              })
            }
            type="button"
          >
            Schedule transfer
          </button>
        </div>
      ) : null}
      {message ? <p role="status">{message}</p> : null}
    </section>
  );
}

function grantOption(grant: ManagementGrant) {
  return (
    <option key={grant.id} value={grant.id}>
      {grant.includeDescendants ? "Descendant scope" : "Direct scope"}
    </option>
  );
}

function impactText(preview: TransferPreview) {
  const impact = preview.impact;
  return `${impact.activeTaskLegs} task legs, ${impact.futureTeamEvents} future events and ${impact.namedWorkItems} named work items are linked.`;
}

function defaultBoundary() {
  const value = new Date(Date.now() + 5 * 60_000);
  return new Date(value.getTime() - value.getTimezoneOffset() * 60_000).toISOString().slice(0, 16);
}
