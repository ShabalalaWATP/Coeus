import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";

import { CalendarViewModePicker, type CalendarViewMode } from "./CalendarViewModePicker";
import { filterCalendarView } from "./calendar-view-model";

function Harness() {
  const [mode, setMode] = useState<CalendarViewMode>("agenda");
  return <CalendarViewModePicker mode={mode} onChange={setMode} />;
}

test("switches canonical views by pointer and keyboard", () => {
  render(<Harness />);
  fireEvent.click(screen.getByRole("tab", { name: "Month" }));
  expect(screen.getByRole("tab", { name: "Month" })).toHaveAttribute("aria-selected", "true");
  fireEvent.keyDown(screen.getByRole("tablist"), { key: "ArrowRight" });
  expect(screen.getByRole("tab", { name: "Week" })).toHaveFocus();
  fireEvent.keyDown(screen.getByRole("tablist"), { key: "ArrowLeft" });
  expect(screen.getByRole("tab", { name: "Month" })).toHaveFocus();
});

test("filters week and month modes at exact boundaries", () => {
  const now = new Date("2026-08-04T09:00:00Z");
  const event = (day: string) => ({ timing: { allDayStart: day, startsAt: null } });
  const events = [
    event("2026-08-03"),
    event("2026-08-04"),
    event("2026-08-10"),
    event("2026-09-01"),
  ];
  expect(filterCalendarView(events, "agenda", now)).toHaveLength(4);
  expect(filterCalendarView(events, "week", now)).toHaveLength(2);
  expect(filterCalendarView(events, "month", now)).toHaveLength(3);
  expect(
    filterCalendarView([{ timing: { allDayStart: null, startsAt: null } }], "week", now),
  ).toEqual([]);
});
