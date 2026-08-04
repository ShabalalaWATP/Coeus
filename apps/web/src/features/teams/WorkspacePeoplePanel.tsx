import { useQuery } from "@tanstack/react-query";
import { Search, UserRoundCheck } from "lucide-react";
import { useState } from "react";

import { ErrorState, LoadingState } from "../../components/ui/PageState";
import { getWorkspacePeople, type WorkspaceScope } from "../../lib/api-client/workspace-operations";

export function WorkspacePeoplePanel({
  includeDescendants,
  unitId,
}: {
  includeDescendants: boolean;
  unitId: string;
}) {
  const [input, setInput] = useState("");
  const [query, setQuery] = useState("");
  const scope: WorkspaceScope = includeDescendants ? "descendants" : "direct";
  const people = useQuery({
    queryKey: ["workspace-people", unitId, scope, query],
    queryFn: () => getWorkspacePeople(unitId, scope, query),
    retry: false,
  });
  if (people.isLoading) return <LoadingState label="Loading authorised team roster" />;
  if (people.isError) {
    return (
      <ErrorState
        message="The authorised roster could not be loaded."
        onRetry={() => void people.refetch()}
      />
    );
  }
  return (
    <section className="workspace-people" aria-labelledby="workspace-people-title">
      <header className="workspace-panel-heading">
        <div>
          <h4 id="workspace-people-title">People</h4>
          <p>
            Effective home-team roles and working-pattern summaries. Private calendar and profile
            details are not shown.
          </p>
        </div>
      </header>
      <form
        role="search"
        onSubmit={(event) => {
          event.preventDefault();
          setQuery(input.trim().length >= 2 ? input.trim() : "");
        }}
      >
        <label>
          <Search aria-hidden="true" size={16} />
          <span className="sr-only">Search people</span>
          <input
            maxLength={120}
            onChange={(event) => setInput(event.target.value)}
            placeholder="Search by name or username"
            value={input}
          />
        </label>
        <button type="submit">Search</button>
      </form>
      {people.data!.items.length === 0 ? <p>No authorised people match this search.</p> : null}
      <ul className="workspace-people__list">
        {people.data!.items.map((person) => (
          <li key={person.userId}>
            <UserRoundCheck aria-hidden="true" size={18} />
            <span>
              <strong>{person.displayName}</strong>
              <small>
                {person.membershipRole.replaceAll("_", " ")} · {person.workingPattern}
              </small>
            </span>
            <span
              className={
                person.assignmentEligible ? "status-chip status-chip--success" : "status-chip"
              }
            >
              {person.assignmentEligible ? "Assignment eligible" : "Not assignable"}
            </span>
          </li>
        ))}
      </ul>
      {people.data!.truncated ? <p>Only the first 100 matching people are shown.</p> : null}
    </section>
  );
}
