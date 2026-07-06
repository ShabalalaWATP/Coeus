import { useMutation, useQuery } from "@tanstack/react-query";
import { UserCheck } from "lucide-react";
import { useState } from "react";

import {
  assignAnalystTask,
  listAnalystCandidates,
  type AnalystTask,
} from "../../lib/api-client/analyst";

type AssignAnalystPanelProps = {
  csrfToken: string;
  onAssigned: (task: AnalystTask) => void;
  ticketId: string;
};

export function AssignAnalystPanel({ csrfToken, onAssigned, ticketId }: AssignAnalystPanelProps) {
  const [analystUserId, setAnalystUserId] = useState("");
  const [workPackages, setWorkPackages] = useState("");
  const candidatesQuery = useQuery({
    queryKey: ["analyst-candidates"],
    queryFn: listAnalystCandidates,
  });
  const assignMutation = useMutation({
    mutationFn: () =>
      assignAnalystTask(ticketId, analystUserId, packageTitles(workPackages), csrfToken),
    onSuccess: (task) => onAssigned(task),
  });
  const candidates = candidatesQuery.data?.analysts ?? [];

  return (
    <section className="routing-assign" aria-label="Assign analyst">
      <h3>Assign analyst</h3>
      <p>
        The route is approved. Choose an analyst to start production. Work packages default to the
        approved route plan when left blank.
      </p>
      {candidatesQuery.isError ? (
        <p role="alert">Analyst candidates could not be loaded. Refresh to try again.</p>
      ) : null}
      <form
        onSubmit={(event) => {
          event.preventDefault();
          assignMutation.mutate();
        }}
      >
        <label>
          Analyst
          <select onChange={(event) => setAnalystUserId(event.target.value)} value={analystUserId}>
            <option value="">Select an analyst</option>
            {candidates.map((candidate) => (
              <option key={candidate.userId} value={candidate.userId}>
                {candidate.displayName}
              </option>
            ))}
          </select>
        </label>
        <label>
          Work packages (semicolon separated)
          <input
            onChange={(event) => setWorkPackages(event.target.value)}
            placeholder="Optional"
            value={workPackages}
          />
        </label>
        <button disabled={analystUserId === "" || assignMutation.isPending} type="submit">
          <UserCheck aria-hidden="true" size={18} />
          Assign analyst
        </button>
      </form>
      {assignMutation.isError ? (
        <p role="alert">Assignment failed. Confirm the ticket is still awaiting assignment.</p>
      ) : null}
    </section>
  );
}

function packageTitles(raw: string) {
  return raw
    .split(";")
    .map((title) => title.trim())
    .filter((title) => title !== "");
}
