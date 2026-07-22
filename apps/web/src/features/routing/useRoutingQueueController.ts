import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import type { RoutingDetailActions, RoutingDetailState } from "./RoutingDetailPanel";
import { isRouteOverride, upsertRoutingTicket } from "./routing-model";
import { QUEUE_LABELS, TEAM_QUEUE_STATES } from "./routing-queue-config";
import {
  approveRoute,
  decideJiocReanalysis,
  decideManagerReanalysis,
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
  markRoutingDuplicate,
} from "../../lib/api-client/similar-requests";
import { useAuth } from "../../lib/auth/auth-context";
import { useActionError } from "../../lib/mutations/action-error";

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

export function useRoutingQueueController(queueKind: RoutingQueueKind) {
  const { session } = useAuth();
  const queryClient = useQueryClient();
  const csrfToken = session?.csrfToken ?? "";
  const isJioc = queueKind === "jioc";
  const catalogueRoute: RoutingRoute = queueKind === "jioc" ? "rfa" : queueKind;
  const [selectedTicketId, setSelectedTicketId] = useState<string>();
  const [decisionRoute, setDecisionRoute] = useState<RoutingRoute>("rfa");
  const [clarificationReason, setClarificationReason] = useState("");
  const [clarificationQuestion, setClarificationQuestion] = useState("");
  const [rejectReason, setRejectReason] = useState("");
  const [overrideReason, setOverrideReason] = useState("");
  const [reanalysisRationale, setReanalysisRationale] = useState("");
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
  const reanalysisMutation = useMutation({
    mutationFn: (decision: "agree" | "refer_to_jioc" | "reanalyse" | "close") => {
      const rationale = reanalysisRationale.trim();
      return isJioc
        ? decideJiocReanalysis(
            selectedTicket.ticketId,
            decision as "reanalyse" | "close",
            rationale,
            csrfToken,
          )
        : decideManagerReanalysis(
            selectedTicket.ticketId,
            decision as "agree" | "refer_to_jioc",
            rationale,
            csrfToken,
          );
    },
    onError: failActionWith("The re-analysis decision could not be recorded. Try again."),
    onMutate: clearActionError,
    onSuccess: (ticket) => {
      setReanalysisRationale("");
      updateQueue(ticket);
    },
  });
  const linkSimilarMutation = useMutation({
    mutationFn: (relatedTicketId: string) => {
      if (selectedTicket === undefined) throw new Error("No ticket selected.");
      return linkRoutingSimilarRequest(selectedTicket.ticketId, relatedTicketId, csrfToken);
    },
    onError: failActionWith("The related request could not be linked. Try again."),
    onMutate: clearActionError,
    onSuccess: (matches) => queryClient.setQueryData(selectedSimilarKey, matches),
  });
  const duplicateMutation = useMutation({
    mutationFn: ({
      relatedTicketId,
      withdrawSource,
    }: {
      relatedTicketId: string;
      withdrawSource: boolean;
    }) => {
      if (selectedTicket === undefined) throw new Error("No ticket selected.");
      return markRoutingDuplicate(
        selectedTicket.ticketId,
        relatedTicketId,
        withdrawSource,
        csrfToken,
      );
    },
    onError: failActionWith("The duplicate request action could not be completed. Try again."),
    onMutate: clearActionError,
    onSuccess: (matches, variables) => {
      queryClient.setQueryData(selectedSimilarKey, matches);
      if (variables.withdrawSource && selectedTicket) removeTicket(selectedTicket.ticketId);
    },
  });
  const actionPending = [
    runMutation,
    approveMutation,
    rejectMutation,
    clarificationMutation,
    linkSimilarMutation,
    duplicateMutation,
    reanalysisMutation,
  ].some((mutation) => mutation.isPending);
  const selectTicket = (ticketId: string) => {
    if (actionPending) return;
    setSelectedTicketId(ticketId);
    setDecisionRoute("rfa");
    setClarificationReason("");
    setClarificationQuestion("");
    setRejectReason("");
    setOverrideReason("");
    setReanalysisRationale("");
    clearActionError();
  };
  const detailActions: RoutingDetailActions = {
    onApprove: () => approveMutation.mutate(),
    onAssigned: (task) => removeTicket(task.ticketId),
    onClarificationQuestionChange: setClarificationQuestion,
    onClarificationReasonChange: setClarificationReason,
    onDecisionRouteChange: setDecisionRoute,
    onLinkSimilar: (id) => linkSimilarMutation.mutate(id),
    onManagerDecision: updateQueue,
    onMarkDuplicate: (id, withdrawSource) =>
      duplicateMutation.mutate({ relatedTicketId: id, withdrawSource }),
    onOverrideReasonChange: setOverrideReason,
    onReanalysisDecision: (decision) => reanalysisMutation.mutate(decision),
    onReanalysisRationaleChange: setReanalysisRationale,
    onReject: () => rejectMutation.mutate(),
    onRejectReasonChange: setRejectReason,
    onRequestClarification: () => clarificationMutation.mutate(),
    onRetrySimilar: () => void similarRequestsQuery.refetch(),
    onRunReviews: () => runMutation.mutate(),
  };
  const detailState: RoutingDetailState = {
    actionError,
    actionPending,
    canDecide: isJioc,
    clarificationQuestion,
    clarificationReason,
    csrfToken,
    decisionRoute,
    isApprovePending: approveMutation.isPending,
    isLinkingSimilar: linkSimilarMutation.isPending || duplicateMutation.isPending,
    isRunningReviews: runMutation.isPending,
    isSimilarLoading: similarRequestsQuery.isLoading,
    isSimilarQueryError: similarRequestsQuery.isError,
    overrideReason,
    rejectReason,
    reanalysisPending: reanalysisMutation.isPending,
    reanalysisRationale,
    route: isJioc ? decisionRoute : queueKind,
    selectedTicket,
    similarMatches: similarRequestsQuery.data,
  };

  return {
    actionPending,
    catalogueRoute,
    detailActions,
    detailState,
    isJioc,
    labels: QUEUE_LABELS[queueKind],
    olderQueueMutation,
    queue,
    queueQuery,
    selectTicket,
    selectedTicket,
  };
}
