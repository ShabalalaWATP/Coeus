import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import { CapabilityCataloguePanel } from "./CapabilityCataloguePanel";
import { RoutingDetailPanel } from "./RoutingDetailPanel";
import { RoutingTicketList } from "./RoutingTicketList";
import { isRouteOverride, upsertRoutingTicket } from "./routing-model";
import { RoutingStats } from "./routing-sections";
import { ErrorState } from "../../components/ui/PageState";
import {
  approveRoute,
  listRoutingQueue,
  rejectRoute,
  requestRouteClarification,
  runRoutingReviews,
  type RoutingQueue,
  type RoutingQueueKind,
  type RoutingRoute,
  type RoutingTicket,
} from "../../lib/api-client/routing";
import {
  linkRoutingSimilarRequest,
  listRoutingSimilarRequests,
} from "../../lib/api-client/similar-requests";
import { useAuth } from "../../lib/auth/auth-context";
import { useActionError } from "../../lib/mutations/action-error";

type RoutingQueuePageProps = {
  queue: RoutingQueueKind;
};

// A team queue holds tickets from assignment through manager approval; once
// forwarded to QC (or released) the ticket leaves the manager's view.
const TEAM_QUEUE_STATES = new Set([
  "ANALYST_ASSIGNMENT",
  "ANALYST_IN_PROGRESS",
  "MANAGER_APPROVAL",
]);

const EMPTY_QUEUE: RoutingQueue = {
  tickets: [],
  nextCursor: null,
  stats: {
    jiocQueueCount: 0,
    collectChoiceCount: 0,
    clarificationCount: 0,
    analystAssignmentCount: 0,
    rfaAcceptanceRate: 0,
    cmFallbackRate: 0,
  },
};

export default function RoutingQueuePage({ queue: queueKind }: RoutingQueuePageProps) {
  const { session } = useAuth();
  const queryClient = useQueryClient();
  const csrfToken = session?.csrfToken ?? "";
  const isJioc = queueKind === "jioc";
  const [selectedTicketId, setSelectedTicketId] = useState<string>();
  const [decisionRoute, setDecisionRoute] = useState<RoutingRoute>("rfa");
  const [clarificationReason, setClarificationReason] = useState("");
  const [clarificationQuestion, setClarificationQuestion] = useState("");
  const [rejectReason, setRejectReason] = useState("");
  const [overrideReason, setOverrideReason] = useState("");
  const { actionError, clearActionError, failActionWith } = useActionError();
  const queueQuery = useQuery({
    queryKey: ["routing-queue", queueKind],
    queryFn: () => listRoutingQueue(queueKind),
    initialData: EMPTY_QUEUE,
    initialDataUpdatedAt: 0,
  });
  const queue = queueQuery.data;
  const olderQueueMutation = useMutation({
    mutationFn: () => listRoutingQueue(queueKind, queue.nextCursor ?? undefined),
    onSuccess: (page) => {
      queryClient.setQueryData<RoutingQueue>(["routing-queue", queueKind], {
        ...queue,
        nextCursor: page.nextCursor,
        tickets: [
          ...queue.tickets,
          ...page.tickets.filter(
            (candidate) => !queue.tickets.some((ticket) => ticket.ticketId === candidate.ticketId),
          ),
        ],
      });
    },
  });
  const selectedTicket = useMemo(
    () => queue.tickets.find((ticket) => ticket.ticketId === selectedTicketId) ?? queue.tickets[0],
    [queue.tickets, selectedTicketId],
  );
  const selectedSimilarKey = ["similar-requests", "routing", selectedTicket?.ticketId] as const;
  const similarRequestsQuery = useQuery({
    enabled: selectedTicket !== undefined,
    queryFn: () => listRoutingSimilarRequests(selectedTicket?.ticketId ?? ""),
    queryKey: selectedSimilarKey,
  });
  const updateQueue = (ticket: RoutingTicket) => {
    const nextTickets = isJioc
      ? upsertRoutingTicket(queue.tickets, ticket)
      : queue.tickets
          .map((item) => (item.ticketId === ticket.ticketId ? ticket : item))
          .filter(
            (item) => item.ticketId !== ticket.ticketId || TEAM_QUEUE_STATES.has(ticket.state),
          );
    queryClient.setQueryData<RoutingQueue>(["routing-queue", queueKind], {
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
    queryClient.setQueryData<RoutingQueue>(["routing-queue", queueKind], {
      ...queue,
      tickets: queue.tickets.filter((ticket) => ticket.ticketId !== ticketId),
    });
    setSelectedTicketId(undefined);
  };
  const runMutation = useMutation({
    mutationFn: () => runRoutingReviews(selectedTicket.ticketId, csrfToken),
    onError: failActionWith("The capability checks could not be run. Try again."),
    onMutate: clearActionError,
    onSuccess: updateQueue,
  });
  const approveMutation = useMutation({
    mutationFn: () =>
      approveRoute(
        selectedTicket.ticketId,
        decisionRoute,
        csrfToken,
        isRouteOverride(selectedTicket, decisionRoute) ? overrideReason.trim() : undefined,
      ),
    onError: failActionWith("The route could not be approved. Try again."),
    onMutate: clearActionError,
    onSuccess: (ticket) => {
      setOverrideReason("");
      updateQueue(ticket);
    },
  });
  const rejectMutation = useMutation({
    mutationFn: () => rejectRoute(selectedTicket.ticketId, decisionRoute, rejectReason, csrfToken),
    onError: failActionWith("The route could not be rejected. Try again."),
    onMutate: clearActionError,
    onSuccess: (ticket) => {
      setRejectReason("");
      updateQueue(ticket);
    },
  });
  const clarificationMutation = useMutation({
    mutationFn: () =>
      requestRouteClarification(
        selectedTicket.ticketId,
        decisionRoute,
        clarificationReason,
        [clarificationQuestion],
        csrfToken,
      ),
    onError: failActionWith("The clarification request could not be sent. Try again."),
    onMutate: clearActionError,
    onSuccess: (ticket) => {
      setClarificationReason("");
      setClarificationQuestion("");
      updateQueue(ticket);
    },
  });
  const linkSimilarMutation = useMutation({
    mutationFn: (relatedTicketId: string) => {
      if (selectedTicket === undefined) {
        throw new Error("No ticket selected.");
      }
      return linkRoutingSimilarRequest(selectedTicket.ticketId, relatedTicketId, csrfToken);
    },
    onError: failActionWith("The related request could not be linked. Try again."),
    onMutate: clearActionError,
    onSuccess: (matches) => queryClient.setQueryData(selectedSimilarKey, matches),
  });
  const labels = QUEUE_LABELS[queueKind];
  const actionPending =
    runMutation.isPending ||
    approveMutation.isPending ||
    rejectMutation.isPending ||
    clarificationMutation.isPending ||
    linkSimilarMutation.isPending;
  const selectTicket = (ticketId: string) => {
    if (actionPending) return;
    setSelectedTicketId(ticketId);
    setDecisionRoute("rfa");
    setClarificationReason("");
    setClarificationQuestion("");
    setRejectReason("");
    setOverrideReason("");
    clearActionError();
  };

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
            <h2>{labels.listTitle}</h2>
            <p>{queue.tickets.length} tickets in this queue.</p>
          </div>
          {isJioc ? <RoutingStats queue={queue} /> : null}
          {queueQuery.isError ? (
            <ErrorState onRetry={() => void queueQuery.refetch()} />
          ) : (
            <>
              <RoutingTicketList
                disabled={actionPending}
                onSelect={selectTicket}
                selectedTicketId={selectedTicket?.ticketId}
                tickets={queue.tickets}
              />
              {queue.nextCursor ? (
                <button
                  className="secondary-button"
                  disabled={olderQueueMutation.isPending}
                  onClick={() => olderQueueMutation.mutate()}
                  type="button"
                >
                  {olderQueueMutation.isPending ? "Loading more…" : "Load more tickets"}
                </button>
              ) : null}
            </>
          )}
          <CapabilityCataloguePanel route={isJioc ? "rfa" : queueKind} showAll={isJioc} />
        </aside>
        <RoutingDetailPanel
          actionError={actionError}
          actionPending={actionPending}
          canDecide={isJioc}
          onManagerDecision={updateQueue}
          clarificationQuestion={clarificationQuestion}
          clarificationReason={clarificationReason}
          csrfToken={csrfToken}
          decisionRoute={decisionRoute}
          isApprovePending={approveMutation.isPending}
          isLinkingSimilar={linkSimilarMutation.isPending}
          isRunningReviews={runMutation.isPending}
          isSimilarLoading={similarRequestsQuery.isLoading}
          isSimilarQueryError={similarRequestsQuery.isError}
          onApprove={() => approveMutation.mutate()}
          onAssigned={(task) => removeTicket(task.ticketId)}
          onClarificationQuestionChange={setClarificationQuestion}
          onClarificationReasonChange={setClarificationReason}
          onDecisionRouteChange={setDecisionRoute}
          onLinkSimilar={(id) => linkSimilarMutation.mutate(id)}
          onOverrideReasonChange={setOverrideReason}
          onReject={() => rejectMutation.mutate()}
          onRejectReasonChange={setRejectReason}
          onRequestClarification={() => clarificationMutation.mutate()}
          onRetrySimilar={() => void similarRequestsQuery.refetch()}
          onRunReviews={() => runMutation.mutate()}
          overrideReason={overrideReason}
          rejectReason={rejectReason}
          route={isJioc ? decisionRoute : queueKind}
          selectedTicket={selectedTicket}
          similarMatches={similarRequestsQuery.data}
        />
      </section>
    </div>
  );
}

const QUEUE_LABELS: Record<
  RoutingQueueKind,
  { title: string; shortName: string; description: string; listTitle: string }
> = {
  jioc: {
    title: "JIOC Queue",
    shortName: "JIOC",
    description:
      "Decide whether each progressed request needs collection (CM) or assessment (RFA).",
    listTitle: "Route decisions",
  },
  rfa: {
    title: "RFA Queue",
    shortName: "RFA",
    description: "Assign analysts and manage the RFA team's active requests.",
    listTitle: "Team queue",
  },
  cm: {
    title: "Collection Queue",
    shortName: "Collection",
    description: "Assign analysts and manage the collection team's active requests.",
    listTitle: "Team queue",
  },
};
