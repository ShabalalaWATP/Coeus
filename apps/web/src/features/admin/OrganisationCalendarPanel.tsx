import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarDays, Eye, EyeOff } from "lucide-react";
import { useMemo, useState } from "react";

import { ErrorState, LoadingState } from "../../components/ui/PageState";
import {
  executeCalendarMutation,
  listUnitCalendar,
  type CalendarActivity,
} from "../../lib/api-client/workforce-calendar";
import { useActionError } from "../../lib/mutations/action-error";

type Props = {
  unit: { id: string; timeZone?: string };
  allowDescendants?: boolean;
  allowDetail?: boolean;
  csrfToken?: string;
  currentUserId?: string;
  managementGrantId?: string | null;
};

function projectionWindow() {
  const start = new Date();
  const end = new Date(start);
  end.setUTCDate(end.getUTCDate() + 14);
  return { start: start.toISOString(), end: end.toISOString() };
}

export function OrganisationCalendarPanel({
  unit,
  allowDescendants = true,
  allowDetail = true,
  csrfToken,
  currentUserId,
  managementGrantId,
}: Props) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [includeDescendants, setIncludeDescendants] = useState(false);
  const [view, setView] = useState<"availability" | "detail">("availability");
  const [activity, setActivity] = useState<CalendarActivity>("meeting");
  const [day, setDay] = useState(new Date().toISOString().slice(0, 10));
  const [note, setNote] = useState("");
  const { actionError, clearActionError, failActionWith } = useActionError();
  const window = useMemo(projectionWindow, []);
  const projection = useQuery({
    enabled: open,
    queryKey: ["organisation-calendar", unit.id, includeDescendants, view, window],
    retry: false,
    queryFn: () =>
      listUnitCalendar(unit.id, window.start, window.end, {
        includeDescendants,
        view,
      }),
  });
  const createTeamEvent = useMutation({
    mutationFn: () => {
      if (!csrfToken || !currentUserId || !managementGrantId) {
        throw new Error("Calendar management authority is unavailable.");
      }
      const end = new Date(`${day}T12:00:00Z`);
      end.setUTCDate(end.getUTCDate() + 1);
      return executeCalendarMutation(
        {
          operation: "create",
          event: {
            eventId: crypto.randomUUID(),
            ownerUserId: currentUserId,
            source: "team",
            activity,
            timing: {
              timeZone: unit.timeZone ?? "Europe/London",
              startsAt: null,
              endsAt: null,
              allDayStart: day,
              allDayEnd: end.toISOString().slice(0, 10),
            },
            availability: "available",
            privacy: "team_detail",
            createdByUserId: currentUserId,
            note: note.trim(),
            recurrence: null,
            managerScopeUnitId: unit.id,
            status: "active",
            version: 1,
            createdAt: null,
            updatedAt: null,
            cancelledAt: null,
          },
          expectedVersion: 0,
          authorisingGrantId: managementGrantId,
          reason: "Create a canonical team calendar event.",
        },
        csrfToken,
      );
    },
    onError: failActionWith("The team calendar event could not be created."),
    onMutate: clearActionError,
    onSuccess: () => {
      setNote("");
      void queryClient.invalidateQueries({ queryKey: ["organisation-calendar", unit.id] });
    },
  });

  return (
    <section className="organisation-calendar" aria-labelledby="organisation-calendar-title">
      <header>
        <div>
          <CalendarDays aria-hidden="true" size={18} />
          <h3 id="organisation-calendar-title">Team calendar</h3>
        </div>
        <p>
          Availability for the next 14 days. Private notes stay hidden unless explicitly shared.
        </p>
        <button aria-expanded={open} onClick={() => setOpen((current) => !current)} type="button">
          {open ? "Close team calendar" : "Open team calendar"}
        </button>
      </header>
      {open ? (
        <div className="organisation-calendar__controls">
          {allowDescendants ? (
            <label>
              <input
                checked={includeDescendants}
                onChange={(event) => setIncludeDescendants(event.target.checked)}
                type="checkbox"
              />
              Include child units
            </label>
          ) : null}
          {allowDetail ? (
            <button
              aria-pressed={view === "detail"}
              onClick={() =>
                setView((current) => (current === "detail" ? "availability" : "detail"))
              }
              type="button"
            >
              {view === "detail" ? (
                <EyeOff aria-hidden="true" size={16} />
              ) : (
                <Eye aria-hidden="true" size={16} />
              )}
              {view === "detail" ? "Use availability view" : "Request detailed view"}
            </button>
          ) : null}
        </div>
      ) : null}
      {open && projection.isLoading ? <LoadingState label="Loading team calendar" /> : null}
      {open && projection.isError ? (
        <ErrorState
          message="This calendar is unavailable or you do not have the required authority."
          onRetry={() => void projection.refetch()}
        />
      ) : null}
      {open && projection.data ? <ProjectionBody projection={projection.data} /> : null}
      {open && managementGrantId && csrfToken && currentUserId ? (
        <form
          className="organisation-calendar__create"
          onSubmit={(event) => {
            event.preventDefault();
            createTeamEvent.mutate();
          }}
        >
          <h4>Add team event</h4>
          <label>
            Activity
            <select
              onChange={(event) => setActivity(event.target.value as CalendarActivity)}
              value={activity}
            >
              <option value="meeting">Meeting</option>
              <option value="training">Training</option>
              <option value="duty">Duty</option>
              <option value="other">Other</option>
            </select>
          </label>
          <label>
            Date
            <input
              onChange={(event) => setDay(event.target.value)}
              required
              type="date"
              value={day}
            />
          </label>
          <label>
            Shared detail
            <input maxLength={280} onChange={(event) => setNote(event.target.value)} value={note} />
          </label>
          <button disabled={createTeamEvent.isPending} type="submit">
            Add team event
          </button>
          {actionError ? <p role="alert">{actionError}</p> : null}
        </form>
      ) : null}
    </section>
  );
}

function ProjectionBody({
  projection,
}: {
  projection: Awaited<ReturnType<typeof listUnitCalendar>>;
}) {
  if (projection.scope === "descendants") {
    return (
      <div className="organisation-calendar__aggregate">
        <p>
          <strong>{projection.memberCount ?? "Fewer than 5"}</strong> people in this view
        </p>
        {projection.suppressed ? (
          <p className="organisation-calendar__privacy">
            Small totals are hidden to protect individual availability.
          </p>
        ) : null}
        <ul aria-label="Daily descendant availability">
          {projection.aggregates.map((cell) => (
            <li key={`${cell.unitId}-${cell.day}`}>
              <time dateTime={cell.day}>{formatDay(cell.day)}</time>
              <span>
                {cell.unavailableCount === null
                  ? "Private"
                  : `${cell.unavailableCount} unavailable`}
              </span>
            </li>
          ))}
        </ul>
      </div>
    );
  }
  if (projection.entries.length === 0) {
    return <p className="organisation-calendar__empty">No availability entries in this period.</p>;
  }
  return (
    <ul className="organisation-calendar__entries" aria-label="Direct team availability">
      {projection.entries.map((entry, index) => (
        <li key={entry.eventId ?? `${entry.unitId}-${index}`}>
          <strong>{entry.ownerUserId ? "Named team member" : "Team member"}</strong>
          <span>{formatAvailability(entry.availability)}</span>
          <small>{formatTiming(entry.timing)}</small>
          {entry.activity ? <small>{entry.activity.replaceAll("_", " ")}</small> : null}
        </li>
      ))}
    </ul>
  );
}

function formatDay(value: string) {
  return new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short" }).format(
    new Date(`${value}T12:00:00Z`),
  );
}

function formatAvailability(value: string) {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function formatTiming(
  timing: Awaited<ReturnType<typeof listUnitCalendar>>["entries"][number]["timing"],
) {
  if (timing.allDayStart) return `${formatDay(timing.allDayStart)} · all day`;
  if (!timing.startsAt) return "Time unavailable";
  return new Intl.DateTimeFormat("en-GB", { dateStyle: "medium", timeStyle: "short" }).format(
    new Date(timing.startsAt),
  );
}
