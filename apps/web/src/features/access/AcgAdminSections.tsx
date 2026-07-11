import type { Dispatch, FormEventHandler, SetStateAction } from "react";
import { KeyRound, Plus, Save, UserMinus, UserPlus, UsersRound } from "lucide-react";

import { ErrorState, LoadingState } from "../../components/ui/PageState";
import type {
  AccessControlGroup,
  CreateAccessControlGroupRequest,
} from "../../lib/api-client/access";

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
  editName,
  isActive,
  memberUserId,
  onAddMember,
  onEditName,
  onIsActive,
  onMemberUserId,
  onRemoveMember,
  onUpdate,
  removePending,
}: {
  acg?: AccessControlGroup;
  canManageMembers: boolean;
  canUpdate: boolean;
  editName: string;
  isActive: boolean;
  memberUserId: string;
  onAddMember: FormEventHandler<HTMLFormElement>;
  onEditName: (value: string) => void;
  onIsActive: (value: boolean) => void;
  onMemberUserId: (value: string) => void;
  onRemoveMember: (id: string) => void;
  onUpdate: FormEventHandler<HTMLFormElement>;
  removePending: boolean;
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
                  <code>{userId}</code>
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
              <button type="submit">
                <Save aria-hidden="true" size={16} /> Save
              </button>
            </form>
          ) : null}
          {canManageMembers ? (
            <form className="inline-form" onSubmit={onAddMember}>
              <label>
                User ID
                <input
                  onChange={(event) => onMemberUserId(event.target.value)}
                  placeholder="00000000-0000-0000-0000-000000000000"
                  value={memberUserId}
                />
              </label>
              <button type="submit">
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
