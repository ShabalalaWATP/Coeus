import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { TeamCalendarGrid } from "./TeamCalendarGrid";
import type { AssignedDay } from "./team-calendar-assignments";
import type { CalendarEntry } from "../../lib/api-client/teams";

const CURSOR = { year: 2026, month: 7 };
const GRID = [["2026-08-03", "2026-08-04", "2026-08-05", "2026-08-06"]];

function assigned(overrides: Partial<AssignedDay> = {}): AssignedDay {
  return {
    packageId: "package-1",
    title: "Assess port imagery",
    reference: "TCK-0042",
    analystUserId: "analyst-1",
    state: "in_progress",
    day: "2026-08-04",
    fromTicket: false,
    ...overrides,
  };
}

function entry(overrides: Partial<CalendarEntry> = {}) {
  return {
    id: "entry-1",
    userId: "analyst-1",
    date: "2026-08-05",
    endDate: "",
    status: "leave",
    note: "",
    ...overrides,
  } as CalendarEntry;
}

function renderGrid(overrides: Partial<Parameters<typeof TeamCalendarGrid>[0]> = {}) {
  const props = {
    assignments: new Map([["2026-08-04", [assigned()]]]),
    canRemove: () => true,
    cursor: CURSOR,
    entries: new Map<string, CalendarEntry[]>(),
    from: "2026-08-03",
    grid: GRID,
    memberName: (userId: string | null) => (userId === null ? "Unassigned" : "Ryan Christie"),
    onPickDay: vi.fn(),
    onRemoveEntry: vi.fn(),
    removing: false,
    to: "2026-08-03",
    today: "2026-08-03",
    ...overrides,
  };
  render(<TeamCalendarGrid {...props} />);
  return props;
}

test("assigned work names the analyst and the request it belongs to", () => {
  renderGrid();

  const chip = screen.getByTitle(/TCK-0042: Assess port imagery/);
  expect(chip).toHaveTextContent("Ryan");
  expect(chip).toHaveTextContent("TCK-0042");
  expect(chip.getAttribute("title")).toContain("Ryan Christie");
});

test("work dated from its request says so, so the day is not read as exact", () => {
  renderGrid({
    assignments: new Map([["2026-08-04", [assigned({ fromTicket: true })]]]),
  });

  expect(screen.getByTitle(/dated from the request/)).toBeVisible();
});

test("unassigned work still appears rather than being hidden", () => {
  renderGrid({
    assignments: new Map([["2026-08-04", [assigned({ analystUserId: null })]]]),
  });

  expect(screen.getByTitle(/TCK-0042/)).toHaveTextContent("Unassigned");
});

test("assigned work is context only and cannot be removed like an entry", () => {
  renderGrid();

  // Availability entries are buttons; assigned work must not be actionable.
  expect(screen.getByTitle(/TCK-0042/).tagName).toBe("SPAN");
});

test("every day is clickable, not just the number", async () => {
  const props = renderGrid();

  await userEvent.click(screen.getByRole("button", { name: "Plan 2026-08-05" }));

  expect(props.onPickDay).toHaveBeenCalledWith("2026-08-05");
});

test("the chosen range is marked across every day it covers", () => {
  renderGrid({ from: "2026-08-04", to: "2026-08-06" });

  const selected = document.querySelectorAll(".cal-day--selected");
  expect(selected).toHaveLength(3);
});

test("availability entries stay removable alongside assigned work", async () => {
  const props = renderGrid({ entries: new Map([["2026-08-05", [entry()]]]) });

  await userEvent.click(
    screen.getByRole("button", { name: "Remove entry for Ryan Christie on 2026-08-05" }),
  );

  expect(props.onRemoveEntry).toHaveBeenCalled();
});
