import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarPlus, Trash2 } from "lucide-react";
import { useState } from "react";

import {
  addCalendarEntry,
  listTeamCalendar,
  removeCalendarEntry,
  type CalendarEntry,
  type OrgTeam,
} from "../../lib/api-client/teams";
import { useActionError } from "../../lib/mutations/action-error";

const STATUS_LABELS: Record<CalendarEntry["status"], string> = {
  available: "Available",
  on_task: "On task",
  leave: "On leave",
};

function isoDate(offsetDays: number) {
  const date = new Date();
  date.setDate(date.getDate() + offsetDays);
  return date.toISOString().slice(0, 10);
}

type TeamCalendarPanelProps = {
  csrfToken: string;
  currentUserId: string;
  team: OrgTeam;
};

export function TeamCalendarPanel({ csrfToken, currentUserId, team }: TeamCalendarPanelProps) {
  const queryClient = useQueryClient();
  const [entryDate, setEntryDate] = useState(isoDate(0));
  const [status, setStatus] = useState<CalendarEntry["status"]>("available");
  const [memberId, setMemberId] = useState(currentUserId);
  const [note, setNote] = useState("");
  const { actionError, clearActionError, failActionWith } = useActionError();
  const windowFrom = isoDate(0);
  const windowTo = isoDate(14);
  const calendarKey = ["team-calendar", team.id, windowFrom, windowTo];
  const calendarQuery = useQuery({
    queryKey: calendarKey,
    queryFn: () => listTeamCalendar(team.id, windowFrom, windowTo),
  });
  const isManager = team.members.some(
    (member) => member.userId === currentUserId && member.isManager,
  );
  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: calendarKey });
    void queryClient.invalidateQueries({ queryKey: ["team-availability", team.id] });
  };
  const addMutation = useMutation({
    mutationFn: () =>
      addCalendarEntry(
        team.id,
        { userId: memberId, date: entryDate, status, note: note.trim() || undefined },
        csrfToken,
      ),
    onError: failActionWith("The calendar entry could not be added."),
    onMutate: clearActionError,
    onSuccess: () => {
      setNote("");
      refresh();
    },
  });
  const removeMutation = useMutation({
    mutationFn: (entryId: string) => removeCalendarEntry(team.id, entryId, csrfToken),
    onError: failActionWith("The calendar entry could not be removed."),
    onMutate: clearActionError,
    onSuccess: refresh,
  });
  const memberName = (userId: string) =>
    team.members.find((member) => member.userId === userId)?.displayName ?? "Former member";
  const canRemove = (entry: CalendarEntry) => isManager || entry.userId === currentUserId;

  return (
    <section className="surface team-calendar" aria-label="Team calendar">
      <h2>Calendar (next two weeks)</h2>
      {calendarQuery.isError ? <p role="alert">The calendar could not be loaded.</p> : null}
      <ul className="team-calendar__list">
        {(calendarQuery.data?.entries ?? []).map((entry) => (
          <li key={entry.id}>
            <span>{entry.date}</span>
            <strong>{memberName(entry.userId)}</strong>
            <span className={`team-calendar__status team-calendar__status--${entry.status}`}>
              {STATUS_LABELS[entry.status]}
            </span>
            {entry.note ? <small>{entry.note}</small> : null}
            {canRemove(entry) ? (
              <button
                aria-label={`Remove entry for ${memberName(entry.userId)} on ${entry.date}`}
                disabled={removeMutation.isPending}
                onClick={() => removeMutation.mutate(entry.id)}
                type="button"
              >
                <Trash2 aria-hidden="true" size={14} />
              </button>
            ) : null}
          </li>
        ))}
      </ul>
      <form
        className="team-calendar__add"
        onSubmit={(event) => {
          event.preventDefault();
          addMutation.mutate();
        }}
      >
        {isManager ? (
          <label>
            Member
            <select onChange={(event) => setMemberId(event.target.value)} value={memberId}>
              {team.members.map((member) => (
                <option key={member.userId} value={member.userId}>
                  {member.displayName}
                </option>
              ))}
            </select>
          </label>
        ) : null}
        <label>
          Date
          <input
            onChange={(event) => setEntryDate(event.target.value)}
            type="date"
            value={entryDate}
          />
        </label>
        <label>
          Status
          <select
            onChange={(event) => setStatus(event.target.value as CalendarEntry["status"])}
            value={status}
          >
            {Object.entries(STATUS_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Note
          <input maxLength={280} onChange={(event) => setNote(event.target.value)} value={note} />
        </label>
        <button disabled={addMutation.isPending} type="submit">
          <CalendarPlus aria-hidden="true" size={16} />
          Add entry
        </button>
      </form>
      {actionError ? (
        <p className="auth-error" role="alert">
          {actionError}
        </p>
      ) : null}
    </section>
  );
}
