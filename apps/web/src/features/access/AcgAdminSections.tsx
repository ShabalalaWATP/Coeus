import type { Dispatch, FormEventHandler, SetStateAction } from "react";
import { KeyRound, Plus, Save, UserMinus, UserPlus, UsersRound } from "lucide-react";

import { ErrorState, LoadingState } from "../../components/ui/PageState";
import type {
  AccessControlGroup,
  CreateAccessControlGroupRequest,
} from "../../lib/api-client/access";
import type { AccessGroupDirectoryUser } from "../../lib/api-client/access-groups";

export function AcgSelector({
  acgs,
  isError,
  isLoading,
  onRetry,
  onSelect,
  selectedId,
}: {
  acgs: AccessControlGroup[];
  isError: boolean;
  isLoading: boolean;
  onRetry: () => void;
  onSelect: (id: string) => void;
  selectedId?: string;
}) {
  return (
    <div className="surface access-list" aria-label="Access control groups">
      <div className="section-heading access-heading">
        <KeyRound aria-hidden="true" size={20} />
        <h2>Groups</h2>
      </div>
      {isLoading ? <LoadingState label="Loading access groups" /> : null}
      {isError ? <ErrorState onRetry={onRetry} /> : null}
      {acgs.map((acg) => (
        <button
          className={selectedId === acg.id ? "access-row access-row--active" : "access-row"}
          key={acg.id}
          onClick={() => onSelect(acg.id)}
          type="button"
        >
          <span>{acg.code}</span>
          <strong>{acg.name}</strong>
          <small>{acg.memberUserIds.length} members</small>
        </button>
      ))}
    </div>
  );
}

export function AcgEditor({
  acg,
  canManageMembers,
  canUpdate,
  directoryError,
  directoryLoading,
  directorySearch,
  directoryTotal,
  editName,
  isActive,
  memberUserId,
  onAddMember,
  onDirectorySearch,
  onEditName,
  onIsActive,
  onMemberUserId,
  onRemoveMember,
  onUpdate,
  addPending,
  removePending,
  updatePending,
  users,
}: {
  acg?: AccessControlGroup;
  canManageMembers: boolean;
  canUpdate: boolean;
  directoryError: boolean;
  directoryLoading: boolean;
  directorySearch: string;
  directoryTotal: number;
  editName: string;
  isActive: boolean;
  memberUserId: string;
  onAddMember: FormEventHandler<HTMLFormElement>;
  onDirectorySearch: (value: string) => void;
  onEditName: (value: string) => void;
  onIsActive: (value: boolean) => void;
  onMemberUserId: (value: string) => void;
  onRemoveMember: (id: string) => void;
  onUpdate: FormEventHandler<HTMLFormElement>;
  addPending: boolean;
  removePending: boolean;
  updatePending: boolean;
  users: AccessGroupDirectoryUser[];
}) {
  return (
    <div className="surface access-detail" aria-label="Selected access group">
      <div className="section-heading access-heading">
        <UsersRound aria-hidden="true" size={20} />
        <h2>{acg?.name ?? "No group selected"}</h2>
      </div>
      {acg ? (
        <>
          <dl className="detail-list">
            <div>
              <dt>Code</dt>
              <dd>{acg.code}</dd>
            </div>
            <div>
              <dt>Status</dt>
              <dd>{acg.isActive ? "Active" : "Inactive"}</dd>
            </div>
            <div>
              <dt>Members</dt>
              <dd>{acg.memberUserIds.length}</dd>
            </div>
          </dl>
          <p>{acg.description}</p>
          <div className="member-list" aria-label="Access group members">
            {acg.memberUserIds.length === 0 ? (
              <p>No members assigned.</p>
            ) : (
              acg.memberUserIds.map((userId) => (
                <div className="member-row" key={userId}>
                  <span>
                    <strong>
                      {acg.members?.find((member) => member.id === userId)?.displayName ??
                        "Identity unavailable"}
                    </strong>
                    <small>
                      {acg.members?.find((member) => member.id === userId)?.username ??
                        "Contact an administrator"}
                    </small>
                  </span>
                  {canManageMembers ? (
                    <button
                      aria-label={`Remove ${userId} from ${acg.name}`}
                      disabled={removePending}
                      onClick={() => onRemoveMember(userId)}
                      type="button"
                    >
                      <UserMinus aria-hidden="true" size={15} /> Remove
                    </button>
                  ) : null}
                </div>
              ))
            )}
          </div>
          {canUpdate ? (
            <form className="inline-form" onSubmit={onUpdate}>
              <label>
                Name
                <input
                  onChange={(event) => onEditName(event.target.value)}
                  placeholder={acg.name}
                  value={editName}
                />
              </label>
              <label className="checkbox-line">
                <input
                  checked={isActive}
                  onChange={(event) => onIsActive(event.target.checked)}
                  type="checkbox"
                />
                Active
              </label>
              <button disabled={updatePending} type="submit">
                <Save aria-hidden="true" size={16} /> Save
              </button>
            </form>
          ) : null}
          {canManageMembers ? (
            <form className="inline-form" onSubmit={onAddMember}>
              <label>
                Search active users
                <input
                  onChange={(event) => onDirectorySearch(event.target.value)}
                  placeholder="Name or username"
                  value={directorySearch}
                />
              </label>
              {directoryLoading ? <p role="status">Searching active users…</p> : null}
              {directoryError ? (
                <p role="alert">The active-user directory could not be loaded.</p>
              ) : null}
              {!directoryLoading &&
              !directoryError &&
              directorySearch.trim().length >= 3 &&
              directoryTotal === 0 ? (
                <p>No active users match this search.</p>
              ) : null}
              {directoryTotal > users.length ? (
                <p>More users match. Refine the name or username to narrow the results.</p>
              ) : null}
              {users.length ? (
                <ul aria-label="Matching active users" className="member-candidates">
                  {users
                    .filter((user) => !acg.memberUserIds.includes(user.id))
                    .map((user) => (
                      <li key={user.id}>
                        <button
                          aria-pressed={memberUserId === user.id}
                          onClick={() => onMemberUserId(user.id)}
                          type="button"
                        >
                          {user.displayName} ({user.username})
                        </button>
                      </li>
                    ))}
                </ul>
              ) : null}
              <button disabled={addPending || memberUserId === ""} type="submit">
                <UserPlus aria-hidden="true" size={16} /> Add member
              </button>
            </form>
          ) : null}
          {!canUpdate && !canManageMembers ? (
            <p>You have read-only access to access control groups.</p>
          ) : null}
        </>
      ) : null}
    </div>
  );
}

export function AcgCreateForm({
  form,
  onChange,
  onSubmit,
  pending,
}: {
  form: CreateAccessControlGroupRequest;
  onChange: Dispatch<SetStateAction<CreateAccessControlGroupRequest>>;
  onSubmit: FormEventHandler<HTMLFormElement>;
  pending: boolean;
}) {
  return (
    <section className="surface" aria-labelledby="create-acg-title">
      <div className="section-heading access-heading">
        <Plus aria-hidden="true" size={20} />
        <h2 id="create-acg-title">Create Group</h2>
      </div>
      <form aria-label="Create access control group" className="create-grid" onSubmit={onSubmit}>
        {(["code", "name", "description"] as const).map((field) => (
          <label key={field}>
            {field[0].toUpperCase() + field.slice(1)}
            <input
              onChange={(event) => onChange({ ...form, [field]: event.target.value })}
              required
              value={form[field]}
            />
          </label>
        ))}
        <button disabled={pending} type="submit">
          <Plus aria-hidden="true" size={16} /> Create
        </button>
      </form>
    </section>
  );
}
