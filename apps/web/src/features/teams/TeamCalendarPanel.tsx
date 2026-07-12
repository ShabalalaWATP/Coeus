import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarPlus, ChevronLeft, ChevronRight, Trash2 } from "lucide-react";
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

function isoDate(offsetDays: number, base = new Date()) {
  const date = new Date(base);
  date.setDate(date.getDate() + offsetDays);
  return [date.getFullYear(), date.getMonth() + 1, date.getDate()]
    .map((part, index) => String(part).padStart(index === 0 ? 4 : 2, "0"))
    .join("-");
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
  const effective = new Map<string, CalendarEntry>();
  for (const entry of entries) {
    const key = `${entry.date}:${entry.userId}`;
    effective.set(key, entry);
  }
  const groups = new Map<string, CalendarEntry[]>();
  for (const entry of effective.values()) {
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
  const [windowOffset, setWindowOffset] = useState(0);
  const windowFrom = isoDate(windowOffset);
  const windowTo = isoDate(windowOffset + 14);
  const today = isoDate(0);
  const [entryDate, setEntryDate] = useState(windowFrom);
  const [status, setStatus] = useState<CalendarEntry["status"]>("available");
  const [memberId, setMemberId] = useState(currentUserId);
  const [note, setNote] = useState("");
  const { actionError, clearActionError, failActionWith } = useActionError();
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
  useEffect(() => setEntryDate(windowFrom), [windowFrom]);
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
      <h2>{windowOffset === 0 ? "Calendar (next two weeks)" : "Calendar (selected fortnight)"}</h2>
      <nav aria-label="Calendar period" className="team-calendar__navigation">
        <button onClick={() => setWindowOffset((current) => current - 14)} type="button">
          <ChevronLeft aria-hidden="true" size={16} /> Previous fortnight
        </button>
        <button disabled={windowOffset === 0} onClick={() => setWindowOffset(0)} type="button">
          Today
        </button>
        <button onClick={() => setWindowOffset((current) => current + 14)} type="button">
          Next fortnight <ChevronRight aria-hidden="true" size={16} />
        </button>
      </nav>
      {calendarQuery.isError ? <p role="alert">The calendar could not be loaded.</p> : null}
      {calendarQuery.isLoading ? <p role="status">Loading team calendar…</p> : null}
      {calendarQuery.isSuccess && calendarQuery.data.entries.length === 0 ? (
        <p className="team-calendar__empty">No entries in this fortnight.</p>
      ) : null}
      {!calendarQuery.isLoading && !calendarQuery.isError
        ? calendarDays(windowFrom, calendarQuery.data?.entries ?? []).map(([date, entries]) => (
            <div
              className={`team-calendar__day${date === today ? " team-calendar__day--today" : ""}`}
              key={date}
            >
              <header>
                <h3>
                  {dayLabel(date)}
                  {date === today ? <span className="team-calendar__today">Today</span> : null}
                </h3>
                <small>{daySummary(entries)}</small>
              </header>
              <ul className="team-calendar__list">
                {entries.length === 0 ? (
                  <li className="team-calendar__free-day">No entries</li>
                ) : null}
                {entries.map((entry) => (
                  <li key={entry.id}>
                    <strong>{memberName(entry.userId)}</strong>
                    <span
                      className={`team-calendar__status team-calendar__status--${entry.status}`}
                    >
                      {STATUS_LABELS[entry.status]}
                    </span>
                    {entry.note ? <small>{entry.note}</small> : null}
                    {canRemove(entry) ? (
                      <button
                        aria-label={`Remove entry for ${memberName(entry.userId)} on ${entry.date}`}
                        disabled={removeMutation.isPending}
                        onClick={() => {
                          if (
                            window.confirm(
                              `Remove this calendar entry for ${memberName(entry.userId)}?`,
                            )
                          ) {
                            removeMutation.mutate(entry.id);
                          }
                        }}
                        type="button"
                      >
                        <Trash2 aria-hidden="true" size={14} />
                      </button>
                    ) : null}
                  </li>
                ))}
              </ul>
            </div>
          ))
        : null}
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
