import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CopyPlus, Trash2 } from "lucide-react";
import { useState } from "react";

import { useAuth } from "../../lib/auth/auth-context";
import {
  deletePackageTemplate,
  getPackageTemplates,
  savePackageTemplate,
  type PackageTemplate,
} from "../../lib/api-client/workspace-productivity";

type Grant = { id: string; version: number };

export function PackageTemplatesPanel({ unitId, grant }: { unitId: string; grant?: Grant }) {
  const { session } = useAuth();
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [titles, setTitles] = useState("");
  const [open, setOpen] = useState(false);
  const queryKey = ["package-templates", unitId];
  const query = useQuery({
    queryKey,
    queryFn: () => getPackageTemplates(unitId),
    enabled: open,
    retry: false,
  });
  const refresh = () => queryClient.invalidateQueries({ queryKey });
  const create = useMutation({
    mutationFn: () =>
      savePackageTemplate(
        unitId,
        {
          name: name.trim(),
          packageTitles: titles
            .split("\n")
            .map((value) => value.trim())
            .filter(Boolean),
        },
        grant!,
        session?.csrfToken ?? "",
      ),
    onSuccess: () => {
      setName("");
      setTitles("");
      void refresh();
    },
  });
  const remove = useMutation({
    mutationFn: (template: PackageTemplate) =>
      deletePackageTemplate(unitId, template, grant!, session?.csrfToken ?? ""),
    onSuccess: () => void refresh(),
  });

  return (
    <details
      className="workspace-productivity"
      onToggle={(event) => setOpen(event.currentTarget.open)}
    >
      <summary>
        <CopyPlus aria-hidden="true" size={16} /> Package templates
      </summary>
      <p>Reusable package outlines suggest structure only. They do not assign or approve work.</p>
      {grant ? (
        <form
          onSubmit={(event) => {
            event.preventDefault();
            if (name.trim() && titles.trim()) create.mutate();
          }}
        >
          <label>
            Template name
            <input maxLength={80} onChange={(event) => setName(event.target.value)} value={name} />
          </label>
          <label>
            Package titles, one per line
            <textarea
              maxLength={2400}
              onChange={(event) => setTitles(event.target.value)}
              rows={3}
              value={titles}
            />
          </label>
          <button disabled={!name.trim() || !titles.trim() || create.isPending} type="submit">
            Create template
          </button>
        </form>
      ) : (
        <p>You can view templates. A workspace configuration grant is required to change them.</p>
      )}
      {query.isError ? <p role="alert">Templates are not available.</p> : null}
      {create.isError || remove.isError ? (
        <p role="alert">The template could not be changed.</p>
      ) : null}
      <ul>
        {query.data?.items.map((item) => (
          <li key={item.templateId}>
            <span>
              <strong>{item.name}</strong>
              <small>{item.packageTitles.join(" · ")}</small>
            </span>
            {grant ? (
              <button
                aria-label={`Delete ${item.name}`}
                disabled={remove.isPending}
                onClick={() => remove.mutate(item)}
                type="button"
              >
                <Trash2 aria-hidden="true" size={15} />
              </button>
            ) : null}
          </li>
        ))}
      </ul>
    </details>
  );
}
