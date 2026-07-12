import { entriesByDay, gridRange, inMonth, isBlock, monthGrid } from "./team-calendar-model";
import type { CalendarEntry } from "../../lib/api-client/teams";

function entry(overrides: Partial<CalendarEntry>): CalendarEntry {
  return {
    id: "e1",
    userId: "u1",
    date: "2026-07-10",
    endDate: "2026-07-10",
    status: "leave",
    note: "",
    createdByUserId: null,
    ...overrides,
  };
}

test("month grid covers whole Monday-first weeks around the month", () => {
  // July 2026: 1st is a Wednesday, 31st is a Friday.
  const grid = monthGrid(2026, 6);
  expect(grid[0][0]).toBe("2026-06-29");
  expect(grid.at(-1)?.at(-1)).toBe("2026-08-02");
  expect(grid.every((week) => week.length === 7)).toBe(true);
  expect(gridRange(grid)).toEqual({ from: "2026-06-29", to: "2026-08-02" });
  expect(inMonth("2026-07-15", 2026, 6)).toBe(true);
  expect(inMonth("2026-06-30", 2026, 6)).toBe(false);
});

test("month grid handles a month starting on Monday and February", () => {
  // June 2026 starts on a Monday.
  const june = monthGrid(2026, 5);
  expect(june[0][0]).toBe("2026-06-01");
  // February 2027 (28 days, starts Monday) is exactly four weeks.
  const february = monthGrid(2027, 1);
  expect(february).toHaveLength(4);
  expect(february[0][0]).toBe("2027-02-01");
  expect(february.at(-1)?.at(-1)).toBe("2027-02-28");
});

test("block entries expand to every covered day", () => {
  const block = entry({ id: "b1", date: "2026-07-10", endDate: "2026-07-13" });
  const single = entry({ id: "s1", date: "2026-07-11", endDate: "2026-07-11", userId: "u2" });
  const byDay = entriesByDay([block, single]);

  expect(byDay.get("2026-07-10")?.map((item) => item.id)).toEqual(["b1"]);
  expect(byDay.get("2026-07-11")?.map((item) => item.id)).toEqual(["b1", "s1"]);
  expect(byDay.get("2026-07-13")?.map((item) => item.id)).toEqual(["b1"]);
  expect(byDay.get("2026-07-14")).toBeUndefined();
  expect(isBlock(block)).toBe(true);
  expect(isBlock(single)).toBe(false);
});

test("an empty endDate is treated as a single day", () => {
  const legacy = entry({ endDate: "" });
  expect(entriesByDay([legacy]).get("2026-07-10")).toHaveLength(1);
  expect(entriesByDay([legacy]).size).toBe(1);
  expect(isBlock(legacy)).toBe(false);
});
