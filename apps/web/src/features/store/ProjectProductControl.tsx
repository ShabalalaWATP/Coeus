import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FolderPlus } from "lucide-react";
import { useState } from "react";

import { addStoreProjectProduct, getStoreProjects } from "../../lib/api-client/store-organisation";
import { useAuth } from "../../lib/auth/auth-context";

export function ProjectProductControl({ productId }: { productId: string }) {
  const { session } = useAuth();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [projectId, setProjectId] = useState("");
  const [saved, setSaved] = useState(false);
  const projects = useQuery({
    enabled: open,
    queryKey: ["store-projects"],
    queryFn: getStoreProjects,
  });
  const available = Array.isArray(projects.data)
    ? projects.data.filter((project) => !project.archived)
    : [];
  const add = useMutation({
    mutationFn: () => addStoreProjectProduct(projectId, productId, session?.csrfToken ?? ""),
    onSuccess: (project) => {
      setSaved(true);
      queryClient.setQueryData(["store-project", project.id], project);
      void queryClient.invalidateQueries({ queryKey: ["store-projects"] });
    },
  });

  if (!open) {
    return (
      <button className="store-action" onClick={() => setOpen(true)} type="button">
        <FolderPlus aria-hidden="true" size={17} />
        Add to project
      </button>
    );
  }
  return (
    <div className="project-product-control" aria-label="Project collection">
      {projects.isLoading ? <small>Loading projects…</small> : null}
      {!projects.isLoading && available.length === 0 ? (
        <small>No active projects are available.</small>
      ) : null}
      {available.length > 0 ? (
        <label>
          <span className="sr-only">Add to project</span>
          <select
            onChange={(event) => {
              setProjectId(event.target.value);
              setSaved(false);
            }}
            value={projectId}
          >
            <option value="">Choose project</option>
            {available.map((project) => (
              <option key={project.id} value={project.id}>
                {project.name}
              </option>
            ))}
          </select>
        </label>
      ) : null}
      {available.length > 0 ? (
        <button disabled={!projectId || add.isPending} onClick={() => add.mutate()} type="button">
          <FolderPlus aria-hidden="true" size={17} />
          {saved ? "Added" : "Add"}
        </button>
      ) : null}
      <button
        className="store-action store-action--secondary"
        onClick={() => setOpen(false)}
        type="button"
      >
        Close
      </button>
      {projects.isError ? <small className="auth-error">Projects are unavailable.</small> : null}
      {add.isError ? <small className="auth-error">Could not add this product.</small> : null}
    </div>
  );
}
