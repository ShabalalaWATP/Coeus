import { CalendarPlus } from "lucide-react";
import { useEffect, useState } from "react";

import type {
  CalendarActivity,
  CalendarRecurrence,
  WorkforceCalendarEvent,
} from "../../lib/api-client/workforce-calendar";

export type CalendarEventDraft = {
  activity: CalendarActivity;
  allDay: boolean;
  availability: "available" | "partial" | "unavailable";
  endDate: string;
  note: string;
  privacy: "private" | "team_summary" | "team_detail";
  recurrence: CalendarRecurrence | null;
  startDate: string;
  startTime: string;
  endTime: string;
};

const ACTIVITIES: Record<CalendarActivity, string> = {
  leave: "Leave",
  training: "Training",
  duty: "Duty",
  appointment: "Appointment",
  meeting: "Meeting",
  task: "Task",
  other: "Other",
};
const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

function dateInput(date = new Date()) {
  const offset = date.getTimezoneOffset() * 60_000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 10);
}

type Props = {
  actionError: string | null;
  disabled: boolean;
  editing: WorkforceCalendarEvent | null;
  onDiscard: () => void;
  onSubmit: (draft: CalendarEventDraft) => void;
  pending: boolean;
  editScope?: "occurrence" | "future" | "series";
};

export function CalendarEventForm(props: Props) {
  const today = dateInput();
  const [startDate, setStartDate] = useState(today);
  const [endDate, setEndDate] = useState(today);
  const [activity, setActivity] = useState<CalendarActivity>("leave");
  const [availability, setAvailability] =
    useState<CalendarEventDraft["availability"]>("unavailable");
  const [privacy, setPrivacy] = useState<CalendarEventDraft["privacy"]>("team_summary");
  const [note, setNote] = useState("");
  const [allDay, setAllDay] = useState(true);
  const [startTime, setStartTime] = useState("09:00");
  const [endTime, setEndTime] = useState("10:00");
  const [frequency, setFrequency] = useState<"none" | "daily" | "weekly">("none");
  const [interval, setInterval] = useState(1);
  const [until, setUntil] = useState(today);
  const [weekdays, setWeekdays] = useState<number[]>([
    new Date(`${today}T12:00:00`).getDay() === 0 ? 6 : new Date(`${today}T12:00:00`).getDay() - 1,
  ]);

  useEffect(() => {
    if (!props.editing) return;
    const event = props.editing;
    const timing =
      props.editScope === "series" ? (event.seriesTiming ?? event.timing) : event.timing;
    const first = timing.allDayStart ?? timing.startsAt?.slice(0, 10) ?? today;
    const final = timing.allDayEnd
      ? previousDay(timing.allDayEnd)
      : localDate(timing.endsAt, first);
    setStartDate(first);
    setEndDate(final);
    setAllDay(Boolean(timing.allDayStart));
    setStartTime(localTime(timing.startsAt, "09:00"));
    setEndTime(localTime(timing.endsAt, "10:00"));
    setActivity(event.activity);
    setAvailability(event.availability);
    setPrivacy(event.privacy);
    setNote(event.note);
    setFrequency(event.recurrence?.frequency ?? "none");
    setInterval(event.recurrence?.interval ?? 1);
    setUntil(event.recurrence?.until ?? first);
    setWeekdays(event.recurrence?.weekdays ?? [weekday(first)]);
  }, [props.editScope, props.editing, today]);

  const submit = () =>
    props.onSubmit({
      activity,
      allDay,
      availability,
      endDate,
      note: note.trim(),
      privacy,
      startDate,
      startTime,
      endTime,
      recurrence:
        frequency === "none"
          ? null
          : {
              frequency,
              interval,
              until,
              weekdays: frequency === "weekly" ? [...weekdays].sort() : [],
            },
    });
  return (
    <form
      className="surface calendar-form"
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
    >
      <h2>
        <CalendarPlus aria-hidden="true" size={18} />{" "}
        {props.editing ? `Edit ${scopeLabel(props.editScope)}` : "Add activity"}
      </h2>
      <label>
        Activity
        <select
          value={activity}
          onChange={(event) => setActivity(event.target.value as CalendarActivity)}
        >
          {Object.entries(ACTIVITIES).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </label>
      <div className="calendar-form__dates">
        <label>
          First day
          <input
            min={today}
            onChange={(event) => {
              setStartDate(event.target.value);
              if (endDate < event.target.value) setEndDate(event.target.value);
              if (until < event.target.value) setUntil(event.target.value);
            }}
            type="date"
            value={startDate}
          />
        </label>
        <label>
          Last day
          <input
            min={startDate}
            onChange={(event) => setEndDate(event.target.value)}
            type="date"
            value={endDate}
          />
        </label>
      </div>
      <label>
        <input
          checked={allDay}
          onChange={(event) => setAllDay(event.target.checked)}
          type="checkbox"
        />
        All day
      </label>
      {!allDay ? (
        <div className="calendar-form__dates">
          <label>
            Start time
            <input
              type="time"
              value={startTime}
              onChange={(event) => setStartTime(event.target.value)}
            />
          </label>
          <label>
            End time
            <input
              type="time"
              value={endTime}
              onChange={(event) => setEndTime(event.target.value)}
            />
          </label>
        </div>
      ) : null}
      <label>
        Availability
        <select
          value={availability}
          onChange={(event) =>
            setAvailability(event.target.value as CalendarEventDraft["availability"])
          }
        >
          <option value="unavailable">Unavailable</option>
          <option value="partial">Partly available</option>
          <option value="available">Available</option>
        </select>
      </label>
      <label>
        Team visibility
        <select
          value={privacy}
          onChange={(event) => setPrivacy(event.target.value as CalendarEventDraft["privacy"])}
        >
          <option value="team_summary">Availability only</option>
          <option value="team_detail">Activity and availability</option>
          <option value="private">Private</option>
        </select>
      </label>
      <fieldset>
        <legend>Repeat</legend>
        <label>
          Frequency
          <select
            value={frequency}
            onChange={(event) => setFrequency(event.target.value as typeof frequency)}
          >
            <option value="none">Does not repeat</option>
            <option value="daily">Daily</option>
            <option value="weekly">Weekly</option>
          </select>
        </label>
        {frequency !== "none" ? (
          <>
            <label>
              Repeat every
              <input
                aria-label="Repeat interval"
                min={1}
                max={52}
                type="number"
                value={interval}
                onChange={(event) => setInterval(Number(event.target.value))}
              />
            </label>
            <label>
              Repeat until
              <input
                min={startDate}
                max={maxUntil(startDate)}
                type="date"
                value={until}
                onChange={(event) => setUntil(event.target.value)}
              />
            </label>
          </>
        ) : null}
        {frequency === "weekly" ? (
          <fieldset>
            <legend>Repeat on</legend>
            {WEEKDAYS.map((label, value) => (
              <label key={label}>
                <input
                  checked={weekdays.includes(value)}
                  onChange={() =>
                    setWeekdays((current) =>
                      current.includes(value)
                        ? current.filter((day) => day !== value)
                        : [...current, value],
                    )
                  }
                  type="checkbox"
                />
                {label}
              </label>
            ))}
          </fieldset>
        ) : null}
      </fieldset>
      <label>
        Note (optional)
        <textarea maxLength={280} onChange={(event) => setNote(event.target.value)} value={note} />
      </label>
      {props.actionError ? (
        <p className="form-error" role="alert">
          {props.actionError}
        </p>
      ) : null}
      <button
        className="button"
        disabled={
          props.disabled ||
          props.pending ||
          (frequency === "weekly" && weekdays.length === 0) ||
          (!allDay && startDate === endDate && startTime >= endTime)
        }
        type="submit"
      >
        {props.pending
          ? "Saving…"
          : props.editing
            ? `Save ${scopeLabel(props.editScope)}`
            : "Add to calendar"}
      </button>
      {props.editing ? (
        <button className="button secondary" onClick={props.onDiscard} type="button">
          Discard changes
        </button>
      ) : null}
    </form>
  );
}

function weekday(value: string) {
  const day = new Date(`${value}T12:00:00Z`).getUTCDay();
  return day === 0 ? 6 : day - 1;
}
function previousDay(value: string) {
  const day = new Date(`${value}T12:00:00Z`);
  day.setUTCDate(day.getUTCDate() - 1);
  return day.toISOString().slice(0, 10);
}
function maxUntil(value: string) {
  if (!value) return undefined;
  const day = new Date(`${value}T12:00:00Z`);
  day.setUTCDate(day.getUTCDate() + 366);
  return day.toISOString().slice(0, 10);
}

function localTime(value: string | null | undefined, fallback: string) {
  if (!value) return fallback;
  return new Intl.DateTimeFormat("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(value));
}

function localDate(value: string | null | undefined, fallback: string) {
  if (!value) return fallback;
  const offset = new Date(value).getTimezoneOffset() * 60_000;
  return new Date(new Date(value).getTime() - offset).toISOString().slice(0, 10);
}

function scopeLabel(scope: Props["editScope"]) {
  if (scope === "occurrence") return "this occurrence";
  if (scope === "future") return "this and future occurrences";
  return "whole series";
}
