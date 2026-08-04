import { Check, X } from "lucide-react";
import { useState, type FormEvent } from "react";

import type { AdminUser } from "../../lib/api-client/admin";
import type {
  ManagementGrant,
  MembershipPreview,
  MembershipRecord,
  MembershipRequest,
  OrganisationUnit,
} from "../../lib/api-client/organisation-admin";

type Mode = "create" | "end" | "update";
type Props = {
  grants: ManagementGrant[];
  membership?: MembershipRecord;
  mode: Mode;
  onClose: () => void;
  onConfirm: (request: MembershipRequest, previewHash: string) => void;
  onPreview: (request: MembershipRequest) => Promise<MembershipPreview>;
  pending: boolean;
  unit: OrganisationUnit;
  users: AdminUser[];
};

export function OrganisationMembershipForm(props: Props) {
  const { membership, mode, unit } = props;
  const [membershipId] = useState(() => membership?.membershipId ?? crypto.randomUUID());
  const [userId, setUserId] = useState(membership?.userId ?? "");
  const [role, setRole] = useState(membership?.role ?? "member");
  const [eligible, setEligible] = useState(membership?.assignmentEligible ?? false);
  const [grantId, setGrantId] = useState("");
  const [reason, setReason] = useState("");
  const [review, setReview] = useState<{
    preview: MembershipPreview;
    request: MembershipRequest;
  }>();
  const locked = review !== undefined;
  const candidates = props.users.filter((user) => user.isActive);

  const buildRequest = (): MembershipRequest => ({
    operation: mode,
    membershipId,
    userId,
    unitId: unit.id,
    expectedVersion: membership?.version ?? 0,
    role,
    assignmentEligible: mode === "end" ? false : eligible,
    validFrom: membership?.validFrom ?? new Date().toISOString(),
    validUntil: mode === "end" ? new Date().toISOString() : null,
    authorisingGrantId: grantId,
    reason: reason.trim(),
  });

  const preview = async (event: FormEvent) => {
    event.preventDefault();
    const request = buildRequest();
    const result = await props.onPreview(request);
    setReview({ preview: result, request });
  };

  return (
    <section className="organisation-membership-form" aria-labelledby="membership-form-title">
      <header>
        <div>
          <span className="eyebrow">Preview required</span>
          <h3 id="membership-form-title">{title(mode, membership, props.users)}</h3>
        </div>
        <button aria-label="Close roster change" onClick={props.onClose} type="button">
          <X aria-hidden="true" size={18} />
        </button>
      </header>
      <form onSubmit={(event) => void preview(event)}>
        <label>
          Person
          <select
            disabled={mode !== "create" || locked}
            onChange={(event) => setUserId(event.target.value)}
            required
            value={userId}
          >
            <option value="">Select a user</option>
            {candidates.map((user) => (
              <option key={user.id} value={user.id}>
                {user.displayName}
              </option>
            ))}
          </select>
        </label>
        <label>
          Team role
          <select
            disabled={mode === "end" || locked}
            onChange={(event) => setRole(event.target.value as typeof role)}
            value={role}
          >
            <option value="member">Member</option>
            <option value="manager">Manager</option>
            <option value="deputy">Deputy</option>
            <option value="coordinator">Coordinator</option>
          </select>
        </label>
        <label className="organisation-membership-form__check">
          <input
            checked={mode !== "end" && eligible}
            disabled={mode === "end" || unit.category !== "delivery_team" || locked}
            onChange={(event) => setEligible(event.target.checked)}
            type="checkbox"
          />
          Eligible for task assignment
        </label>
        <label>
          Authorising grant
          <select
            disabled={locked}
            onChange={(event) => setGrantId(event.target.value)}
            required
            value={grantId}
          >
            <option value="">Select roster authority</option>
            {props.grants.map((grant) => (
              <option key={grant.id} value={grant.id}>
                {grant.includeDescendants ? "Descendant scope" : "Direct scope"}
              </option>
            ))}
          </select>
        </label>
        <label className="organisation-membership-form__wide">
          Reason
          <textarea
            disabled={locked}
            maxLength={500}
            onChange={(event) => setReason(event.target.value)}
            required
            value={reason}
          />
        </label>
        <button disabled={props.pending || locked} type="submit">
          Review impact
        </button>
      </form>
      {review ? (
        <div className="organisation-membership-form__review" role="status">
          <Check aria-hidden="true" size={18} />
          <div>
            <strong>Impact checked</strong>
            <p>{review.preview.snapshot.activeTaskLegs} active task legs are linked.</p>
          </div>
          <button
            disabled={props.pending}
            onClick={() => props.onConfirm(review.request, review.preview.previewHash)}
            type="button"
          >
            Confirm {mode === "end" ? "removal" : "membership"}
          </button>
        </div>
      ) : null}
    </section>
  );
}

function title(mode: Mode, membership: MembershipRecord | undefined, users: AdminUser[]) {
  if (mode === "create") return "Add a team member";
  const person = users.find((user) => user.id === membership?.userId)?.displayName ?? "member";
  return mode === "end" ? `Remove ${person}` : `Update ${person}`;
}
