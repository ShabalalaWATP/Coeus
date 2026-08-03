import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FolderKanban, Plus } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { ProjectDetailPanel } from "./ProjectDetailPanel";
import { StoreSectionHeading } from "./StoreSectionHeading";
import { StoreWorkspaceHeader } from "./StoreWorkspaceHeader";
import {
  createStoreProject,
  getStoreProject,
  getStoreProjects,
  type StoreProjectCreateInput,
} from "../../lib/api-client/store-organisation";
import { useAuth } from "../../lib/auth/auth-context";

const emptyProject: StoreProjectCreateInput = {
  name: "",
  purpose: "",
  region: null,
  dateFrom: null,
  dateTo: null,
};

export default function StoreProjectsPage() {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const { session } = useAuth();
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState(emptyProject);
  const [creating, setCreating] = useState(false);
  const projects = useQuery({ queryKey: ["store-projects"], queryFn: getStoreProjects });
  const project = useQuery({
    enabled: projectId !== undefined,
    queryKey: ["store-project", projectId],
    queryFn: () => getStoreProject(projectId ?? ""),
  });
  const create = useMutation({
    mutationFn: () => createStoreProject(draft, session?.csrfToken ?? ""),
    onSuccess: (created) => {
      setDraft(emptyProject);
      setCreating(false);
      void queryClient.invalidateQueries({ queryKey: ["store-projects"] });
      queryClient.setQueryData(["store-project", created.id], created);
      void navigate(`/store/projects/${encodeURIComponent(created.id)}`);
    },
  });

  return (
    <div className="store-page">
      <StoreWorkspaceHeader
        action={
          <button
            className="store-action"
            onClick={() => setCreating((value) => !value)}
            type="button"
          >
            <Plus aria-hidden="true" size={17} />
            New project
          </button>
        }
        description="Organise authorised reporting, research notes and questions with your team."
        title="Projects"
        titleId="projects-title"
      />

      {creating ? (
        <ProjectCreateForm
          draft={draft}
          error={create.isError}
          pending={create.isPending}
          onChange={setDraft}
          onSubmit={() => create.mutate()}
        />
      ) : null}

      <section className="store-projects-layout">
        <aside className="surface store-project-list" aria-label="Your projects">
          <StoreSectionHeading count={projects.data?.length ?? 0} title="Your projects" />
          {projects.isLoading ? <p>Loading projects…</p> : null}
          {projects.isError ? <p className="auth-error">Projects are unavailable.</p> : null}
          {(projects.data ?? []).map((item) => (
            <Link
              aria-current={item.id === projectId ? "page" : undefined}
              className="store-project-list__item"
              key={item.id}
              to={`/store/projects/${encodeURIComponent(item.id)}`}
            >
              <FolderKanban aria-hidden="true" size={18} />
              <span>
                <strong>{item.name}</strong>
                <small>
                  {item.visibleProductCount} products · {item.memberCount} members
                </small>
              </span>
              {item.archived ? <span className="store-chip">Archived</span> : null}
            </Link>
          ))}
          {!projects.isLoading && !projects.isError && projects.data?.length === 0 ? (
            <p>No projects yet. Create one for an operation, topic or continuing question.</p>
          ) : null}
        </aside>

        {projectId === undefined ? (
          <section className="surface store-workspace-empty">
            <FolderKanban aria-hidden="true" size={26} />
            <h2>Select or create a project</h2>
            <p>Projects keep collaborative context separate from your private Library folders.</p>
          </section>
        ) : project.isLoading ? (
          <section className="surface">
            <p>Loading project…</p>
          </section>
        ) : project.isError || project.data === undefined ? (
          <section className="surface">
            <p className="auth-error">This project is unavailable.</p>
          </section>
        ) : (
          <ProjectDetailPanel project={project.data} />
        )}
      </section>
    </div>
  );
}

function ProjectCreateForm({
  draft,
  error,
  onChange,
  onSubmit,
  pending,
}: {
  draft: StoreProjectCreateInput;
  error: boolean;
  onChange: (value: StoreProjectCreateInput) => void;
  onSubmit: () => void;
  pending: boolean;
}) {
  const update = (field: keyof StoreProjectCreateInput, value: string) =>
    onChange({ ...draft, [field]: value || null });
  return (
    <form
      className="surface store-project-create"
      onSubmit={(event) => {
        event.preventDefault();
        if (draft.name.trim() && draft.purpose.trim()) onSubmit();
      }}
    >
      <StoreSectionHeading title="Create project" />
      <label>
        Project name
        <input
          maxLength={80}
          onChange={(event) => update("name", event.target.value)}
          value={draft.name}
        />
      </label>
      <label>
        Purpose
        <textarea
          maxLength={2000}
          onChange={(event) => update("purpose", event.target.value)}
          value={draft.purpose}
        />
      </label>
      <label>
        Region
        <input
          maxLength={80}
          onChange={(event) => update("region", event.target.value)}
          value={draft.region ?? ""}
        />
      </label>
      <label>
        Coverage from
        <input
          onChange={(event) => update("dateFrom", event.target.value)}
          type="date"
          value={draft.dateFrom ?? ""}
        />
      </label>
      <label>
        Coverage to
        <input
          onChange={(event) => update("dateTo", event.target.value)}
          type="date"
          value={draft.dateTo ?? ""}
        />
      </label>
      <button
        className="store-action"
        disabled={!draft.name.trim() || !draft.purpose.trim() || pending}
        type="submit"
      >
        Create project
      </button>
      {error ? (
        <p className="auth-error" role="alert">
          The project could not be created.
        </p>
      ) : null}
    </form>
  );
}
