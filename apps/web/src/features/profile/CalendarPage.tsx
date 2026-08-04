import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Trash2 } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import {
  executeCalendarMutation,
  listMyCommitments,
  listMyCalendar,
  respondToCommitment,
  type CalendarCommitment,
  type CalendarActivity,
  type WorkforceCalendarEvent,
} from "../../lib/api-client/workforce-calendar";
import { useAuth } from "../../lib/auth/auth-context";
import { useActionError } from "../../lib/mutations/action-error";
import { CalendarEventForm, type CalendarEventDraft } from "./CalendarEventForm";
import { CalendarCommitmentActions } from "./CalendarCommitmentActions";
import { CalendarViewModePicker, type CalendarViewMode } from "./CalendarViewModePicker";
import { filterCalendarView } from "./calendar-view-model";
import { calendarMutation, type CalendarEditScope, seriesEvent } from "./calendar-event-mutations";

const ACTIVITIES: Record<CalendarActivity, string> = {
  leave: "Leave",
  training: "Training",
  duty: "Duty",
  appointment: "Appointment",
  meeting: "Meeting",
  task: "Task",
  other: "Other",
};

function eventDate(event: WorkforceCalendarEvent) {
  const raw = event.timing.allDayStart ?? event.timing.startsAt;
  if (!raw) return "Date unavailable";
  const date = event.timing.allDayStart ? new Date(`${raw}T12:00:00Z`) : new Date(raw);
  return new Intl.DateTimeFormat("en-GB", { dateStyle: "full" }).format(date);
}

function eventTime(event: WorkforceCalendarEvent) {
  if (!event.timing.startsAt || !event.timing.endsAt) return "";
  const format = (value: string) =>
    new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit" }).format(
      new Date(value),
    );
  return ` · ${format(event.timing.startsAt)}–${format(event.timing.endsAt)}`;
}

export default function CalendarPage() {
  const { session } = useAuth();
  const queryClient = useQueryClient();
  const horizon = new Date();
  horizon.setDate(horizon.getDate() + 90);
  const [editing, setEditing] = useState<WorkforceCalendarEvent | null>(null);
  const [editScope, setEditScope] = useState<CalendarEditScope>("series");
  const [viewMode, setViewMode] = useState<CalendarViewMode>("agenda");
  const { actionError, clearActionError, failActionWith } = useActionError();
  const range = { start: new Date().toISOString(), end: horizon.toISOString() };
  const calendar = useQuery({
    queryKey: ["workforce-calendar", "agenda", range.start.slice(0, 10)],
    queryFn: () => listMyCalendar(range.start, range.end),
    retry: false,
  });
  const commitments = useQuery({
    queryKey: ["workforce-calendar", "commitments"],
    queryFn: listMyCommitments,
    retry: false,
  });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["workforce-calendar"] });
  const saveEvent = useMutation({
    mutationFn: async (draft: CalendarEventDraft) => {
      if (!session) throw new Error("Your session has ended.");
      const request = calendarMutation(draft, session.user.id, editing, editScope);
      if (editing?.recurrence && !window.confirm(saveConfirmation(editScope))) {
        throw new ConfirmationDeclined();
      }
      return executeCalendarMutation(request, session.csrfToken);
    },
    onError: (error) => {
      if (!(error instanceof ConfirmationDeclined))
        failActionWith("The calendar event could not be saved.")(error);
    },
    onMutate: clearActionError,
    onSuccess: () => {
      setEditing(null);
      void refresh();
    },
  });
  const cancelEvent = useMutation({
    mutationFn: async ({
      event,
      scope,
    }: {
      event: WorkforceCalendarEvent;
      scope: "occurrence" | "series";
    }) => {
      if (!session) throw new Error("Your session has ended.");
      if (event.recurrence && !window.confirm(cancelConfirmation(scope))) {
        throw new ConfirmationDeclined();
      }
      return executeCalendarMutation(
        {
          operation: scope === "occurrence" ? "cancel_occurrence" : "cancel",
          event: seriesEvent(event),
          expectedVersion: event.version,
          authorisingGrantId: null,
          reason:
            scope === "occurrence"
              ? "Cancel one personal calendar occurrence."
              : "Cancel a personal calendar series.",
          occurrenceKey: scope === "occurrence" ? event.occurrenceKey : null,
          futureEventId: null,
        },
        session.csrfToken,
      );
    },
    onError: (error) => {
      if (!(error instanceof ConfirmationDeclined))
        failActionWith("The calendar event could not be removed.")(error);
    },
    onMutate: clearActionError,
    onSuccess: () => void refresh(),
  });
  const respond = useMutation({
    mutationFn: ({
      commitment,
      state,
      reason,
    }: {
      commitment: CalendarCommitment;
      state: "acknowledged" | "disputed";
      reason?: string;
    }) =>
      respondToCommitment(
        commitment.event.eventId,
        { state, expectedVersion: commitment.responseVersion, reason },
        session?.csrfToken ?? "",
      ),
    onError: failActionWith("Your commitment response could not be saved."),
    onMutate: clearActionError,
    onSuccess: () => void refresh(),
  });
  if (!session) return null;
  const events = filterCalendarView(calendar.data?.events ?? [], viewMode);
  const commitmentByEvent = new Map(
    (commitments.data?.commitments ?? []).map((item) => [item.event.eventId, item]),
  );
  return (
    <div className="calendar-page">
      <header className="calendar-page__header">
        <div>
          <p className="eyebrow">Workforce calendar</p>
          <h1>My calendar</h1>
          <p>Plan your own activity. Team views use the same privacy-safe occurrences.</p>
        </div>
        <Link className="button secondary" to="/account/profile">
          Back to profile
        </Link>
      </header>
      <div className="calendar-page__layout">
        <CalendarEventForm
          actionError={actionError}
          disabled={calendar.isError}
          editing={editing}
          editScope={editScope}
          onDiscard={() => setEditing(null)}
          onSubmit={(draft) => saveEvent.mutate(draft)}
          pending={saveEvent.isPending}
        />
        <section className="surface calendar-agenda" aria-labelledby="calendar-agenda-title">
          <div className="calendar-agenda__heading">
            <div>
              <p className="eyebrow">Canonical calendar</p>
              <h2 id="calendar-agenda-title">Your activity</h2>
            </div>
            <CalendarViewModePicker mode={viewMode} onChange={setViewMode} />
          </div>
          {calendar.isLoading ? <p role="status">Loading your calendar…</p> : null}
          {calendar.isError ? (
            <p role="alert">Your calendar is not available yet. No changes can be made here.</p>
          ) : null}
          {!calendar.isLoading && !calendar.isError && events.length === 0 ? (
            <p className="calendar-agenda__empty">No activity has been added.</p>
          ) : null}
          <ol
            aria-label={`${viewMode} calendar activity`}
            className={`calendar-agenda__list calendar-agenda__list--${viewMode}`}
            id="calendar-activity-panel"
            role="tabpanel"
          >
            {events.map((event) => (
              <li
                key={`${event.seriesEventId ?? event.eventId}-${event.occurrenceKey ?? "single"}`}
              >
                <span
                  className={`calendar-agenda__effect calendar-agenda__effect--${event.availability}`}
                />
                <span>
                  <strong>{ACTIVITIES[event.activity]}</strong>
                  <small>
                    {eventDate(event)}
                    {eventTime(event)}
                    {event.recurrence ? ` · Repeats ${event.recurrence.frequency}` : ""}
                    {event.note ? ` · ${event.note}` : ""}
                  </small>
                </span>
                {event.source === "personal" ? (
                  <div className="calendar-agenda__actions">
                    {event.recurrence ? (
                      <>
                        <EditButton event={event} label="this occurrence" onEdit={beginEdit} />
                        <EditButton
                          event={event}
                          label="this and future occurrences"
                          onEdit={beginEdit}
                        />
                        <EditButton event={event} label="whole series" onEdit={beginEdit} />
                        <CancelButton
                          event={event}
                          label="occurrence"
                          onCancel={cancelEvent.mutate}
                        />
                      </>
                    ) : (
                      <EditButton event={event} label="whole series" onEdit={beginEdit} />
                    )}
                    <button
                      aria-label={
                        event.recurrence
                          ? `Cancel ${ACTIVITIES[event.activity]} series`
                          : `Remove ${ACTIVITIES[event.activity]}`
                      }
                      disabled={cancelEvent.isPending}
                      onClick={() => cancelEvent.mutate({ event, scope: "series" })}
                      title={event.recurrence ? "Cancel whole series" : "Remove activity"}
                      type="button"
                    >
                      <Trash2 aria-hidden="true" size={15} />
                    </button>
                  </div>
                ) : event.source === "manager" && commitmentByEvent.has(event.eventId) ? (
                  <CalendarCommitmentActions
                    commitment={commitmentByEvent.get(event.eventId)!}
                    disabled={respond.isPending}
                    onRespond={(commitment, state, reason) =>
                      respond.mutate({ commitment, state, reason })
                    }
                  />
                ) : null}
              </li>
            ))}
          </ol>
        </section>
      </div>
    </div>
  );

  function beginEdit(event: WorkforceCalendarEvent, label: string) {
    setEditing(event);
    setEditScope(
      label === "this occurrence"
        ? "occurrence"
        : label === "this and future occurrences"
          ? "future"
          : "series",
    );
  }
}

type EditProps = {
  event: WorkforceCalendarEvent;
  label: string;
  onEdit: (event: WorkforceCalendarEvent, label: string) => void;
};

function EditButton({ event, label, onEdit }: EditProps) {
  return (
    <button
      aria-label={`Edit ${ACTIVITIES[event.activity]} ${label}`}
      onClick={() => onEdit(event, label)}
      title={`Edit ${label}`}
      type="button"
    >
      <Pencil aria-hidden="true" size={15} />
    </button>
  );
}

function CancelButton({
  event,
  label,
  onCancel,
}: Omit<EditProps, "onEdit"> & {
  onCancel: (value: { event: WorkforceCalendarEvent; scope: "occurrence" }) => void;
}) {
  return (
    <button
      aria-label={`Cancel ${ACTIVITIES[event.activity]} ${label}`}
      onClick={() => onCancel({ event, scope: "occurrence" })}
      title="Cancel this occurrence"
      type="button"
    >
      <Trash2 aria-hidden="true" size={15} />
    </button>
  );
}

const saveConfirmation = (scope: CalendarEditScope) =>
  scope === "occurrence"
    ? "Save changes to this occurrence only?"
    : scope === "future"
      ? "Save changes to this and all future occurrences?"
      : "Save changes to every occurrence in this series?";

const cancelConfirmation = (scope: "occurrence" | "series") =>
  scope === "occurrence"
    ? "Cancel this occurrence only?"
    : "Cancel every occurrence in this series?";

class ConfirmationDeclined extends Error {}
