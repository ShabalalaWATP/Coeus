import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarPlus, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";

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

const DAY_LABEL = new Intl.DateTimeFormat("en-GB", {
  weekday: "short",
  day: "numeric",
  month: "short",
});

function dayLabel(date: string) {
  return DAY_LABEL.format(new Date(`${date}T00:00:00Z`));
}

function groupByDate(entries: CalendarEntry[]): [string, CalendarEntry[]][] {
  const groups = new Map<string, CalendarEntry[]>();
  for (const entry of entries) {
    groups.set(entry.date, [...(groups.get(entry.date) ?? []), entry]);
  }
  return [...groups.entries()].sort(([a], [b]) => a.localeCompare(b));
}

function calendarDays(from: string, entries: CalendarEntry[]): [string, CalendarEntry[]][] {
  const grouped = new Map(groupByDate(entries));
  return Array.from({ length: 15 }, (_, offset) => {
    const date = new Date(`${from}T00:00:00Z`);
    date.setUTCDate(date.getUTCDate() + offset);
    const key = date.toISOString().slice(0, 10);
    return [key, grouped.get(key) ?? []];
  });
}

function daySummary(entries: CalendarEntry[]) {
  const counts = new Map<CalendarEntry["status"], number>();
  for (const entry of entries) {
    counts.set(entry.status, (counts.get(entry.status) ?? 0) + 1);
  }
  return [...counts.entries()]
    .map(([status, count]) => `${count} ${STATUS_LABELS[status].toLowerCase()}`)
    .join(", ");
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
  useEffect(() => {
    const validMember = team.members.some((member) => member.userId === currentUserId)
      ? currentUserId
      : (team.members[0]?.userId ?? "");
    setMemberId(validMember);
  }, [currentUserId, team.id, team.members]);
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
      {calendarQuery.isSuccess && calendarQuery.data.entries.length === 0 ? (
        <p className="team-calendar__empty">No entries in the next two weeks.</p>
      ) : null}
      {calendarDays(windowFrom, calendarQuery.data?.entries ?? []).map(([date, entries]) => (
        <div
          className={`team-calendar__day${date === windowFrom ? " team-calendar__day--today" : ""}`}
          key={date}
        >
          <header>
            <h3>
              {dayLabel(date)}
              {date === windowFrom ? <span className="team-calendar__today">Today</span> : null}
            </h3>
            <small>{daySummary(entries)}</small>
          </header>
          <ul className="team-calendar__list">
            {entries.length === 0 ? <li className="team-calendar__free-day">No entries</li> : null}
            {entries.map((entry) => (
              <li key={entry.id}>
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
        </div>
      ))}
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
            min={windowFrom}
            max={windowTo}
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
