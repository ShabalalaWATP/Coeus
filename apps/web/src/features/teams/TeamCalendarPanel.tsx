import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarPlus, ChevronLeft, ChevronRight } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { TeamCalendarGrid } from "./TeamCalendarGrid";
import { assignmentsByDay, selectedRange } from "./team-calendar-assignments";
import {
  ACTIVITY_LABELS,
  entriesByDay,
  gridRange,
  isBlock,
  monthGrid,
  monthTitle,
  todayIso,
} from "./team-calendar-model";
import { getTeamTaskBoard } from "../../lib/api-client/team-task-board";
import {
  addCalendarEntry,
  listTeamCalendar,
  removeCalendarEntry,
  type CalendarActivity,
  type CalendarEntry,
  type OrgTeam,
} from "../../lib/api-client/teams";
import { queryKeys } from "../../lib/query-keys";
import { useActionError } from "../../lib/mutations/action-error";

type TeamCalendarPanelProps = {
  csrfToken: string;
  currentUserId: string;
  team: OrgTeam;
};

export function TeamCalendarPanel({ csrfToken, currentUserId, team }: TeamCalendarPanelProps) {
  const queryClient = useQueryClient();
  const now = new Date();
  const [cursor, setCursor] = useState({ year: now.getFullYear(), month: now.getMonth() });
  const today = todayIso();
  const [fromDate, setFromDate] = useState(today);
  const [toDate, setToDate] = useState(today);
  const [activity, setActivity] = useState<CalendarActivity>("leave");
  const [memberId, setMemberId] = useState(currentUserId);
  const [note, setNote] = useState("");
  const { actionError, clearActionError, failActionWith } = useActionError();
  const grid = useMemo(() => monthGrid(cursor.year, cursor.month), [cursor]);
  const range = gridRange(grid);
  const calendarKey = ["team-calendar", team.id, range.from, range.to];
  const calendarQuery = useQuery({
    queryKey: calendarKey,
    queryFn: () => listTeamCalendar(team.id, range.from, range.to),
  });
  const byDay = useMemo(
    () => entriesByDay(calendarQuery.data?.entries ?? []),
    [calendarQuery.data?.entries],
  );
  // Assigned work is read-only context here, so a failure to load it must not
  // stop anyone blocking out dates.
  const boardQuery = useQuery({
    queryKey: ["team-calendar-board", team.id],
    queryFn: () => getTeamTaskBoard(team.id, { includeCompleted: false }),
    retry: false,
  });
  const assignments = useMemo(() => assignmentsByDay(boardQuery.data), [boardQuery.data]);
  const [anchor, setAnchor] = useState<string | null>(null);
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
    void queryClient.invalidateQueries({ queryKey: ["team-calendar", team.id] });
    void queryClient.invalidateQueries({
      queryKey: queryKeys.teams.availabilityPrefix(team.id),
    });
  };
  const addMutation = useMutation({
    mutationFn: () =>
      addCalendarEntry(
        team.id,
        {
          userId: memberId,
          date: fromDate,
          ...(toDate && toDate !== fromDate ? { endDate: toDate } : {}),
          status: activity,
          note: note.trim() || undefined,
        },
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
  // Assigned work can name nobody, so this also answers for an absent owner.
  const memberName = (userId: string | null) =>
    userId === null
      ? "Unassigned"
      : (team.members.find((member) => member.userId === userId)?.displayName ?? "Former member");
  const canRemove = (entry: CalendarEntry) => isManager || entry.userId === currentUserId;
  const moveMonth = (delta: number) => {
    setCursor(({ year, month }) => {
      const next = new Date(year, month + delta, 1);
      return { year: next.getFullYear(), month: next.getMonth() };
    });
  };
  // First click starts a range, second click closes it. Picking either way
  // round works, so a range can be dragged out backwards from its end date.
  const pickDay = (day: string) => {
    if (anchor === null) {
      setAnchor(day);
      setFromDate(day);
      setToDate(day);
      return;
    }
    const range = selectedRange(anchor, day);
    setFromDate(range.from);
    setToDate(range.to);
    setAnchor(null);
  };
  const removeEntry = (entry: CalendarEntry) => {
    const span = isBlock(entry) ? `${entry.date} to ${entry.endDate}` : entry.date;
    if (window.confirm(`Remove ${memberName(entry.userId)}'s entry (${span})?`)) {
      removeMutation.mutate(entry.id);
    }
  };

  return (
    <section className="surface team-calendar" aria-label="Team calendar">
      <header className="team-calendar__header">
        <h2>{monthTitle(cursor.year, cursor.month)}</h2>
        <nav aria-label="Calendar period" className="team-calendar__navigation">
          <button aria-label="Previous month" onClick={() => moveMonth(-1)} type="button">
            <ChevronLeft aria-hidden="true" size={16} />
          </button>
          <button
            onClick={() => setCursor({ year: now.getFullYear(), month: now.getMonth() })}
            type="button"
          >
            Today
          </button>
          <button aria-label="Next month" onClick={() => moveMonth(1)} type="button">
            <ChevronRight aria-hidden="true" size={16} />
          </button>
        </nav>
      </header>
      {calendarQuery.isLoading ? (
        <p role="status">Loading team calendar…</p>
      ) : calendarQuery.isError ? (
        <p role="alert">The calendar could not be loaded.</p>
      ) : (
        <TeamCalendarGrid
          assignments={assignments}
          canRemove={canRemove}
          cursor={cursor}
          entries={byDay}
          from={fromDate}
          grid={grid}
          memberName={memberName}
          onPickDay={pickDay}
          onRemoveEntry={removeEntry}
          removing={removeMutation.isPending}
          to={toDate}
          today={today}
        />
      )}
      <form
        className="team-calendar__add"
        onSubmit={(event) => {
          event.preventDefault();
          addMutation.mutate();
        }}
      >
        <div className="team-calendar__add-intro">
          <span className="team-calendar__add-title">Block out dates</span>
          <p>
            {anchor
              ? "Pick the last day to finish the range, or set the dates below."
              : "Click a day to start a range, or set the dates below."}
          </p>
        </div>
        <p aria-live="polite" className="team-calendar__range">
          {rangeSummary(fromDate, toDate)}
        </p>
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
          Activity
          <select
            onChange={(event) => setActivity(event.target.value as CalendarActivity)}
            value={activity}
          >
            {Object.entries(ACTIVITY_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label className="team-calendar__date">
          From
          <input
            min={today}
            onChange={(event) => {
              setAnchor(null);
              setFromDate(event.target.value);
            }}
            type="date"
            value={fromDate}
          />
        </label>
        <label className="team-calendar__date">
          To
          <input
            min={fromDate}
            onChange={(event) => {
              setAnchor(null);
              setToDate(event.target.value);
            }}
            type="date"
            value={toDate}
          />
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

function rangeSummary(from: string, to: string) {
  const format = (value: string) =>
    new Intl.DateTimeFormat("en-GB", {
      weekday: "short",
      day: "numeric",
      month: "short",
    }).format(new Date(`${value}T00:00:00`));
  if (from === to) return `Selected ${format(from)}`;
  const days = Math.round(
    (new Date(`${to}T00:00:00`).getTime() - new Date(`${from}T00:00:00`).getTime()) / 86_400_000 +
      1,
  );
  return `Selected ${format(from)} to ${format(to)} · ${days} days`;
}
