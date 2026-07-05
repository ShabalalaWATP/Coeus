import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import {
  approveRoute,
  listRoutingQueue,
  rejectRoute,
  requestRouteClarification,
  runRoutingReviews,
  type CmCapabilityReview,
  type RfaCapabilityReview,
  type RoutingQueue,
  type RoutingRoute,
  type RoutingTicket,
} from "../../lib/api-client/routing";
import { useAuth } from "../../lib/auth/auth-context";

type RoutingQueuePageProps = {
  route: RoutingRoute;
};

const EMPTY_QUEUE: RoutingQueue = {
  tickets: [],
  stats: {
    routeAssessmentCount: 0,
    rfaReviewCount: 0,
    cmReviewCount: 0,
    clarificationCount: 0,
    analystAssignmentCount: 0,
    rfaAcceptanceRate: 0,
    cmFallbackRate: 0,
  },
};

export default function RoutingQueuePage({ route }: RoutingQueuePageProps) {
  const { session } = useAuth();
  const queryClient = useQueryClient();
  const csrfToken = session?.csrfToken ?? "";
  const [selectedTicketId, setSelectedTicketId] = useState<string>();
  const [clarificationReason, setClarificationReason] = useState("");
  const [clarificationQuestion, setClarificationQuestion] = useState("");
  const [rejectReason, setRejectReason] = useState("");
  const queueQuery = useQuery({
    queryKey: ["routing-queue", route],
    queryFn: () => listRoutingQueue(route),
    initialData: EMPTY_QUEUE,
    initialDataUpdatedAt: 0,
  });
  const queue = queueQuery.data;
  const selectedTicket = useMemo(
    () => queue.tickets.find((ticket) => ticket.ticketId === selectedTicketId) ?? queue.tickets[0],
    [queue.tickets, selectedTicketId],
  );
  const updateQueue = (ticket: RoutingTicket) => {
    queryClient.setQueryData<RoutingQueue>(["routing-queue", route], {
      ...queue,
      tickets: upsertRoutingTicket(queue.tickets, ticket, route),
    });
    setSelectedTicketId(ticket.ticketId);
  };
  const runMutation = useMutation({
    mutationFn: () => runRoutingReviews(selectedTicket.ticketId, csrfToken),
    onSuccess: updateQueue,
  });
  const approveMutation = useMutation({
    mutationFn: () => approveRoute(selectedTicket.ticketId, route, csrfToken),
    onSuccess: updateQueue,
  });
  const rejectMutation = useMutation({
    mutationFn: () => rejectRoute(selectedTicket.ticketId, route, rejectReason, csrfToken),
    onSuccess: updateQueue,
  });
  const clarificationMutation = useMutation({
    mutationFn: () =>
      requestRouteClarification(
        selectedTicket.ticketId,
        route,
        clarificationReason,
        [clarificationQuestion],
        csrfToken,
      ),
    onSuccess: updateQueue,
  });
  const labels = route === "rfa" ? rfaLabels : cmLabels;

  return (
    <div className="routing-page">
      <section className="overview-hero" aria-labelledby="routing-title">
        <div>
          <h1 id="routing-title">{labels.title}</h1>
          <p>{labels.description}</p>
        </div>
        <div className="classification-note">MOCK DATA ONLY</div>
      </section>
      <section className="routing-grid">
        <aside className="surface routing-list" aria-label={`${labels.shortName} tickets`}>
          <div className="section-heading">
            <h2>Manager queue</h2>
            <p>{queue.tickets.length} tickets need route action.</p>
          </div>
          <RoutingStats queue={queue} />
          {queue.tickets.length ? (
            queue.tickets.map((ticket) => (
              <button
                className="request-row"
                key={ticket.ticketId}
                onClick={() => setSelectedTicketId(ticket.ticketId)}
                type="button"
              >
                <strong>{ticket.reference}</strong>
                <span>{ticket.title}</span>
                <small>{formatState(ticket.state)}</small>
              </button>
            ))
          ) : (
            <p>No tickets in this queue.</p>
          )}
        </aside>
        <section className="surface routing-detail" aria-label="Route recommendation">
          {selectedTicket ? (
            <>
              <div className="section-heading">
                <h2>{selectedTicket.reference}</h2>
                <p>{selectedTicket.title}</p>
              </div>
              <p className="status-pill">{formatState(selectedTicket.state)}</p>
              <Recommendation ticket={selectedTicket} />
              <Review title="RFA recommendation" review={selectedTicket.rfaReview} />
              <Review title="CM recommendation" review={selectedTicket.cmReview} />
              <PlanUpdates ticket={selectedTicket} />
              <div className="routing-actions">
                {selectedTicket.state === "ROUTE_ASSESSMENT" ? (
                  <button
                    disabled={runMutation.isPending}
                    onClick={() => runMutation.mutate()}
                    type="button"
                  >
                    Run capability checks
                  </button>
                ) : null}
                <button
                  disabled={!canApprove(selectedTicket, route) || approveMutation.isPending}
                  onClick={() => approveMutation.mutate()}
                  type="button"
                >
                  Approve route
                </button>
              </div>
              <div className="routing-forms">
                <label>
                  Clarification reason
                  <textarea
                    onChange={(event) => setClarificationReason(event.target.value)}
                    value={clarificationReason}
                  />
                </label>
                <label>
                  Clarification question
                  <input
                    onChange={(event) => setClarificationQuestion(event.target.value)}
                    value={clarificationQuestion}
                  />
                </label>
                <button
                  disabled={!canSubmitClarification(selectedTicket, route, clarificationReason)}
                  onClick={() => clarificationMutation.mutate()}
                  type="button"
                >
                  Request clarification
                </button>
                <label>
                  Rejection reason
                  <textarea
                    onChange={(event) => setRejectReason(event.target.value)}
                    value={rejectReason}
                  />
                </label>
                <button
                  disabled={!canReject(selectedTicket, route, rejectReason)}
                  onClick={() => rejectMutation.mutate()}
                  type="button"
                >
                  Reject route
                </button>
              </div>
            </>
          ) : (
            <p>No ticket selected.</p>
          )}
        </section>
      </section>
    </div>
  );
}

function RoutingStats({ queue }: { queue: RoutingQueue }) {
  return (
    <dl className="routing-stats" aria-label="Routing statistics">
      <div>
        <dt>RFA review</dt>
        <dd>{queue.stats.rfaReviewCount}</dd>
      </div>
      <div>
        <dt>CM review</dt>
        <dd>{queue.stats.cmReviewCount}</dd>
      </div>
      <div>
        <dt>CM fallback</dt>
        <dd>{Math.round(queue.stats.cmFallbackRate * 100)}%</dd>
      </div>
    </dl>
  );
}

function Recommendation({ ticket }: { ticket: RoutingTicket }) {
  return ticket.recommendation ? (
    <article className="routing-recommendation">
      <h3>Recommended route: {ticket.recommendation.recommendedRoute.toUpperCase()}</h3>
      <p>{ticket.recommendation.reasoningSummary}</p>
    </article>
  ) : (
    <article className="routing-recommendation">
      <h3>No route recommendation</h3>
      <p>Capability checks have not run for this ticket.</p>
    </article>
  );
}

function Review({
  review,
  title,
}: {
  review: CmCapabilityReview | RfaCapabilityReview | null;
  title: string;
}) {
  if (!review) {
    return null;
  }
  return (
    <article className="routing-review">
      <h3>{title}</h3>
      <p>{review.reasoningSummary}</p>
      <dl>
        <div>
          <dt>Can satisfy</dt>
          <dd>{review.canSatisfy ? "Yes" : "No"}</dd>
        </div>
        <div>
          <dt>Confidence</dt>
          <dd>{Math.round(review.confidence * 100)}%</dd>
        </div>
        <div>
          <dt>Effort</dt>
          <dd>{review.estimatedEffort}</dd>
        </div>
      </dl>
      {review.requiredClarifications.length ? (
        <ul>
          {review.requiredClarifications.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      ) : null}
    </article>
  );
}

function PlanUpdates({ ticket }: { ticket: RoutingTicket }) {
  return ticket.projectPlanUpdates.length ? (
    <article className="routing-plan">
      <h3>Project plan updates</h3>
      <ul>
        {ticket.projectPlanUpdates.map((item) => (
          <li key={item.id}>
            <strong>{item.title}</strong>
            <span>{item.ownerRole}</span>
          </li>
        ))}
      </ul>
    </article>
  ) : null;
}

function canApprove(ticket: RoutingTicket, route: RoutingRoute) {
  return ticket.state === (route === "rfa" ? "RFA_MANAGER_REVIEW" : "CM_MANAGER_REVIEW");
}

function canReject(ticket: RoutingTicket, route: RoutingRoute, reason: string) {
  return canApprove(ticket, route) && reason.trim().length >= 3;
}

function canSubmitClarification(ticket: RoutingTicket, route: RoutingRoute, reason: string) {
  return canApprove(ticket, route) && reason.trim().length >= 3;
}

function formatState(state: string) {
  return state.replaceAll("_", " ");
}

function upsertRoutingTicket(
  tickets: RoutingTicket[],
  nextTicket: RoutingTicket,
  route: RoutingRoute,
) {
  const visibleState = route === "rfa" ? "RFA_MANAGER_REVIEW" : "CM_MANAGER_REVIEW";
  const shouldRemainVisible =
    nextTicket.state === visibleState || nextTicket.state === "ROUTE_ASSESSMENT";
  const withoutCurrent = tickets.filter((ticket) => ticket.ticketId !== nextTicket.ticketId);
  return shouldRemainVisible ? [nextTicket, ...withoutCurrent] : withoutCurrent;
}

const rfaLabels = {
  title: "RFA Queue",
  shortName: "RFA",
  description: "Review RFA capability decisions and approve assessment-led routes.",
};

const cmLabels = {
  title: "Collection Queue",
  shortName: "Collection",
  description: "Review CM capability decisions and approve collection-backed routes.",
};
