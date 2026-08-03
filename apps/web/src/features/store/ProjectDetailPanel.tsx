import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Archive, MessageSquareText, RotateCcw, Trash2, UserPlus } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { StoreSectionHeading } from "./StoreSectionHeading";
import {
  addStoreProjectEntry,
  addStoreProjectMember,
  removeStoreProjectMember,
  removeStoreProjectProduct,
  setStoreProjectArchived,
  type StoreProject,
} from "../../lib/api-client/store-organisation";
import { useAuth } from "../../lib/auth/auth-context";

const activityLabels: Record<string, string> = {
  project_created: "created the project",
  project_member_added: "added a project member",
  project_member_removed: "removed a project member",
  project_product_added: "added intelligence",
  project_product_removed: "removed intelligence",
  project_note_added: "added a note",
  project_question_added: "added a question",
  project_archived: "archived the project",
  project_restored: "restored the project",
};

export function ProjectDetailPanel({ project }: { project: StoreProject }) {
  const { session } = useAuth();
  const queryClient = useQueryClient();
  const [username, setUsername] = useState("");
  const [entryKind, setEntryKind] = useState<"note" | "question">("note");
  const [entryBody, setEntryBody] = useState("");
  const csrf = session?.csrfToken ?? "";
  const updateProject = (updated: StoreProject) => {
    queryClient.setQueryData(["store-project", project.id], updated);
    void queryClient.invalidateQueries({ queryKey: ["store-projects"] });
  };
  const status = useMutation({
    mutationFn: () => setStoreProjectArchived(project.id, !project.archived, csrf),
    onSuccess: updateProject,
  });
  const addMember = useMutation({
    mutationFn: () => addStoreProjectMember(project.id, username.trim(), csrf),
    onSuccess: (updated) => {
      setUsername("");
      updateProject(updated);
    },
  });
  const removeMember = useMutation({
    mutationFn: (memberId: string) => removeStoreProjectMember(project.id, memberId, csrf),
    onSuccess: updateProject,
  });
  const removeProduct = useMutation({
    mutationFn: (productId: string) => removeStoreProjectProduct(project.id, productId, csrf),
    onSuccess: updateProject,
  });
  const addEntry = useMutation({
    mutationFn: () => addStoreProjectEntry(project.id, entryKind, entryBody.trim(), csrf),
    onSuccess: (updated) => {
      setEntryBody("");
      updateProject(updated);
    },
  });
  const mutationError =
    status.isError ||
    addMember.isError ||
    removeMember.isError ||
    removeProduct.isError ||
    addEntry.isError;

  return (
    <section className="store-project-detail" aria-labelledby="project-detail-title">
      <header className="surface store-project-detail__header">
        <div>
          {/* Active is the unremarkable default, so only archived is marked. */}
          <div className="store-project-detail__title">
            <h2 id="project-detail-title">{project.name}</h2>
            {project.archived ? <span className="store-status-badge">Archived</span> : null}
          </div>
          <p>{project.purpose}</p>
          <small>
            {[project.region, coverage(project.dateFrom, project.dateTo)]
              .filter(Boolean)
              .join(" · ") || "No geographic or date scope"}
          </small>
        </div>
        {project.owner ? (
          <button
            className="store-action store-action--secondary"
            disabled={status.isPending}
            onClick={() => status.mutate()}
            type="button"
          >
            {project.archived ? (
              <RotateCcw aria-hidden="true" size={17} />
            ) : (
              <Archive aria-hidden="true" size={17} />
            )}
            {project.archived ? "Restore project" : "Archive project"}
          </button>
        ) : null}
      </header>

      {mutationError ? (
        <p className="auth-error" role="alert">
          The project change could not be saved.
        </p>
      ) : null}

      <div className="store-project-detail__grid">
        <section
          className="surface store-project-products"
          aria-labelledby="project-products-title"
        >
          <StoreSectionHeading
            count={project.products.length}
            id="project-products-title"
            level={3}
            title="Intelligence products"
          />
          {project.products.map((product) => (
            <div className="store-project-product" key={product.id}>
              <Link
                state={{ from: `/store/projects/${project.id}`, origin: "project" }}
                to={`/store/products/${encodeURIComponent(product.id)}`}
              >
                <span className="mono-ref">{product.reference}</span>
                <strong>{product.title}</strong>
                <small>
                  {product.areaOrRegion} ·{" "}
                  {coverage(product.timePeriodStart, product.timePeriodEnd)}
                </small>
              </Link>
              {!project.archived ? (
                <button
                  aria-label={`Remove ${product.title} from project`}
                  disabled={removeProduct.isPending}
                  onClick={() => removeProduct.mutate(product.id)}
                  type="button"
                >
                  <Trash2 aria-hidden="true" size={15} />
                </button>
              ) : null}
            </div>
          ))}
          {project.products.length === 0 ? (
            <p>
              Open an authorised product and choose <strong>Add to project</strong>.
            </p>
          ) : null}
        </section>

        <section className="surface store-project-members" aria-labelledby="project-members-title">
          <StoreSectionHeading
            count={project.members.length}
            id="project-members-title"
            level={3}
            title="Members"
          />
          <ul>
            {project.members.map((member) => (
              <li key={member.id}>
                <span>
                  <strong>{member.displayName}</strong>
                  <small>
                    {member.username || "Account removed"}
                    {member.owner ? " · Owner" : ""}
                  </small>
                </span>
                {project.owner && !member.owner && !project.archived ? (
                  <button
                    aria-label={`Remove ${member.displayName}`}
                    disabled={removeMember.isPending}
                    onClick={() => removeMember.mutate(member.id)}
                    type="button"
                  >
                    <Trash2 aria-hidden="true" size={15} />
                  </button>
                ) : null}
              </li>
            ))}
          </ul>
          {project.owner && !project.archived ? (
            <form
              onSubmit={(event) => {
                event.preventDefault();
                if (username.trim()) addMember.mutate();
              }}
            >
              <label>
                Username
                <input
                  maxLength={120}
                  onChange={(event) => setUsername(event.target.value)}
                  placeholder="name@example.test"
                  value={username}
                />
              </label>
              <button disabled={!username.trim() || addMember.isPending} type="submit">
                <UserPlus aria-hidden="true" size={16} /> Add member
              </button>
            </form>
          ) : null}
        </section>
      </div>

      <section className="surface store-project-notes" aria-labelledby="project-notes-title">
        <StoreSectionHeading
          count={project.entries.length}
          id="project-notes-title"
          level={3}
          title="Notes and questions"
        />
        {!project.archived ? (
          <form
            onSubmit={(event) => {
              event.preventDefault();
              if (entryBody.trim()) addEntry.mutate();
            }}
          >
            <label>
              Type
              <select
                onChange={(event) => setEntryKind(event.target.value as "note" | "question")}
                value={entryKind}
              >
                <option value="note">Note</option>
                <option value="question">Intelligence question</option>
              </select>
            </label>
            <label>
              Text
              <textarea
                maxLength={entryKind === "question" ? 500 : 2000}
                onChange={(event) => setEntryBody(event.target.value)}
                value={entryBody}
              />
            </label>
            <button disabled={!entryBody.trim() || addEntry.isPending} type="submit">
              <MessageSquareText aria-hidden="true" size={16} /> Add {entryKind}
            </button>
          </form>
        ) : null}
        <div className="store-project-entry-list">
          {[...project.entries].reverse().map((entry) => (
            <article key={entry.id}>
              <span className="store-chip">{entry.kind === "question" ? "Question" : "Note"}</span>
              <p>{entry.body}</p>
              <small>
                {entry.author.displayName} · {new Date(entry.createdAt).toLocaleString()}
              </small>
            </article>
          ))}
          {project.entries.length === 0 ? (
            <p>No working notes or intelligence questions yet.</p>
          ) : null}
        </div>
      </section>

      <details className="surface store-project-activity">
        <summary>Project activity</summary>
        <ol>
          {[...project.activity].reverse().map((item) => (
            <li key={item.id}>
              <strong>{item.actorDisplayName}</strong>{" "}
              {activityLabels[item.action] ?? "updated the project"}
              <small>{new Date(item.occurredAt).toLocaleString()}</small>
            </li>
          ))}
        </ol>
      </details>
    </section>
  );
}

function coverage(start: string | null, end: string | null) {
  if (!start) return "Date not recorded";
  return `${start} to ${end ?? "ongoing"}`;
}
