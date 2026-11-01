import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";

import { assignmentsByDay } from "../teams/team-calendar-assignments";
import { getTeamTaskBoard } from "../../lib/api-client/team-task-board";
import { getWorkspacePeople } from "../../lib/api-client/workspace-operations";

type Props = { unitId: string; includeDescendants: boolean };

/**
 * Assigned work for the unit, beside the availability it competes with.
 *
 * The board says what is due and who owns it; the people list turns the owner
 * into a name. Both are read-only context, so a failure in either leaves the
 * calendar itself usable.
 */
export function WorkspaceAssignedWork({ unitId, includeDescendants }: Props) {
  // Follow the calendar's own scope toggle: a parent unit holds no work of its
  // own, so showing only direct work would read as an empty team.
  const scope = includeDescendants ? "descendants" : "direct";
  const board = useQuery({
    queryKey: ["workspace-assigned-board", unitId, scope],
    queryFn: () => getTeamTaskBoard(unitId, { includeCompleted: false, scope }),
    retry: false,
  });
  const people = useQuery({
    queryKey: ["workspace-assigned-people", unitId, scope],
    queryFn: () => getWorkspacePeople(unitId, scope),
    retry: false,
  });
  const byDay = useMemo(() => assignmentsByDay(board.data), [board.data]);
  const names = useMemo(() => {
    const lookup = new Map<string, string>();
    for (const person of people.data?.items ?? []) {
      lookup.set(person.userId, person.displayName);
    }
    return lookup;
  }, [people.data]);
  const days = [...byDay.keys()].sort();

  if (board.isLoading) return <p role="status">Loading assigned work…</p>;
  if (board.isError) {
    return <p className="organisation-calendar__empty">Assigned work is unavailable.</p>;
  }
  if (days.length === 0) {
    return <p className="organisation-calendar__empty">No assigned work is dated in this team.</p>;
  }

  return (
    <div className="workspace-assigned">
      <h4>Assigned work</h4>
      <ul aria-label="Assigned work by day">
        {days.map((day) => (
          <li key={day}>
            <time dateTime={day}>{formatDay(day)}</time>
            <ul>
              {(byDay.get(day) ?? []).map((item) => (
                <li key={item.packageId}>
                  <strong>{names.get(item.analystUserId ?? "") ?? "Unassigned"}</strong>
                  <span>{item.title}</span>
                  <small>
                    {item.reference}
                    {item.fromTicket ? " · dated from the request" : ""}
                  </small>
                </li>
              ))}
            </ul>
          </li>
        ))}
      </ul>
    </div>
  );
}

function formatDay(value: string) {
  return new Intl.DateTimeFormat("en-GB", {
    weekday: "short",
    day: "numeric",
    month: "short",
  }).format(new Date(`${value}T12:00:00Z`));
}
