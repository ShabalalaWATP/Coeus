import { apiRequestJson } from "./client";

export type AuditEvent = {
  eventId: string;
  eventType: string;
  occurredAt: string;
  actorUserId: string | null;
  metadata: Record<string, string>;
};

export async function listAuditEvents(): Promise<AuditEvent[]> {
  const response = await apiRequestJson<{ events: AuditEvent[] }>("/api/v1/audit", {
    method: "GET",
  });
  return response.events;
}
