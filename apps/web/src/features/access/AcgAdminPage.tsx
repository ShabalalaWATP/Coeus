import { useMemo, useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { KeyRound, Plus, Save, UserPlus, UsersRound } from "lucide-react";

import { apiClient, type AccessControlGroup } from "../../lib/api-client/client";
import { useAuth } from "../../lib/auth/auth-context";

type AcgFormState = {
  code: string;
  name: string;
  description: string;
};

export default function AcgAdminPage() {
  const { session } = useAuth();
  const queryClient = useQueryClient();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [createForm, setCreateForm] = useState<AcgFormState>({
    code: "",
    name: "",
    description: "",
  });
  const [editName, setEditName] = useState("");
  const [isActive, setIsActive] = useState(true);
  const [memberUserId, setMemberUserId] = useState("");

  const acgsQuery = useQuery({
    queryKey: ["acgs"],
    queryFn: () => apiClient.listAcgs(),
  });
  const acgs = useMemo(() => acgsQuery.data ?? [], [acgsQuery.data]);
  const selectedAcg = useMemo(
    () => acgs.find((acg) => acg.id === (selectedId ?? acgs[0]?.id)),
    [acgs, selectedId],
  );
  const csrfToken = session?.csrfToken ?? "";

  const createAcg = useMutation({
    mutationFn: () => apiClient.createAcg(createForm, csrfToken),
    onSuccess: async (created) => {
      setCreateForm({ code: "", name: "", description: "" });
      setSelectedId(created.id);
      await queryClient.invalidateQueries({ queryKey: ["acgs"] });
    },
  });
  const updateAcg = useMutation({
    mutationFn: (acg: AccessControlGroup) =>
      apiClient.updateAcg(acg.id, { name: editName || acg.name, isActive }, csrfToken),
    onSuccess: async (updated) => {
      setSelectedId(updated.id);
      await queryClient.invalidateQueries({ queryKey: ["acgs"] });
    },
  });
  const addMember = useMutation({
    mutationFn: (acg: AccessControlGroup) =>
      apiClient.addAcgMember(acg.id, memberUserId, csrfToken),
    onSuccess: async () => {
      setMemberUserId("");
      await queryClient.invalidateQueries({ queryKey: ["acgs"] });
    },
  });

  function submitCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    createAcg.mutate();
  }

  function submitUpdate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (selectedAcg !== undefined) {
      updateAcg.mutate(selectedAcg);
    }
  }

  function submitMember(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (selectedAcg !== undefined) {
      addMember.mutate(selectedAcg);
    }
  }

  return (
    <div className="access-page">
      <section className="overview-hero" aria-labelledby="acg-title">
        <div>
          <h1 id="acg-title">Access Control Groups</h1>
          <p>MOCK DATA ONLY access groups for Sprint 3 project and product filtering.</p>
        </div>
        <div className="classification-note">MOCK DATA ONLY</div>
      </section>

      <section className="access-grid">
        <div className="surface access-list" aria-label="Access control groups">
          <div className="section-heading access-heading">
            <KeyRound aria-hidden="true" size={20} />
            <h2>Groups</h2>
          </div>
          {acgsQuery.isLoading ? <p>Loading access groups</p> : null}
          {acgs.map((acg) => (
            <button
              className={
                selectedAcg?.id === acg.id ? "access-row access-row--active" : "access-row"
              }
              key={acg.id}
              onClick={() => {
                setSelectedId(acg.id);
                setEditName(acg.name);
                setIsActive(acg.isActive);
              }}
              type="button"
            >
              <span>{acg.code}</span>
              <strong>{acg.name}</strong>
              <small>{acg.memberUserIds.length} members</small>
            </button>
          ))}
        </div>

        <div className="surface access-detail" aria-label="Selected access group">
          <div className="section-heading access-heading">
            <UsersRound aria-hidden="true" size={20} />
            <h2>{selectedAcg?.name ?? "No group selected"}</h2>
          </div>
          {selectedAcg === undefined ? null : (
            <>
              <dl className="detail-list">
                <div>
                  <dt>Code</dt>
                  <dd>{selectedAcg.code}</dd>
                </div>
                <div>
                  <dt>Status</dt>
                  <dd>{selectedAcg.isActive ? "Active" : "Inactive"}</dd>
                </div>
                <div>
                  <dt>Members</dt>
                  <dd>{selectedAcg.memberUserIds.length}</dd>
                </div>
              </dl>
              <p>{selectedAcg.description}</p>
              <form className="inline-form" onSubmit={submitUpdate}>
                <label>
                  Name
                  <input
                    onChange={(event) => setEditName(event.target.value)}
                    placeholder={selectedAcg.name}
                    value={editName}
                  />
                </label>
                <label className="checkbox-line">
                  <input
                    checked={isActive}
                    onChange={(event) => setIsActive(event.target.checked)}
                    type="checkbox"
                  />
                  Active
                </label>
                <button type="submit">
                  <Save aria-hidden="true" size={16} /> Save
                </button>
              </form>
              <form className="inline-form" onSubmit={submitMember}>
                <label>
                  User ID
                  <input
                    onChange={(event) => setMemberUserId(event.target.value)}
                    placeholder="00000000-0000-0000-0000-000000000000"
                    value={memberUserId}
                  />
                </label>
                <button type="submit">
                  <UserPlus aria-hidden="true" size={16} /> Add member
                </button>
              </form>
            </>
          )}
        </div>
      </section>

      <section className="surface" aria-labelledby="create-acg-title">
        <div className="section-heading access-heading">
          <Plus aria-hidden="true" size={20} />
          <h2 id="create-acg-title">Create Group</h2>
        </div>
        <form
          aria-label="Create access control group"
          className="create-grid"
          onSubmit={submitCreate}
        >
          <label>
            Code
            <input
              onChange={(event) => setCreateForm({ ...createForm, code: event.target.value })}
              required
              value={createForm.code}
            />
          </label>
          <label>
            Name
            <input
              onChange={(event) => setCreateForm({ ...createForm, name: event.target.value })}
              required
              value={createForm.name}
            />
          </label>
          <label>
            Description
            <input
              onChange={(event) =>
                setCreateForm({ ...createForm, description: event.target.value })
              }
              required
              value={createForm.description}
            />
          </label>
          <button type="submit">
            <Plus aria-hidden="true" size={16} /> Create
          </button>
        </form>
      </section>
    </div>
  );
}
