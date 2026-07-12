import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarPlus, ChevronLeft, ChevronRight } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import {
  ACTIVITY_LABELS,
  entriesByDay,
  gridRange,
  inMonth,
  isBlock,
  monthGrid,
  monthTitle,
  todayIso,
} from "./team-calendar-model";
import {
  addCalendarEntry,
  listTeamCalendar,
  removeCalendarEntry,
  type CalendarActivity,
  type CalendarEntry,
  type OrgTeam,
} from "../../lib/api-client/teams";
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
    void queryClient.invalidateQueries({ queryKey: ["team-availability", team.id] });
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
  const memberName = (userId: string) =>
    team.members.find((member) => member.userId === userId)?.displayName ?? "Former member";
  const canRemove = (entry: CalendarEntry) => isManager || entry.userId === currentUserId;
  const moveMonth = (delta: number) => {
    setCursor(({ year, month }) => {
      const next = new Date(year, month + delta, 1);
      return { year: next.getFullYear(), month: next.getMonth() };
    });
  };
  const pickDay = (day: string) => {
    setFromDate(day);
    setToDate(day);
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
      {calendarQuery.isError ? (
        <p role="alert">The calendar could not be loaded.</p>
      ) : (
        <div aria-label="Month grid" className="cal-grid" role="grid">
          {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((weekday) => (
            <span className="cal-grid__weekday" key={weekday} role="columnheader">
              {weekday}
            </span>
          ))}
          {grid.flat().map((day) => {
            const entries = byDay.get(day) ?? [];
            const outside = !inMonth(day, cursor.year, cursor.month);
            const shown = entries.slice(0, 3);
            return (
              <div
                className={`cal-day${outside ? " cal-day--outside" : ""}${
                  day === today ? " cal-day--today" : ""
                }`}
                key={day}
                role="gridcell"
              >
                <button
                  aria-label={`Plan ${day}`}
                  className="cal-day__number"
                  onClick={() => pickDay(day)}
                  type="button"
                >
                  {Number(day.slice(8, 10))}
                </button>
                <div className="cal-day__entries">
                  {shown.map((entry) => (
                    <button
                      aria-label={`Remove entry for ${memberName(entry.userId)} on ${day}`}
                      className={`cal-chip cal-chip--${entry.status}`}
                      disabled={!canRemove(entry) || removeMutation.isPending}
                      key={`${entry.id}-${day}`}
                      onClick={() => removeEntry(entry)}
                      title={`${memberName(entry.userId)}: ${ACTIVITY_LABELS[entry.status]}${
                        entry.note ? ` · ${entry.note}` : ""
                      }`}
                      type="button"
                    >
                      <span className="cal-chip__dot" aria-hidden="true" />
                      {memberName(entry.userId).split(" ")[0]}
                    </button>
                  ))}
                  {entries.length > shown.length ? (
                    <span className="cal-day__more">+{entries.length - shown.length}</span>
                  ) : null}
                </div>
              </div>
            );
          })}
        </div>
      )}
      <form
        className="team-calendar__add"
        onSubmit={(event) => {
          event.preventDefault();
          addMutation.mutate();
        }}
      >
        <span className="team-calendar__add-title">Block out dates</span>
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
        <label>
          From
          <input
            min={today}
            onChange={(event) => setFromDate(event.target.value)}
            type="date"
            value={fromDate}
          />
        </label>
        <label>
          To
          <input
            min={fromDate}
            onChange={(event) => setToDate(event.target.value)}
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
