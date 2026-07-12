import type { CalendarActivity, CalendarEntry } from "../../lib/api-client/teams";

export const ACTIVITY_LABELS: Record<CalendarActivity, string> = {
  available: "Available",
  on_task: "On task",
  leave: "On leave",
  course: "Course",
  duty: "Duty travel",
  appointment: "Appointment",
  other: "Other",
};

// Safety cap when expanding a block entry into days (matches the API's
// 62-day calendar window).
const MAX_BLOCK_DAYS = 62;

function isoDate(date: Date): string {
  return [
    String(date.getFullYear()).padStart(4, "0"),
    String(date.getMonth() + 1).padStart(2, "0"),
    String(date.getDate()).padStart(2, "0"),
  ].join("-");
}

export function todayIso(): string {
  return isoDate(new Date());
}

export function monthTitle(year: number, month: number): string {
  return new Intl.DateTimeFormat("en-GB", { month: "long", year: "numeric" }).format(
    new Date(year, month, 1),
  );
}

/** Monday-first month grid: whole weeks covering the given month. */
export function monthGrid(year: number, month: number): string[][] {
  const first = new Date(year, month, 1);
  const last = new Date(year, month + 1, 0);
  // getDay(): Sunday 0 ... Saturday 6; normalise to Monday-first offsets.
  const start = new Date(first);
  start.setDate(first.getDate() - ((first.getDay() + 6) % 7));
  const end = new Date(last);
  end.setDate(last.getDate() + (6 - ((last.getDay() + 6) % 7)));
  const weeks: string[][] = [];
  const cursor = new Date(start);
  while (cursor <= end) {
    const week: string[] = [];
    for (let day = 0; day < 7; day += 1) {
      week.push(isoDate(cursor));
      cursor.setDate(cursor.getDate() + 1);
    }
    weeks.push(week);
  }
  return weeks;
}

export function gridRange(grid: string[][]): { from: string; to: string } {
  const days = grid.flat();
  return { from: days[0], to: days[days.length - 1] };
}

export function inMonth(day: string, year: number, month: number): boolean {
  const prefix = `${String(year).padStart(4, "0")}-${String(month + 1).padStart(2, "0")}-`;
  return day.startsWith(prefix);
}

/** Expand block entries so each covered day lists the entry. */
export function entriesByDay(entries: CalendarEntry[]): Map<string, CalendarEntry[]> {
  const byDay = new Map<string, CalendarEntry[]>();
  for (const entry of entries) {
    const start = new Date(`${entry.date}T00:00:00`);
    const end = new Date(`${entry.endDate || entry.date}T00:00:00`);
    const cursor = new Date(start);
    for (let step = 0; cursor <= end && step < MAX_BLOCK_DAYS; step += 1) {
      const key = isoDate(cursor);
      byDay.set(key, [...(byDay.get(key) ?? []), entry]);
      cursor.setDate(cursor.getDate() + 1);
    }
  }
  return byDay;
}

export function isBlock(entry: CalendarEntry): boolean {
  return entry.endDate !== "" && entry.endDate !== entry.date;
}
