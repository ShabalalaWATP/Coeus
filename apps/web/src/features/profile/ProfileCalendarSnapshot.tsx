import { useQuery } from "@tanstack/react-query";
import { CalendarDays } from "lucide-react";
import { Link } from "react-router-dom";

import {
  listMyCalendar,
  type WorkforceCalendarEvent,
} from "../../lib/api-client/workforce-calendar";

function snapshotWindow() {
  const start = new Date();
  const end = new Date(start);
  end.setDate(end.getDate() + 7);
  return { start: start.toISOString(), end: end.toISOString() };
}

function timingLabel(event: WorkforceCalendarEvent) {
  if (event.timing.allDayStart) {
    return new Intl.DateTimeFormat("en-GB", { dateStyle: "medium" }).format(
      new Date(`${event.timing.allDayStart}T12:00:00Z`),
    );
  }
  if (!event.timing.startsAt) return "Date unavailable";
  return new Intl.DateTimeFormat("en-GB", {
    weekday: "short",
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(event.timing.startsAt));
}

export function ProfileCalendarSnapshot() {
  const range = snapshotWindow();
  const calendar = useQuery({
    queryKey: ["workforce-calendar", "snapshot", range.start.slice(0, 10)],
    queryFn: () => listMyCalendar(range.start, range.end),
    retry: false,
  });
  const events = calendar.data?.events ?? [];

  return (
    <section className="profile-panel profile-calendar" aria-labelledby="profile-calendar-title">
      <div className="profile-panel__heading">
        <h3 id="profile-calendar-title">
          <CalendarDays aria-hidden="true" size={15} /> My next 7 days
        </h3>
        <Link className="profile-panel__link" to="/account/calendar">
          Open calendar
        </Link>
      </div>
      {calendar.isLoading ? <p className="profile-muted">Loading your calendar…</p> : null}
      {calendar.isError ? (
        <p className="profile-muted" role="alert">
          Your calendar is not available yet.
        </p>
      ) : null}
      {!calendar.isLoading && !calendar.isError && events.length === 0 ? (
        <p className="profile-muted">Nothing is scheduled for the next seven days.</p>
      ) : null}
      {events.length > 0 ? (
        <ol className="profile-calendar__events">
          {events.slice(0, 5).map((event) => (
            <li key={event.eventId}>
              <span
                className={`profile-calendar__effect profile-calendar__effect--${event.availability}`}
              />
              <span>
                <strong>{event.activity.replace("_", " ")}</strong>
                <small>{timingLabel(event)}</small>
              </span>
            </li>
          ))}
        </ol>
      ) : null}
    </section>
  );
}
