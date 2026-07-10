import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import { CapabilityCataloguePanel } from "./CapabilityCataloguePanel";
import { ReleaseQueuePanel } from "./ReleaseQueuePanel";
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
  route: RoutingRoute;
};

const EMPTY_QUEUE: RoutingQueue = {
  tickets: [],
  nextCursor: null,
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
  const [overrideReason, setOverrideReason] = useState("");
  const { actionError, clearActionError, failActionWith } = useActionError();
  const queueQuery = useQuery({
    queryKey: ["routing-queue", route],
    queryFn: () => listRoutingQueue(route),
    initialData: EMPTY_QUEUE,
    initialDataUpdatedAt: 0,
  });
  const queue = queueQuery.data;
  const olderQueueMutation = useMutation({
    mutationFn: () => listRoutingQueue(route, queue.nextCursor ?? undefined),
    onSuccess: (page) => {
      queryClient.setQueryData<RoutingQueue>(["routing-queue", route], {
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
    onError: failActionWith("The capability checks could not be run. Try again."),
    onMutate: clearActionError,
    onSuccess: updateQueue,
  });
  const approveMutation = useMutation({
    mutationFn: () =>
      approveRoute(
        selectedTicket.ticketId,
        route,
        csrfToken,
        isRouteOverride(selectedTicket, route) ? overrideReason.trim() : undefined,
      ),
    onError: failActionWith("The route could not be approved. Try again."),
    onMutate: clearActionError,
    onSuccess: (ticket) => {
      setOverrideReason("");
      updateQueue(ticket);
    },
  });
  const rejectMutation = useMutation({
    mutationFn: () => rejectRoute(selectedTicket.ticketId, route, rejectReason, csrfToken),
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
        route,
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
            <>
              <RoutingTicketList onSelect={setSelectedTicketId} tickets={queue.tickets} />
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
        </aside>
        <RoutingDetailPanel
          actionError={actionError}
          clarificationQuestion={clarificationQuestion}
          clarificationReason={clarificationReason}
          csrfToken={csrfToken}
          isApprovePending={approveMutation.isPending}
          isLinkingSimilar={linkSimilarMutation.isPending}
          isRunningReviews={runMutation.isPending}
          isSimilarLoading={similarRequestsQuery.isLoading}
          isSimilarQueryError={similarRequestsQuery.isError}
          onApprove={() => approveMutation.mutate()}
          onAssigned={(task) => removeTicket(task.ticketId)}
          onClarificationQuestionChange={setClarificationQuestion}
          onClarificationReasonChange={setClarificationReason}
          onLinkSimilar={(id) => linkSimilarMutation.mutate(id)}
          onOverrideReasonChange={setOverrideReason}
          onReject={() => rejectMutation.mutate()}
          onRejectReasonChange={setRejectReason}
          onRequestClarification={() => clarificationMutation.mutate()}
          onRetrySimilar={() => void similarRequestsQuery.refetch()}
          onRunReviews={() => runMutation.mutate()}
          overrideReason={overrideReason}
          rejectReason={rejectReason}
          route={route}
          selectedTicket={selectedTicket}
          similarMatches={similarRequestsQuery.data}
        />
      </section>
      <ReleaseQueuePanel csrfToken={csrfToken} route={route} />
    </div>
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
