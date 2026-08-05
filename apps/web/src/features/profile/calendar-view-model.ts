import type { CalendarViewMode } from "./CalendarViewModePicker";

export function filterCalendarView<
  T extends { timing: { allDayStart: string | null; startsAt: string | null } },
>(events: T[], mode: CalendarViewMode, now = new Date()): T[] {
  if (mode === "agenda") return events;
  const start = new Date(now);
  start.setHours(0, 0, 0, 0);
  const end = new Date(start);
  if (mode === "week") end.setDate(end.getDate() + 7);
  else {
    start.setDate(1);
    end.setMonth(end.getMonth() + 1, 1);
  }
  return events.filter((event) => {
    const raw = event.timing.allDayStart ?? event.timing.startsAt;
    if (!raw) return false;
    const date = new Date(event.timing.allDayStart ? `${raw}T00:00:00` : raw);
    return date >= start && date < end;
  });
}
