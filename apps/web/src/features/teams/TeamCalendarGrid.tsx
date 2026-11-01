import { ACTIVITY_LABELS, inMonth } from "./team-calendar-model";
import { withinRange, type AssignedDay } from "./team-calendar-assignments";
import type { CalendarEntry } from "../../lib/api-client/teams";

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const MAX_CHIPS_PER_DAY = 3;

type TeamCalendarGridProps = {
  assignments: Map<string, AssignedDay[]>;
  canRemove: (entry: CalendarEntry) => boolean;
  cursor: { year: number; month: number };
  entries: Map<string, CalendarEntry[]>;
  from: string;
  grid: string[][];
  memberName: (userId: string | null) => string;
  onPickDay: (day: string) => void;
  onRemoveEntry: (entry: CalendarEntry) => void;
  removing: boolean;
  to: string;
  today: string;
};

export function TeamCalendarGrid({
  assignments,
  canRemove,
  cursor,
  entries,
  from,
  grid,
  memberName,
  onPickDay,
  onRemoveEntry,
  removing,
  to,
  today,
}: TeamCalendarGridProps) {
  return (
    <div aria-label="Month calendar" className="cal-grid">
      {WEEKDAYS.map((weekday) => (
        <span className="cal-grid__weekday" key={weekday}>
          {weekday}
        </span>
      ))}
      {grid.flat().map((day) => {
        const dayEntries = entries.get(day) ?? [];
        const dayAssignments = assignments.get(day) ?? [];
        const shown = dayEntries.slice(0, MAX_CHIPS_PER_DAY);
        const classes = [
          "cal-day",
          !inMonth(day, cursor.year, cursor.month) ? "cal-day--outside" : "",
          day === today ? "cal-day--today" : "",
          withinRange(day, from, to) ? "cal-day--selected" : "",
        ]
          .filter(Boolean)
          .join(" ");
        return (
          <div className={classes} key={day}>
            {/* The pick target spans the cell width: the bare number was a
                small target and hid that the calendar sets the dates at all. */}
            <button
              aria-label={`Plan ${day}`}
              className="cal-day__pick"
              onClick={() => onPickDay(day)}
              type="button"
            >
              <span className="cal-day__number">{Number(day.slice(8, 10))}</span>
            </button>
            <div className="cal-day__entries">
              {shown.map((entry) => (
                <button
                  aria-label={`Remove entry for ${memberName(entry.userId)} on ${day}`}
                  className={`cal-chip cal-chip--${entry.status}`}
                  disabled={!canRemove(entry) || removing}
                  key={`${entry.id}-${day}`}
                  onClick={() => onRemoveEntry(entry)}
                  title={`${memberName(entry.userId)}: ${ACTIVITY_LABELS[entry.status]}${
                    entry.note ? ` · ${entry.note}` : ""
                  }`}
                  type="button"
                >
                  <span className="cal-chip__dot" aria-hidden="true" />
                  {memberName(entry.userId).split(" ")[0]}
                </button>
              ))}
              {dayAssignments.map((assignment) => (
                <span
                  className="cal-chip cal-chip--assigned"
                  key={`${assignment.packageId}-${day}`}
                  title={
                    `${assignment.reference}: ${assignment.title} · ` +
                    `${memberName(assignment.analystUserId)}` +
                    (assignment.fromTicket ? " · dated from the request" : "")
                  }
                >
                  <span className="cal-chip__dot" aria-hidden="true" />
                  {memberName(assignment.analystUserId).split(" ")[0]}
                  <span className="cal-chip__ref">{assignment.reference}</span>
                </span>
              ))}
              {dayEntries.length > shown.length ? (
                <span className="cal-day__more">+{dayEntries.length - shown.length}</span>
              ) : null}
            </div>
          </div>
        );
      })}
    </div>
  );
}
