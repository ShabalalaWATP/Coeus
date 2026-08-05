import { apiRequestJson } from "./client";
import type { components } from "./generated/openapi";

type ApiSchemas = components["schemas"];

export type CalendarProjection = ApiSchemas["CalendarProjectionResponse"];

export type CalendarActivity =
  "leave" | "training" | "duty" | "appointment" | "meeting" | "task" | "other";

type CalendarTiming = {
  timeZone: string;
  startsAt: string | null;
  endsAt: string | null;
  allDayStart: string | null;
  allDayEnd: string | null;
};

export type CalendarRecurrence = {
  frequency: "daily" | "weekly";
  interval: number;
  until: string;
  weekdays: number[];
};

export type WorkforceCalendarSeriesEvent = {
  eventId: string;
  ownerUserId: string;
  source: "personal" | "manager" | "team" | "task" | "external" | "legacy";
  activity: CalendarActivity;
  timing: CalendarTiming;
  availability: "available" | "partial" | "unavailable";
  privacy: "private" | "team_summary" | "team_detail";
  createdByUserId: string;
  note: string;
  recurrence: CalendarRecurrence | null;
  managerScopeUnitId: string | null;
  status: "active" | "cancelled" | "conflicted";
  version: number;
  createdAt: string | null;
  updatedAt: string | null;
  cancelledAt: string | null;
  deduplicationKey?: string | null;
};

export type WorkforceCalendarEvent = WorkforceCalendarSeriesEvent & {
  seriesEventId?: string;
  occurrenceKey?: string;
  seriesTiming?: CalendarTiming;
  duplicateSources?: WorkforceCalendarSeriesEvent["source"][];
};

export type CalendarCommitment = {
  event: WorkforceCalendarSeriesEvent;
  responseState: "pending" | "acknowledged" | "disputed";
  responseVersion: number;
  notifiedAt: string;
  respondedAt: string | null;
};

export type CalendarMutation = {
  operation:
    "create" | "update" | "cancel" | "update_occurrence" | "cancel_occurrence" | "update_future";
  event: WorkforceCalendarSeriesEvent;
  expectedVersion: number;
  authorisingGrantId: string | null;
  reason: string;
  occurrenceKey?: string | null;
  futureEventId?: string | null;
};

type CalendarPreview = { previewHash: string; request: CalendarMutation };

export async function listMyCalendar(
  windowStart: string,
  windowEnd: string,
): Promise<{ events: WorkforceCalendarEvent[] }> {
  const query = new URLSearchParams({ windowStart, windowEnd });
  return apiRequestJson<{ events: WorkforceCalendarEvent[] }>(
    `/api/v1/calendar/me?${query.toString()}`,
    { method: "GET" },
  );
}

export async function listUnitCalendar(
  unitId: string,
  windowStart: string,
  windowEnd: string,
  options: { includeDescendants: boolean; view: "availability" | "detail" },
): Promise<CalendarProjection> {
  const query = new URLSearchParams({
    windowStart,
    windowEnd,
    includeDescendants: String(options.includeDescendants),
    view: options.view,
  });
  return apiRequestJson<CalendarProjection>(
    `/api/v1/calendar/units/${encodeURIComponent(unitId)}?${query.toString()}`,
    { method: "GET" },
  );
}

export async function listMyCommitments(): Promise<{ commitments: CalendarCommitment[] }> {
  return apiRequestJson("/api/v1/calendar/commitments/me", { method: "GET" });
}

export async function respondToCommitment(
  eventId: string,
  response: {
    state: "acknowledged" | "disputed";
    expectedVersion: number;
    reason?: string;
  },
  csrfToken: string,
): Promise<CalendarCommitment> {
  return apiRequestJson(`/api/v1/calendar/commitments/${encodeURIComponent(eventId)}/responses`, {
    body: JSON.stringify(response),
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrfToken },
    method: "POST",
  });
}

export async function executeCalendarMutation(
  request: CalendarMutation,
  csrfToken: string,
): Promise<{ eventId: string; version: number; replayed: boolean }> {
  const headers = { "Content-Type": "application/json", "X-CSRF-Token": csrfToken };
  const preview = await apiRequestJson<CalendarPreview>("/api/v1/calendar/previews", {
    body: JSON.stringify(request),
    headers,
    method: "POST",
  });
  return apiRequestJson("/api/v1/calendar/commands", {
    body: JSON.stringify({
      commandId: crypto.randomUUID(),
      idempotencyKey: `calendar-${request.operation}-${crypto.randomUUID()}`,
      request: preview.request,
      previewHash: preview.previewHash,
    }),
    headers,
    method: "POST",
  });
}
