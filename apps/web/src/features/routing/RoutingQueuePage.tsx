import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { MessageCircleQuestion } from "lucide-react";
import { useMemo, useState } from "react";

import { AssignAnalystPanel } from "./AssignAnalystPanel";
import { CapabilityCataloguePanel } from "./CapabilityCataloguePanel";
import { ReleaseQueuePanel } from "./ReleaseQueuePanel";
import {
  canApprove,
  canReject,
  canSubmitClarification,
  upsertRoutingTicket,
} from "./routing-model";
import { PlanUpdates, Recommendation, Review, RoutingStats } from "./routing-sections";
import { EmptyState, ErrorState } from "../../components/ui/PageState";
import { StatusPill } from "../../components/ui/StatusPill";
import { formatWorkflowState } from "../../lib/workflow/state-format";
import {
  approveRoute,
  listRoutingQueue,
  rejectRoute,
  requestRouteClarification,
  runRoutingReviews,
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
    const nextTickets = upsertRoutingTicket(queue.tickets, ticket, route);
    queryClient.setQueryData<RoutingQueue>(["routing-queue", route], {
      ...queue,
      tickets: nextTickets,
    });
    // Keep the ticket selected only while it stays in this queue. Once it is
    // routed away (reject, clarification or approval) clear the selection so the
    // detail panel does not silently fall back to an unrelated ticket.
    const stillVisible = nextTickets.some((item) => item.ticketId === ticket.ticketId);
    setSelectedTicketId(stillVisible ? ticket.ticketId : undefined);
  };
  const removeTicket = (ticketId: string) => {
    queryClient.setQueryData<RoutingQueue>(["routing-queue", route], {
      ...queue,
      tickets: queue.tickets.filter((ticket) => ticket.ticketId !== ticketId),
    });
    setSelectedTicketId(undefined);
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
          <CapabilityCataloguePanel route={route} />
          {queueQuery.isError ? (
            <ErrorState onRetry={() => void queueQuery.refetch()} />
          ) : (
            <TicketList onSelect={setSelectedTicketId} tickets={queue.tickets} />
          )}
        </aside>
        <section className="surface routing-detail" aria-label="Route recommendation">
          {selectedTicket ? (
            <>
              <div className="section-heading">
                <h2>{selectedTicket.reference}</h2>
                <p>{selectedTicket.title}</p>
              </div>
              <StatusPill state={selectedTicket.state} />
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
              {selectedTicket.state === "ANALYST_ASSIGNMENT" ? (
                <AssignAnalystPanel
                  csrfToken={csrfToken}
                  onAssigned={(task) => removeTicket(task.ticketId)}
                  suggestedTeamName={teamNameForAssignment(selectedTicket, route)}
                  ticketId={selectedTicket.ticketId}
                />
              ) : (
                <details className="workspace-details">
                  <summary>
                    <MessageCircleQuestion aria-hidden="true" size={16} />
                    Query or reject this route
                  </summary>
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
                </details>
              )}
            </>
          ) : (
            <EmptyState
              hint="Approved and routed tickets leave this queue automatically."
              title="No ticket selected"
            />
          )}
        </section>
      </section>
      <ReleaseQueuePanel csrfToken={csrfToken} route={route} />
    </div>
  );
}

function TicketList({
  onSelect,
  tickets,
}: {
  onSelect: (ticketId: string) => void;
  tickets: RoutingTicket[];
}) {
  if (tickets.length === 0) {
    return <p>No tickets in this queue.</p>;
  }
  return (
    <>
      {tickets.map((ticket) => (
        <button
          className="request-row"
          key={ticket.ticketId}
          onClick={() => onSelect(ticket.ticketId)}
          type="button"
        >
          <strong>{ticket.reference}</strong>
          <span>{ticket.title}</span>
          <small>{formatWorkflowState(ticket.state)}</small>
        </button>
      ))}
    </>
  );
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

function teamNameForAssignment(ticket: RoutingTicket, route: RoutingRoute) {
  if (route === "rfa") {
    return ticket.rfaReview?.suggestedTeamName ?? "";
  }
  return ticket.cmReview?.suggestedCollectionTeamName ?? "";
}
