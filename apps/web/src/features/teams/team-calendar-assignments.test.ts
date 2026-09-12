import type { TeamTaskBoard } from "../../lib/api-client/team-task-board";
import { assignmentsByDay, selectedRange, withinRange } from "./team-calendar-assignments";

function board(packages: Array<Record<string, unknown>>, targetDate: string | null = null) {
  return {
    cards: [
      {
        reference: "TCK-0001",
        targetDate,
        packages: packages.map((item) => ({
          packageId: "package-1",
          title: "Assess imagery",
          state: "in_progress",
          accountableUserId: "analyst-1",
          dueAt: null,
          ...item,
        })),
      },
    ],
  } as TeamTaskBoard;
}

test("a package is placed on the day it is due", () => {
  const byDay = assignmentsByDay(board([{ dueAt: "2026-08-12T09:00:00Z" }]));

  expect([...byDay.keys()]).toEqual(["2026-08-12"]);
  expect(byDay.get("2026-08-12")?.[0]).toMatchObject({
    title: "Assess imagery",
    analystUserId: "analyst-1",
    fromTicket: false,
  });
});

test("a package without its own date falls back to the ticket target date", () => {
  const byDay = assignmentsByDay(board([{ dueAt: null }], "2026-08-20"));

  expect(byDay.get("2026-08-20")?.[0].fromTicket).toBe(true);
});

test("work with no date at all is left off rather than guessed onto a day", () => {
  expect(assignmentsByDay(board([{ dueAt: null }], null)).size).toBe(0);
});

test("finished work is not shown, because the calendar is about what is still coming", () => {
  const byDay = assignmentsByDay(
    board([
      { packageId: "done", state: "complete", dueAt: "2026-08-12T09:00:00Z" },
      { packageId: "gone", state: "cancelled", dueAt: "2026-08-12T09:00:00Z" },
    ]),
  );

  expect(byDay.size).toBe(0);
});

test("an unusable date is ignored instead of creating a bad day key", () => {
  expect(assignmentsByDay(board([{ dueAt: "not-a-date" }])).size).toBe(0);
});

test("no board yields no assignments", () => {
  expect(assignmentsByDay(undefined).size).toBe(0);
});

test("a range reads the same whichever end was picked first", () => {
  expect(selectedRange("2026-08-10", "2026-08-04")).toEqual({
    from: "2026-08-04",
    to: "2026-08-10",
  });
  expect(selectedRange("2026-08-04", "2026-08-10")).toEqual({
    from: "2026-08-04",
    to: "2026-08-10",
  });
});

test("range membership includes both ends", () => {
  expect(withinRange("2026-08-04", "2026-08-04", "2026-08-06")).toBe(true);
  expect(withinRange("2026-08-06", "2026-08-04", "2026-08-06")).toBe(true);
  expect(withinRange("2026-08-07", "2026-08-04", "2026-08-06")).toBe(false);
});
