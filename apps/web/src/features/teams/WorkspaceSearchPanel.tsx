import { useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { useState } from "react";

import {
  searchWorkspace,
  type WorkspaceScope,
  type WorkspaceSearchResult,
} from "../../lib/api-client/workspace-operations";

export function WorkspaceSearchPanel({
  includeDescendants,
  onSelect,
  storeOnly = false,
  unitId,
}: {
  includeDescendants: boolean;
  onSelect?: (result: WorkspaceSearchResult) => void;
  storeOnly?: boolean;
  unitId: string;
}) {
  const [input, setInput] = useState("");
  const [query, setQuery] = useState("");
  const scope: WorkspaceScope = includeDescendants ? "descendants" : "direct";
  const results = useQuery({
    enabled: query.length >= 2,
    queryKey: ["workspace-search", unitId, scope, query, storeOnly],
    queryFn: () => searchWorkspace(unitId, scope, query, storeOnly),
    retry: false,
  });
  const items = results.data?.items ?? [];
  return (
    <section className="workspace-search" aria-labelledby={"workspace-search-" + unitId}>
      <h4 id={"workspace-search-" + unitId}>
        {storeOnly ? "Find an authorised Store item" : "Search this workspace"}
      </h4>
      <form
        role="search"
        onSubmit={(event) => {
          event.preventDefault();
          if (input.trim().length >= 2) setQuery(input.trim());
        }}
      >
        <label>
          <span className="sr-only">Search terms</span>
          <Search aria-hidden="true" size={16} />
          <input
            maxLength={120}
            onChange={(event) => setInput(event.target.value)}
            placeholder={
              storeOnly ? "Report or project title" : "Team, work package, report or project"
            }
            value={input}
          />
        </label>
        <button disabled={input.trim().length < 2} type="submit">
          Search
        </button>
      </form>
      {results.isError ? <p role="alert">Search could not be completed.</p> : null}
      {query && results.isSuccess && items.length === 0 ? (
        <p>No authorised matches found.</p>
      ) : null}
      {items.length ? (
        <ul aria-label="Authorised workspace search results">
          {items.map((item) => (
            <li key={item.resultType + ":" + item.objectId}>
              <span>
                <strong>{item.label}</strong>
                <small>{item.context}</small>
              </span>
              {onSelect ? (
                <button onClick={() => onSelect(item)} type="button">
                  Select
                </button>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
