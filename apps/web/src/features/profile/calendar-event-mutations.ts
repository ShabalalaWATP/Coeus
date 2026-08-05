import type {
  CalendarMutation,
  WorkforceCalendarEvent,
  WorkforceCalendarSeriesEvent,
} from "../../lib/api-client/workforce-calendar";
import type { CalendarEventDraft } from "./CalendarEventForm";

export type CalendarEditScope = "occurrence" | "future" | "series";

export function calendarMutation(
  draft: CalendarEventDraft,
  userId: string,
  existing: WorkforceCalendarEvent | null,
  scope: CalendarEditScope,
): CalendarMutation {
  const base = existing ? seriesEvent(existing) : newEvent(userId, draft);
  const operation = !existing
    ? "create"
    : scope === "occurrence" && existing.recurrence
      ? "update_occurrence"
      : scope === "future" && existing.recurrence
        ? "update_future"
        : "update";
  return {
    operation,
    event: {
      ...base,
      activity: draft.activity,
      timing: timing(draft),
      availability: draft.availability,
      privacy: draft.privacy,
      note: draft.note,
      recurrence: draft.recurrence,
    },
    expectedVersion: existing?.version ?? 0,
    authorisingGrantId: null,
    reason: reason(operation),
    occurrenceKey:
      operation.includes("occurrence") || operation === "update_future"
        ? existing?.occurrenceKey
        : null,
    futureEventId: operation === "update_future" ? crypto.randomUUID() : null,
  };
}

export function seriesEvent(event: WorkforceCalendarEvent): WorkforceCalendarSeriesEvent {
  return {
    eventId: event.eventId,
    ownerUserId: event.ownerUserId,
    source: event.source,
    activity: event.activity,
    timing: event.seriesTiming ?? event.timing,
    availability: event.availability,
    privacy: event.privacy,
    createdByUserId: event.createdByUserId,
    note: event.note,
    recurrence: event.recurrence,
    managerScopeUnitId: event.managerScopeUnitId,
    status: event.status,
    version: event.version,
    createdAt: event.createdAt,
    updatedAt: event.updatedAt,
    cancelledAt: event.cancelledAt,
  };
}

function timing(draft: CalendarEventDraft) {
  const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  if (draft.allDay) {
    return {
      timeZone,
      startsAt: null,
      endsAt: null,
      allDayStart: draft.startDate,
      allDayEnd: nextDay(draft.endDate),
    };
  }
  return {
    timeZone,
    startsAt: new Date(`${draft.startDate}T${draft.startTime}:00`).toISOString(),
    endsAt: new Date(`${draft.endDate}T${draft.endTime}:00`).toISOString(),
    allDayStart: null,
    allDayEnd: null,
  };
}

function newEvent(userId: string, draft: CalendarEventDraft): WorkforceCalendarSeriesEvent {
  return {
    eventId: crypto.randomUUID(),
    ownerUserId: userId,
    source: "personal",
    activity: draft.activity,
    timing: timing(draft),
    availability: draft.availability,
    privacy: draft.privacy,
    createdByUserId: userId,
    note: draft.note,
    recurrence: null,
    managerScopeUnitId: null,
    status: "active",
    version: 1,
    createdAt: null,
    updatedAt: null,
    cancelledAt: null,
  };
}

function nextDay(value: string) {
  const date = new Date(`${value}T12:00:00Z`);
  date.setUTCDate(date.getUTCDate() + 1);
  return date.toISOString().slice(0, 10);
}

function reason(operation: CalendarMutation["operation"]) {
  const labels: Record<CalendarMutation["operation"], string> = {
    create: "Add a personal calendar series.",
    update: "Update every occurrence in a personal calendar series.",
    cancel: "Cancel a personal calendar series.",
    update_occurrence: "Update one personal calendar occurrence.",
    cancel_occurrence: "Cancel one personal calendar occurrence.",
    update_future: "Split and update this and future personal calendar occurrences.",
  };
  return labels[operation];
}
