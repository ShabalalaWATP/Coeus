import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bookmark, Trash2 } from "lucide-react";
import { useState } from "react";

import { useAuth } from "../../lib/auth/auth-context";
import {
  deleteView,
  getSavedViews,
  saveView,
  type BoardFilters,
  type SavedView,
} from "../../lib/api-client/workspace-productivity";

export function SavedBoardViewsPanel({
  unitId,
  filters,
  onApply,
}: {
  unitId: string;
  filters: BoardFilters;
  onApply: (filters: BoardFilters) => void;
}) {
  const { session } = useAuth();
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [open, setOpen] = useState(false);
  const query = useQuery({
    queryKey: ["saved-board-views"],
    queryFn: getSavedViews,
    enabled: open,
    retry: false,
  });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["saved-board-views"] });
  const create = useMutation({
    mutationFn: () => saveView(unitId, name.trim(), filters, session?.csrfToken ?? ""),
    onSuccess: () => {
      setName("");
      void refresh();
    },
  });
  const remove = useMutation({
    mutationFn: (view: SavedView) => deleteView(unitId, view, session?.csrfToken ?? ""),
    onSuccess: () => void refresh(),
  });
  const items = query.data?.items.filter((item) => item.unitId === unitId) ?? [];

  return (
    <details
      className="workspace-productivity"
      onToggle={(event) => setOpen(event.currentTarget.open)}
    >
      <summary>
        <Bookmark aria-hidden="true" size={16} /> Saved board views
      </summary>
      <p>Keep a private shortcut to the current authorised filters.</p>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          if (name.trim()) create.mutate();
        }}
      >
        <label>
          View name
          <input maxLength={80} onChange={(event) => setName(event.target.value)} value={name} />
        </label>
        <button disabled={!name.trim() || create.isPending} type="submit">
          Save current filters
        </button>
      </form>
      {query.isError ? <p role="alert">Saved views are not available.</p> : null}
      {create.isError || remove.isError ? (
        <p role="alert">The saved view could not be changed.</p>
      ) : null}
      {items.length ? (
        <ul>
          {items.map((item) => (
            <li key={item.viewId}>
              <button onClick={() => onApply(item.filters)} type="button">
                {item.name}
              </button>
              <button
                aria-label={`Delete ${item.name}`}
                disabled={remove.isPending}
                onClick={() => remove.mutate(item)}
                type="button"
              >
                <Trash2 aria-hidden="true" size={15} />
              </button>
            </li>
          ))}
        </ul>
      ) : query.isSuccess ? (
        <p>No views saved for this board.</p>
      ) : null}
    </details>
  );
}
