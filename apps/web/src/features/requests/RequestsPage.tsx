import {
  type InfiniteData,
  useInfiniteQuery,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { MessageSquarePlus } from "lucide-react";
import { useEffect, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";

import { RequestDashboard } from "./RequestDashboard";
import { RequestRouteMissingState } from "./RequestRouteMissingState";
import { TicketWorkspace } from "./TicketWorkspace";
import { SIMILAR_NOTICE_STATES } from "./request-state-sets";
import { useRequestWorkspaceMutations } from "./useRequestWorkspaceMutations";
import { ErrorState, LoadingState } from "../../components/ui/PageState";
import { FeedbackPanel } from "../feedback/FeedbackPanel";
import { getRfiSearchResults } from "../../lib/api-client/rfi-search";
import { getSimilarRequestNotice } from "../../lib/api-client/similar-requests";
import {
  getTicket,
  listTickets,
  type TicketSummary,
  type TicketSummaryPage,
} from "../../lib/api-client/tickets";
import { useAuth } from "../../lib/auth/auth-context";
import { hasPermissions } from "../../lib/permissions/route-access";

const EMPTY_TICKETS: TicketSummary[] = [];
export default function RequestsPage() {
  const { session } = useAuth();
  const { ticketId } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const isNewRequest = location.pathname.endsWith("/new");
  const [journeyOpen, setJourneyOpen] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [dismissedSimilarNoticeIds, setDismissedSimilarNoticeIds] = useState<string[]>([]);
  const csrfToken = session?.csrfToken ?? "";
  const canCreate = session !== null && hasPermissions(session.user, ["chat:use"]);
  const ticketsQuery = useInfiniteQuery<
    TicketSummaryPage,
    Error,
    InfiniteData<TicketSummaryPage>,
    readonly ["tickets"],
    string | undefined
  >({
    getNextPageParam: (page) => page.nextCursor ?? undefined,
    initialPageParam: undefined as string | undefined,
    queryKey: ["tickets"],
    queryFn: ({ pageParam }): Promise<TicketSummaryPage> => listTickets(pageParam),
  });
  const tickets = ticketsQuery.data?.pages.flatMap((page) => page.tickets) ?? EMPTY_TICKETS;
  const selectedTicketQuery = useQuery({
    enabled: !isNewRequest && ticketId !== undefined,
    queryKey: ["tickets", "detail", ticketId],
    queryFn: () => getTicket(ticketId!),
  });
  const selectedTicket = selectedTicketQuery.data;
  const existingTicketLoading =
    !isNewRequest &&
    ticketId !== undefined &&
    selectedTicket === undefined &&
    selectedTicketQuery.isFetching;
  const summaryExhaustedWithoutTicket =
    !ticketsQuery.isFetching &&
    !ticketsQuery.hasNextPage &&
    !tickets.some((ticket) => ticket.id === ticketId);
  const requestedTicketMissing =
    ticketId !== undefined &&
    selectedTicket === undefined &&
    (summaryExhaustedWithoutTicket ||
      (!selectedTicketQuery.isFetching && selectedTicketQuery.isError));
  const selectedTicketId = selectedTicket?.id ?? "";
  const similarNoticeDismissed = dismissedSimilarNoticeIds.includes(selectedTicketId);
  const similarNoticeEligible =
    selectedTicket !== undefined &&
    selectedTicket.requesterUserId === session?.user.id &&
    SIMILAR_NOTICE_STATES.has(selectedTicket.state) &&
    !similarNoticeDismissed;
  const selectedRfiKey = ["rfi-search", selectedTicketId] as const;
  const hasCachedRfiResults =
    selectedTicket !== undefined && queryClient.getQueryData(selectedRfiKey) !== undefined;
  const rfiResultsQuery = useQuery({
    enabled:
      selectedTicket !== undefined &&
      selectedTicket.state !== "DRAFT_INTAKE" &&
      selectedTicket.state !== "INFO_REQUIRED" &&
      selectedTicket.state !== "RFI_SEARCHING" &&
      !hasCachedRfiResults,
    queryFn: () => getRfiSearchResults(selectedTicketId),
    queryKey: selectedRfiKey,
  });
  const similarNoticeQuery = useQuery({
    enabled: similarNoticeEligible,
    queryFn: () => getSimilarRequestNotice(selectedTicketId),
    queryKey: ["similar-requests", "customer", selectedTicketId],
  });
  useEffect(() => setActionError(null), [selectedTicketId]);
  const mutations = useRequestWorkspaceMutations({
    allowCreate: isNewRequest,
    csrfToken,
    currentRouteTicketId: ticketId,
    selectedTicket,
    selectedTicketId,
    setActionError,
    setDismissedSimilarNoticeIds,
    setJourneyOpen,
  });
  const showWorkspace = isNewRequest || ticketId !== undefined;

  return (
    <div className="requests-page">
      <section className="overview-hero" aria-labelledby="requests-title">
        <div>
          <h1 id="requests-title">{showWorkspace ? "Request" : "My Requests"}</h1>
          <p>
            {showWorkspace
              ? "Describe what you need and the assistant will capture the details."
              : "Track your requests and open a new one when you need intelligence support."}
          </p>
        </div>
        {!showWorkspace && canCreate ? (
          <button
            className="store-action"
            onClick={() => void navigate("/app/requests/new")}
            type="button"
          >
            <MessageSquarePlus aria-hidden="true" size={18} />
            Open new request
          </button>
        ) : null}
        {!canCreate ? <div className="classification-note">MOCK DATA ONLY</div> : null}
      </section>
      {ticketsQuery.isError ? (
        <section className="surface">
          <ErrorState onRetry={() => void ticketsQuery.refetch()} />
        </section>
      ) : requestedTicketMissing ? (
        <RequestRouteMissingState onBack={() => void navigate("/app/requests")} />
      ) : existingTicketLoading ? (
        <section className="surface" aria-label="Request loading">
          <p role="status">Loading request…</p>
        </section>
      ) : showWorkspace ? (
        <TicketWorkspace
          actions={mutations.actions}
          actionError={actionError}
          currentUserId={session?.user.id ?? ""}
          journeyOpen={journeyOpen}
          onClearActionError={mutations.clearActionError}
          onJourneyToggle={setJourneyOpen}
          pending={mutations.pending}
          rfiError={rfiResultsQuery.isError}
          rfiLoading={rfiResultsQuery.isLoading}
          rfiResults={rfiResultsQuery.data}
          similarNotice={
            // Gate on the ticket's CURRENT eligible state, not on cached query data, so a
            // ticket that has left the eligible states (cancelled, closed) never shows a stale
            // notice or a live "Join as viewer" button from persisted react-query data.
            similarNoticeEligible
              ? {
                  isJoining: mutations.isJoiningSimilarRequest,
                  isLoading: similarNoticeQuery.isLoading,
                  isQueryError: similarNoticeQuery.isError,
                  notice: similarNoticeQuery.data,
                  onContinue: () =>
                    setDismissedSimilarNoticeIds((current) => [
                      ...new Set([...current, selectedTicketId]),
                    ]),
                  onJoin: mutations.joinSimilarRequest,
                  onRetry: () => void similarNoticeQuery.refetch(),
                }
              : undefined
          }
          ticket={selectedTicket}
        />
      ) : (
        <>
          {actionError ? (
            <div className="workspace-alert" role="alert">
              <span>{actionError}</span>
              <button onClick={mutations.clearActionError} type="button">
                Dismiss
              </button>
            </div>
          ) : null}
          {ticketsQuery.isLoading ? <LoadingState label="Loading your requests" /> : null}
          {!ticketsQuery.isLoading ? (
            <RequestDashboard
              canCreate={canCreate}
              currentUserId={session?.user.id ?? ""}
              isConfirming={mutations.isConfirmingDelivery}
              onConfirmDelivery={mutations.confirmDelivery}
              onOpen={(id) => void navigate(`/app/requests/${encodeURIComponent(id)}`)}
              tickets={tickets}
            />
          ) : null}
          {ticketsQuery.hasNextPage ? (
            <button
              className="secondary-action"
              disabled={ticketsQuery.isFetchingNextPage}
              onClick={() => void ticketsQuery.fetchNextPage()}
              type="button"
            >
              {ticketsQuery.isFetchingNextPage ? "Loading…" : "Load older requests"}
            </button>
          ) : null}
          <FeedbackPanel csrfToken={csrfToken} />
        </>
      )}
    </div>
  );
}
