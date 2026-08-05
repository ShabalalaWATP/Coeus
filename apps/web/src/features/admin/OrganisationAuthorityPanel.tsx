import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { KeyRound, UserRoundCog } from "lucide-react";
import { useMemo, useState } from "react";

import { listAdminUsers } from "../../lib/api-client/admin";
import {
  createManagementGrant,
  listManagementGrants,
  revokeManagementGrant,
  type ManagementAction,
  type ManagementGrant,
  type OrganisationUnit,
} from "../../lib/api-client/organisation-admin";
import { useAuth } from "../../lib/auth/auth-context";

type Props = { onClose: () => void; unit: OrganisationUnit };

export function OrganisationAuthorityPanel({ onClose, unit }: Props) {
  const { session } = useAuth();
  const queryClient = useQueryClient();
  const [managerId, setManagerId] = useState("");
  const [sourceId, setSourceId] = useState("");
  const [reason, setReason] = useState("");
  const [validUntil, setValidUntil] = useState("");
  const [includeDescendants, setIncludeDescendants] = useState(false);
  const [revoking, setRevoking] = useState<ManagementGrant>();
  const [message, setMessage] = useState<string>();
  const csrf = session?.csrfToken ?? "";
  const grants = useQuery({
    queryKey: ["organisation-grants", "all-active"],
    queryFn: () => listManagementGrants(),
  });
  const users = useQuery({ queryKey: ["admin-users"], queryFn: listAdminUsers });
  const activeSources = useMemo(
    () =>
      (grants.data ?? []).filter(
        (grant) =>
          grant.managerUserId === session?.user.id &&
          !grant.revokedAt &&
          (!grant.validUntil || new Date(grant.validUntil) > new Date()),
      ),
    [grants.data, session?.user.id],
  );
  const unitGrants = useMemo(
    () => (grants.data ?? []).filter((grant) => grant.rootUnitId === unit.id),
    [grants.data, unit.id],
  );
  const source = activeSources.find((grant) => grant.id === sourceId);
  const refresh = async () => {
    await queryClient.invalidateQueries({ queryKey: ["organisation-grants"] });
  };
  const createGrant = useMutation({
    mutationFn: () => {
      if (!source) throw new Error("Select an authorising grant.");
      return createManagementGrant(
        {
          action: source.action,
          expectedSourceVersion: source.version,
          includeDescendants,
          managerUserId: managerId,
          reason: reason.trim(),
          rootUnitId: unit.id,
          sourceGrantId: source.id,
          validUntil: validUntil ? new Date(validUntil).toISOString() : null,
        },
        csrf,
      );
    },
    onError: () => setMessage("The grant could not be created. Check its scope and try again."),
    onSuccess: async () => {
      setManagerId("");
      setSourceId("");
      setReason("");
      setValidUntil("");
      setIncludeDescendants(false);
      setMessage("Management authority granted.");
      await refresh();
    },
  });
  const revokeGrant = useMutation({
    mutationFn: (grant: ManagementGrant) => revokeManagementGrant(grant, reason.trim(), csrf),
    onError: () => setMessage("The grant could not be revoked. Refresh and try again."),
    onSuccess: async () => {
      setReason("");
      setRevoking(undefined);
      setMessage("Management authority revoked.");
      await refresh();
    },
  });
  const isPending = createGrant.isPending || revokeGrant.isPending;
  const canSubmit = Boolean(managerId && source && reason.trim() && !isPending);

  return (
    <div className="organisation-authority-panel">
      <header>
        <div>
          <span className="eyebrow">Delegated authority</span>
          <h2>{unit.shortName}</h2>
          <p>Grant one action at a time, within authority you already hold.</p>
        </div>
        <button onClick={onClose} type="button">
          Close
        </button>
      </header>

      <form
        onSubmit={(event) => {
          event.preventDefault();
          if (revoking) revokeGrant.mutate(revoking);
          else createGrant.mutate();
        }}
      >
        {revoking ? (
          <RevokeFields grant={revoking} onCancel={() => setRevoking(undefined)} />
        ) : (
          <>
            <label>
              Manager
              <select onChange={(event) => setManagerId(event.target.value)} value={managerId}>
                <option value="">Select a user</option>
                {(users.data ?? [])
                  .filter((user) => user.isActive)
                  .map((user) => (
                    <option key={user.id} value={user.id}>
                      {user.displayName}
                    </option>
                  ))}
              </select>
            </label>
            <label>
              Authorising grant
              <select
                onChange={(event) => {
                  const nextId = event.target.value;
                  setSourceId(nextId);
                  if (!activeSources.find((grant) => grant.id === nextId)?.includeDescendants) {
                    setIncludeDescendants(false);
                  }
                }}
                value={sourceId}
              >
                <option value="">Select authority</option>
                {activeSources.map((grant) => (
                  <option key={grant.id} value={grant.id}>
                    {formatAction(grant.action)}
                  </option>
                ))}
              </select>
            </label>
            <label className="organisation-authority-panel__check">
              <input
                checked={includeDescendants}
                disabled={!source?.includeDescendants}
                onChange={(event) => setIncludeDescendants(event.target.checked)}
                type="checkbox"
              />
              Include descendant units
            </label>
            <label>
              Expiry (optional)
              <input
                onChange={(event) => setValidUntil(event.target.value)}
                type="datetime-local"
                value={validUntil}
              />
            </label>
          </>
        )}
        <label>
          Reason
          <textarea
            maxLength={500}
            onChange={(event) => setReason(event.target.value)}
            required
            value={reason}
          />
        </label>
        <button disabled={revoking ? !reason.trim() || isPending : !canSubmit} type="submit">
          {isPending ? "Saving…" : revoking ? "Confirm revocation" : "Grant authority"}
        </button>
      </form>
      {message ? <p role="status">{message}</p> : null}

      <section aria-labelledby="current-authority-title">
        <div className="organisation-authority-panel__heading">
          <KeyRound aria-hidden="true" size={18} />
          <h3 id="current-authority-title">Current authority</h3>
        </div>
        {grants.isLoading || users.isLoading ? <p>Loading authority…</p> : null}
        <GrantList grants={unitGrants} onRevoke={setRevoking} users={users.data ?? []} />
      </section>
    </div>
  );
}

function RevokeFields({ grant, onCancel }: { grant: ManagementGrant; onCancel: () => void }) {
  return (
    <div className="organisation-authority-panel__warning">
      <UserRoundCog aria-hidden="true" size={18} />
      <p>
        Revoke <strong>{formatAction(grant.action)}</strong>? Existing work is not reassigned.
      </p>
      <button onClick={onCancel} type="button">
        Cancel
      </button>
    </div>
  );
}

function GrantList({
  grants,
  onRevoke,
  users,
}: {
  grants: ManagementGrant[];
  onRevoke: (grant: ManagementGrant) => void;
  users: { displayName: string; id: string }[];
}) {
  const names = new Map(users.map((user) => [user.id, user.displayName]));
  const active = grants.filter((grant) => !grant.revokedAt);
  if (active.length === 0) return <p>No active grants are rooted at this unit.</p>;
  return (
    <ul>
      {active.map((grant) => (
        <li key={grant.id}>
          <span>
            <strong>{names.get(grant.managerUserId) ?? "Unknown user"}</strong>
            {formatAction(grant.action)}
          </span>
          <small>{grant.includeDescendants ? "Unit and descendants" : "This unit only"}</small>
          <button onClick={() => onRevoke(grant)} type="button">
            Revoke
          </button>
        </li>
      ))}
    </ul>
  );
}

function formatAction(value: ManagementAction) {
  return value.replace(":", ": ").replaceAll("_", " ");
}
