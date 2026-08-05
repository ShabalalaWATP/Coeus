import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { UserPlus, UsersRound } from "lucide-react";
import { useMemo, useState } from "react";

import { OrganisationMembershipForm } from "./OrganisationMembershipForm";
import { OrganisationTransferForm } from "./OrganisationTransferForm";
import { listAdminUsers } from "../../lib/api-client/admin";
import {
  executeMembership,
  listManagementGrants,
  listUnitMemberships,
  previewMembership,
  type MembershipPreview,
  type MembershipRecord,
  type MembershipRequest,
  type OrganisationUnit,
} from "../../lib/api-client/organisation-admin";
import { useAuth } from "../../lib/auth/auth-context";

type Props = { onClose: () => void; unit: OrganisationUnit };
type Change = { membership?: MembershipRecord; mode: "create" | "end" | "transfer" | "update" };

export function OrganisationRosterPanel({ onClose, unit }: Props) {
  const { session } = useAuth();
  const queryClient = useQueryClient();
  const [change, setChange] = useState<Change>();
  const [message, setMessage] = useState<string>();
  const memberships = useQuery({
    queryKey: ["organisation-memberships", unit.id],
    queryFn: () => listUnitMemberships(unit.id),
  });
  const users = useQuery({ queryKey: ["admin-users"], queryFn: listAdminUsers });
  const grants = useQuery({
    queryKey: ["organisation-grants", "all-active"],
    queryFn: () => listManagementGrants(),
  });
  const rosterGrants = useMemo(
    () =>
      (grants.data ?? []).filter(
        (grant) =>
          grant.managerUserId === session?.user.id &&
          grant.action === "roster:manage" &&
          !grant.revokedAt,
      ),
    [grants.data, session?.user.id],
  );
  const transferGrants = useMemo(
    () =>
      (grants.data ?? []).filter(
        (grant) =>
          grant.managerUserId === session?.user.id &&
          grant.action === "roster:transfer" &&
          !grant.revokedAt,
      ),
    [grants.data, session?.user.id],
  );
  const previewMutation = useMutation({
    mutationFn: (request: MembershipRequest) =>
      previewMembership(request, session?.csrfToken ?? ""),
    onError: () => setMessage("The roster change could not be completed. Refresh and try again."),
  });
  const executeMutation = useMutation({
    mutationFn: (input: { previewHash: string; request: MembershipRequest }) =>
      executeMembership(input.request, input.previewHash, session?.csrfToken ?? ""),
    onError: () => setMessage("The roster change could not be completed. Refresh and try again."),
  });
  const preview = (request: MembershipRequest): Promise<MembershipPreview> => {
    setMessage(undefined);
    return previewMutation.mutateAsync(request);
  };
  const confirm = (request: MembershipRequest, previewHash: string) => {
    executeMutation.mutate(
      { previewHash, request },
      {
        onSuccess: () => {
          setChange(undefined);
          setMessage("Roster updated.");
          void queryClient.invalidateQueries({ queryKey: ["organisation-memberships", unit.id] });
        },
      },
    );
  };
  const pending = previewMutation.isPending || executeMutation.isPending;

  return (
    <div className="organisation-roster-panel">
      <header>
        <div>
          <span className="eyebrow">Single home team</span>
          <h2>{unit.shortName} roster</h2>
          <p>Each person has one effective home team. Changes are previewed and audited.</p>
        </div>
        <button onClick={onClose} type="button">
          Close
        </button>
      </header>
      {change?.mode === "transfer" ? (
        <OrganisationTransferForm
          grants={transferGrants}
          onClose={() => setChange(undefined)}
          target={unit}
          users={users.data ?? []}
        />
      ) : change ? (
        <OrganisationMembershipForm
          grants={rosterGrants}
          membership={change.membership}
          mode={change.mode}
          onClose={() => setChange(undefined)}
          onConfirm={confirm}
          onPreview={preview}
          pending={pending}
          unit={unit}
          users={users.data ?? []}
        />
      ) : (
        <>
          <div className="organisation-roster-panel__toolbar">
            <div>
              <UsersRound aria-hidden="true" size={18} />
              <strong>Current members</strong>
            </div>
            <button onClick={() => setChange({ mode: "create" })} type="button">
              <UserPlus aria-hidden="true" size={17} /> Add member
            </button>
            <button onClick={() => setChange({ mode: "transfer" })} type="button">
              Transfer member
            </button>
          </div>
          {memberships.isLoading || users.isLoading ? <p>Loading roster…</p> : null}
          {memberships.isError || users.isError ? (
            <p role="alert">The roster could not be loaded.</p>
          ) : null}
          <RosterList
            memberships={memberships.data ?? []}
            onChange={setChange}
            users={users.data ?? []}
          />
        </>
      )}
      {rosterGrants.length === 0 && change?.mode !== "transfer" ? (
        <p role="alert">No roster management grant is available.</p>
      ) : null}
      {message ? <p role="status">{message}</p> : null}
    </div>
  );
}

function RosterList({
  memberships,
  onChange,
  users,
}: {
  memberships: MembershipRecord[];
  onChange: (change: Change) => void;
  users: { displayName: string; id: string }[];
}) {
  const names = new Map(users.map((user) => [user.id, user.displayName]));
  if (memberships.length === 0) return <p>No current members.</p>;
  return (
    <ul className="organisation-roster-panel__list">
      {memberships.map((membership) => (
        <li key={membership.membershipId}>
          <span>
            <strong>{names.get(membership.userId) ?? "Unknown user"}</strong>
            {membership.role}
          </span>
          <small>
            {membership.assignmentEligible ? "Assignment eligible" : "Not assignment eligible"}
          </small>
          <button onClick={() => onChange({ membership, mode: "update" })} type="button">
            Edit
          </button>
          <button
            className="organisation-roster-panel__remove"
            onClick={() => onChange({ membership, mode: "end" })}
            type="button"
          >
            Remove
          </button>
        </li>
      ))}
    </ul>
  );
}
