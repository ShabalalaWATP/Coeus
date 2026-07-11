import { apiRequestJson } from "./client";

type AuditEvent = {
  eventId: string;
  eventType: string;
  occurredAt: string;
  actorUserId: string | null;
  metadata: Record<string, string>;
};

export type AuditEventPage = {
  events: AuditEvent[];
  nextCursor: string | null;
};

export async function listAuditEvents(cursor?: string): Promise<AuditEventPage> {
  const query = cursor ? `?before=${encodeURIComponent(cursor)}` : "";
  return apiRequestJson<AuditEventPage>(`/api/v1/audit${query}`, {
    method: "GET",
  });
}
