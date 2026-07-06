import { useQuery } from "@tanstack/react-query";
import { ClipboardList } from "lucide-react";

import { EmptyState, ErrorState, LoadingState } from "../../components/ui/PageState";
import { listAuditEvents } from "../../lib/api-client/audit";

export default function AuditPage() {
  const auditQuery = useQuery({
    queryKey: ["audit-events"],
    queryFn: listAuditEvents,
  });
  const events = auditQuery.data ?? [];

  return (
    <div className="project-page">
      <section className="overview-hero" aria-labelledby="audit-title">
        <div>
          <h1 id="audit-title">Audit</h1>
          <p>Immutable security and workflow events for operational review.</p>
        </div>
        <div className="classification-note">MOCK DATA ONLY</div>
      </section>

      <section className="surface" aria-labelledby="audit-events-title">
        <div className="section-heading access-heading">
          <ClipboardList aria-hidden="true" size={20} />
          <div>
            <h2 id="audit-events-title">Events</h2>
            <p>{events.length} events recorded.</p>
          </div>
        </div>
        {auditQuery.isLoading ? <LoadingState label="Loading audit events" /> : null}
        {auditQuery.isError ? <ErrorState onRetry={() => void auditQuery.refetch()} /> : null}
        {events.length === 0 && !auditQuery.isLoading && !auditQuery.isError ? (
          <EmptyState
            hint="Security and workflow events appear here as operators use the system."
            title="No audit events recorded"
          />
        ) : null}
        <div className="stack-list">
          {events.map((event) => (
            <article className="stack-row" key={event.eventId}>
              <strong>{event.eventType}</strong>
              <span>{new Date(event.occurredAt).toLocaleString()}</span>
              <small>{event.actorUserId ?? "system"}</small>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}
