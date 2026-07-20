import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { Dispatch, SetStateAction } from "react";
import { useNavigate } from "react-router-dom";

import {
  acceptProductOffer,
  rejectProductOffer,
  runRfiSearch,
  type RfiSearchResults,
} from "../../lib/api-client/rfi-search";
import {
  continueAfterSimilarRequest,
  joinSimilarRequest,
  retryActiveWorkSearch,
} from "../../lib/api-client/similar-requests";
import {
  chooseCollectOption,
  consentNoMatch,
  decideProductOutcome,
  type Ticket,
} from "../../lib/api-client/tickets";

type FailureHandler = (message: string) => (error: unknown) => void;

type DecisionMutationInput = {
  clearActionError: () => void;
  csrfToken: string;
  failAction: FailureHandler;
  onProductOutcome: (ticket: Ticket) => void;
  onRfiUpdate: (result: RfiSearchResults) => void;
  onTicketUpdate: (ticket: Ticket) => void;
  selectedTicketId: string;
  setDismissedSimilarNoticeIds: Dispatch<SetStateAction<string[]>>;
};

export function useRequestDecisionMutations({
  clearActionError,
  csrfToken,
  failAction,
  onProductOutcome,
  onRfiUpdate,
  onTicketUpdate,
  selectedTicketId,
  setDismissedSimilarNoticeIds,
}: DecisionMutationInput) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const joinSimilar = useMutation({
    mutationFn: (relatedTicketId: string) =>
      joinSimilarRequest(selectedTicketId, relatedTicketId, csrfToken),
    onError: failAction("The similar request could not be joined. Try again."),
    onMutate: clearActionError,
    onSuccess: (joined) => {
      setDismissedSimilarNoticeIds((current) => [...new Set([...current, selectedTicketId])]);
      void queryClient.invalidateQueries({ queryKey: ["tickets"] });
      void navigate(`/app/requests/${encodeURIComponent(joined.joinedTicketId)}`);
    },
  });
  const continueSimilar = useMutation({
    mutationFn: () => continueAfterSimilarRequest(selectedTicketId, csrfToken),
    onError: failAction("The active-work decision could not be recorded. Try again."),
    onMutate: clearActionError,
    onSuccess: onTicketUpdate,
  });
  const retryActiveWork = useMutation({
    mutationFn: () => retryActiveWorkSearch(selectedTicketId, csrfToken),
    onError: failAction("The active-work search could not be completed. Try again."),
    onMutate: clearActionError,
    onSuccess: onTicketUpdate,
  });
  const runRfi = useMutation({
    mutationFn: () => runRfiSearch(selectedTicketId, csrfToken),
    onError: failAction("The product search could not be started. Try again."),
    onMutate: clearActionError,
    onSuccess: onRfiUpdate,
  });
  const acceptOffer = useMutation({
    mutationFn: (productId: string) => acceptProductOffer(selectedTicketId, productId, csrfToken),
    onError: failAction("The product offer could not be accepted. Try again."),
    onMutate: clearActionError,
    onSuccess: onRfiUpdate,
  });
  const rejectOffer = useMutation({
    mutationFn: ({ productId, reason }: { productId: string; reason: string }) =>
      rejectProductOffer(selectedTicketId, productId, reason, csrfToken),
    onError: failAction("The product offer could not be rejected. Try again."),
    onMutate: clearActionError,
    onSuccess: onRfiUpdate,
  });
  const noMatchConsent = useMutation({
    mutationFn: (taskAsNewRequest: boolean) =>
      consentNoMatch(selectedTicketId, taskAsNewRequest, csrfToken),
    onError: failAction("The tasking decision could not be recorded. Try again."),
    onMutate: clearActionError,
    onSuccess: onTicketUpdate,
  });
  const collectChoice = useMutation({
    mutationFn: (analysed: boolean) => chooseCollectOption(selectedTicketId, analysed, csrfToken),
    onError: failAction("The collect choice could not be recorded. Try again."),
    onMutate: clearActionError,
    onSuccess: onTicketUpdate,
  });
  const productOutcome = useMutation({
    mutationFn: ({
      ticketId,
      meetsRequirement,
      reason,
      unmetCriteria,
    }: {
      ticketId: string;
      meetsRequirement: boolean;
      reason: string;
      unmetCriteria: string[];
    }) => decideProductOutcome(ticketId, { meetsRequirement, reason, unmetCriteria }, csrfToken),
    onError: failAction("The product decision could not be recorded. Refresh and try again."),
    onMutate: clearActionError,
    onSuccess: onProductOutcome,
  });

  return {
    acceptOffer,
    collectChoice,
    continueSimilar,
    joinSimilar,
    noMatchConsent,
    productOutcome,
    rejectOffer,
    retryActiveWork,
    runRfi,
  };
}
