import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ShieldCheck, UserCog } from "lucide-react";
import { useState } from "react";

import { CLEARANCE_OPTIONS, ROLE_OPTIONS } from "./user-options";
import { ErrorState, LoadingState } from "../../components/ui/PageState";
import {
  listAdminUsers,
  resetAdminUserCredential,
  updateAdminUserClearance,
  updateAdminUserRoles,
  updateAdminUserStatus,
  type AdminUser,
} from "../../lib/api-client/admin";
import { useAuth } from "../../lib/auth/auth-context";

type UserMutationInput =
  | { type: "roles"; userId: string; roles: string[] }
  | { type: "clearance"; userId: string; clearanceLevel: number }
  | { type: "status"; userId: string; isActive: boolean };

export default function UserManagementPage() {
  const { session } = useAuth();
  const queryClient = useQueryClient();
  const csrfToken = session?.csrfToken ?? "";
  const [actionError, setActionError] = useState<string | null>(null);
  const [resetResult, setResetResult] = useState<{
    temporaryCredential: string;
    userId: string;
  } | null>(null);
  const usersQuery = useQuery({ queryKey: ["admin-users"], queryFn: listAdminUsers });
  const updateMutation = useMutation({
    mutationFn: (input: UserMutationInput) => {
      if (input.type === "roles") {
        return updateAdminUserRoles(input.userId, input.roles, csrfToken);
      }
      if (input.type === "clearance") {
        return updateAdminUserClearance(input.userId, input.clearanceLevel, csrfToken);
      }
      return updateAdminUserStatus(input.userId, input.isActive, csrfToken);
    },
    onError: () => setActionError("The user change could not be saved. Refresh and try again."),
    onMutate: () => {
      setActionError(null);
      setResetResult(null);
    },
    onSuccess: (updatedUser) => {
      queryClient.setQueryData<AdminUser[]>(["admin-users"], (current) =>
        (current ?? []).map((user) => (user.id === updatedUser.id ? updatedUser : user)),
      );
    },
  });
  const resetMutation = useMutation({
    mutationFn: (userId: string) => resetAdminUserCredential(userId, csrfToken),
    onError: () => setActionError("The credential could not be reset. Refresh and try again."),
    onMutate: () => {
      setActionError(null);
      setResetResult(null);
    },
    onSuccess: (result, userId) =>
      setResetResult({ temporaryCredential: result.temporaryCredential, userId }),
  });
  const isSaving = updateMutation.isPending || resetMutation.isPending;

  return (
    <div className="project-page">
      <section className="overview-hero" aria-labelledby="users-title">
        <div>
          <h1 id="users-title">Users</h1>
          <p>Manage team access, role assignments, clearance levels and account status.</p>
        </div>
        <div className="classification-note">MOCK DATA ONLY</div>
      </section>

      <section className="surface admin-users" aria-label="User management">
        <div className="section-heading access-heading">
          <UserCog aria-hidden="true" size={20} />
          <h2>Accounts</h2>
        </div>
        {actionError ? (
          <p className="auth-error" role="alert">
            {actionError}
          </p>
        ) : null}
        {usersQuery.isLoading ? <LoadingState label="Loading users" /> : null}
        {usersQuery.isError ? <ErrorState onRetry={() => void usersQuery.refetch()} /> : null}
        {usersQuery.data?.map((user) => (
          <UserManagementRow
            currentUserId={session?.user.id ?? ""}
            isSaving={isSaving}
            key={user.id}
            onReset={(userId) => resetMutation.mutate(userId)}
            onUpdate={(input) => updateMutation.mutate(input)}
            resetCredential={
              resetResult?.userId === user.id ? resetResult.temporaryCredential : null
            }
            user={user}
          />
        ))}
      </section>
    </div>
  );
}

type UserManagementRowProps = {
  currentUserId: string;
  isSaving: boolean;
  onReset: (userId: string) => void;
  onUpdate: (input: UserMutationInput) => void;
  resetCredential: string | null;
  user: AdminUser;
};

function UserManagementRow({
  currentUserId,
  isSaving,
  onReset,
  onUpdate,
  resetCredential,
  user,
}: UserManagementRowProps) {
  const self = user.id === currentUserId;

  function toggleRole(role: string, checked: boolean) {
    const nextRoles = checked
      ? [...new Set([...user.roles, role])]
      : user.roles.filter((currentRole) => currentRole !== role);
    if (nextRoles.length > 0) {
      onUpdate({ type: "roles", userId: user.id, roles: nextRoles });
    }
  }

  return (
    <article className="admin-user-row">
      <div className="admin-user-row__identity">
        <ShieldCheck aria-hidden="true" size={18} />
        <div>
          <strong>{user.displayName}</strong>
          <span>{user.username}</span>
        </div>
      </div>
      <fieldset className="admin-user-row__roles" disabled={self || isSaving}>
        <legend>Roles</legend>
        {ROLE_OPTIONS.map((role) => (
          <label key={role}>
            <input
              checked={user.roles.includes(role)}
              onChange={(event) => toggleRole(role, event.target.checked)}
              type="checkbox"
            />
            {role}
          </label>
        ))}
      </fieldset>
      <label className="admin-user-row__select">
        Clearance
        <select
          disabled={self || isSaving}
          onChange={(event) =>
            onUpdate({
              type: "clearance",
              userId: user.id,
              clearanceLevel: Number(event.target.value),
            })
          }
          value={user.clearanceLevel}
        >
          {CLEARANCE_OPTIONS.map((level) => (
            <option key={level} value={level}>
              Level {level}
            </option>
          ))}
        </select>
      </label>
      <label className="admin-user-row__status">
        <input
          checked={user.isActive}
          disabled={self || isSaving}
          onChange={(event) =>
            onUpdate({ type: "status", userId: user.id, isActive: event.target.checked })
          }
          type="checkbox"
        />
        Active account
      </label>
      <button
        className="admin-user-row__reset"
        disabled={self || isSaving}
        onClick={() => onReset(user.id)}
        type="button"
      >
        Reset credential
      </button>
      {self ? <p className="admin-user-row__note">Signed-in account changes are blocked.</p> : null}
      {resetCredential ? (
        <p className="admin-user-row__credential" role="status">
          Temporary credential: <code>{resetCredential}</code>. Shown once.
        </p>
      ) : null}
    </article>
  );
}
