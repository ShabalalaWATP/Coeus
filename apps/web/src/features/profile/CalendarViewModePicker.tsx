import { useRef } from "react";

export type CalendarViewMode = "month" | "week" | "agenda";

const MODES: CalendarViewMode[] = ["month", "week", "agenda"];

type Props = {
  mode: CalendarViewMode;
  onChange: (mode: CalendarViewMode) => void;
};

export function CalendarViewModePicker({ mode, onChange }: Props) {
  const buttons = useRef<Array<HTMLButtonElement | null>>([]);
  return (
    <div
      aria-label="Calendar view"
      className="calendar-view-picker"
      onKeyDown={(event) => {
        if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
        event.preventDefault();
        const offset = event.key === "ArrowRight" ? 1 : -1;
        const next = (MODES.indexOf(mode) + offset + MODES.length) % MODES.length;
        onChange(MODES[next]);
        buttons.current[next]?.focus();
      }}
      role="tablist"
    >
      {MODES.map((value, index) => (
        <button
          aria-controls="calendar-activity-panel"
          aria-selected={mode === value}
          key={value}
          onClick={() => onChange(value)}
          ref={(node) => {
            buttons.current[index] = node;
          }}
          role="tab"
          tabIndex={mode === value ? 0 : -1}
          type="button"
        >
          {value[0].toUpperCase() + value.slice(1)}
        </button>
      ))}
    </div>
  );
}
