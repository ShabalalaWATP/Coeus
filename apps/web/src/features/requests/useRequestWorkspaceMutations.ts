import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { Dispatch, SetStateAction } from "react";
import { useNavigate } from "react-router-dom";

import type { TicketWorkspaceActions, TicketWorkspacePending } from "./TicketWorkspace";
import { useRequestDecisionMutations } from "./useRequestDecisionMutations";
import {
  ticketSummary,
  updateTicketSummary,
  updateTicketSummaryState,
  withAcceptedProduct,
} from "./request-summary-updates";
import type { RfiSearchResults } from "../../lib/api-client/rfi-search";
import {
  addTicketAttachment,
  addTicketCollaborator,
  addTicketInformation,
  cancelTicket,
  reopenTicketConversation,
  removeTicketCollaborator,
  sendChatMessage,
  submitTicket,
  updateTicketIntake,
  type AttachmentMetadataInput,
  type IntakeUpdate,
  type Ticket,
} from "../../lib/api-client/tickets";
import { ApiError } from "../../lib/api-client/client";
import { actionErrorMessage } from "../../lib/mutations/action-error";

type UseRequestWorkspaceMutationsInput = {
  allowCreate: boolean;
  csrfToken: string;
  currentRouteTicketId?: string;
  selectedTicket?: Ticket;
  selectedTicketId: string;
  setActionError: Dispatch<SetStateAction<string | null>>;
  setDismissedSimilarNoticeIds: Dispatch<SetStateAction<string[]>>;
  setJourneyOpen: (open: boolean) => void;
};

export function useRequestWorkspaceMutations({
  allowCreate,
  csrfToken,
  currentRouteTicketId,
  selectedTicket,
  selectedTicketId,
  setActionError,
  setDismissedSimilarNoticeIds,
  setJourneyOpen,
}: UseRequestWorkspaceMutationsInput) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const clearActionError = () => setActionError(null);
  const failAction = (message: string) => (error: unknown) => {
    setActionError(actionErrorMessage(error, message));
    if (error instanceof ApiError && error.status === 409) {
      void queryClient.invalidateQueries({ queryKey: ["tickets", "detail", selectedTicketId] });
      void queryClient.invalidateQueries({ queryKey: ["tickets"] });
    }
  };

  const updateTicketCache = (ticket: Ticket) => {
    setActionError(null);
    queryClient.setQueryData(["tickets", "detail", ticket.id], ticket);
    updateTicketSummary(queryClient, ticketSummary(ticket));
    if (ticket.id !== currentRouteTicketId) {
      void navigate(`/app/requests/${encodeURIComponent(ticket.id)}`, { replace: true });
    }
  };
  const updateRfiCache = (result: RfiSearchResults) => {
    setActionError(null);
    queryClient.setQueryData(["rfi-search", result.ticketId], result);
    queryClient.setQueryData<Ticket>(["tickets", "detail", result.ticketId], (ticket) =>
      ticket
        ? {
            ...ticket,
            state: result.ticketState,
            visibleProductMatches: result.offers.map((offer) => offer.title),
            releasedProductIds: withAcceptedProduct(
              ticket.releasedProductIds,
              result.metrics?.acceptedProductId ?? null,
            ),
          }
        : ticket,
    );
    updateTicketSummaryState(
      queryClient,
      result.ticketId,
      result.ticketState,
      result.metrics?.acceptedProductId ?? null,
    );
  };

  const chatMutation = useMutation({
    mutationFn: (message: string) => {
      if (!allowCreate && selectedTicket === undefined) {
        throw new Error("The requested ticket has not loaded.");
      }
      return sendChatMessage({ ticketId: selectedTicket?.id, message }, csrfToken);
    },
    onError: failAction("The message could not be sent. Try again."),
    onMutate: clearActionError,
    onSuccess: updateTicketCache,
  });
  const intakeMutation = useMutation({
    mutationFn: (payload: IntakeUpdate) => updateTicketIntake(selectedTicketId, payload, csrfToken),
    onError: failAction("The request details could not be saved. Refresh and try again."),
    onMutate: clearActionError,
    onSuccess: updateTicketCache,
  });
  const reopenConversationMutation = useMutation({
    mutationFn: () => reopenTicketConversation(selectedTicketId, csrfToken),
    onError: failAction("The conversation could not be reopened. Refresh and try again."),
    onMutate: clearActionError,
    onSuccess: updateTicketCache,
  });
  const submitMutation = useMutation({
    mutationFn: () => submitTicket(selectedTicketId, csrfToken),
    onError: failAction("The request could not be submitted. Check the details and try again."),
    onMutate: clearActionError,
    onSuccess: (ticket) => {
      setDismissedSimilarNoticeIds((current) => current.filter((id) => id !== ticket.id));
      updateTicketCache(ticket);
      void queryClient.invalidateQueries({
        queryKey: ["similar-requests", "customer", ticket.id],
      });
      setJourneyOpen(true);
    },
  });
  const attachmentMutation = useMutation({
    mutationFn: (payload: AttachmentMetadataInput) =>
      addTicketAttachment(selectedTicketId, payload, csrfToken),
    onError: failAction("Attachment metadata could not be added. Try again."),
    onMutate: clearActionError,
    onSuccess: updateTicketCache,
  });
  const informationMutation = useMutation({
    mutationFn: (body: string) => addTicketInformation(selectedTicketId, body, csrfToken),
    onError: failAction("Additional information could not be added. Try again."),
    onMutate: clearActionError,
    onSuccess: updateTicketCache,
  });
  const addCollaboratorMutation = useMutation({
    mutationFn: ({ username, access }: { username: string; access: "editor" | "viewer" }) =>
      addTicketCollaborator(selectedTicketId, username, access, csrfToken),
    onError: failAction("The user could not be tagged on this request. Try again."),
    onMutate: clearActionError,
    onSuccess: updateTicketCache,
  });
  const removeCollaboratorMutation = useMutation({
    mutationFn: (userId: string) => removeTicketCollaborator(selectedTicketId, userId, csrfToken),
    onError: failAction("The tagged user could not be removed. Try again."),
    onMutate: clearActionError,
    onSuccess: updateTicketCache,
  });
  const cancelMutation = useMutation({
    mutationFn: (reason: string) => cancelTicket(selectedTicketId, reason, csrfToken),
    onError: failAction("The request could not be cancelled. Refresh and try again."),
    onMutate: clearActionError,
    onSuccess: updateTicketCache,
  });
  const decisions = useRequestDecisionMutations({
    clearActionError,
    csrfToken,
    failAction,
    onProductOutcome: (ticket) => {
      setActionError(null);
      queryClient.setQueryData(["tickets", "detail", ticket.id], ticket);
      updateTicketSummary(queryClient, ticketSummary(ticket));
    },
    onRfiUpdate: updateRfiCache,
    onTicketUpdate: updateTicketCache,
    selectedTicketId,
    setDismissedSimilarNoticeIds,
  });

  const actions: TicketWorkspaceActions = {
    onAccept: (productId) => decisions.acceptOffer.mutate(productId),
    onAddAttachment: (payload, onSuccess) => attachmentMutation.mutate(payload, { onSuccess }),
    onAddCollaborator: (username, access, onSuccess) =>
      addCollaboratorMutation.mutate({ username, access }, { onSuccess }),
    onAddInformation: (body) => informationMutation.mutate(body),
    onCancel: (reason, onSuccess) => cancelMutation.mutate(reason, { onSuccess }),
    onCollectChoice: (analysed) => decisions.collectChoice.mutate(analysed),
    onNoMatchConsent: (taskAsNewRequest) => decisions.noMatchConsent.mutate(taskAsNewRequest),
    onReject: (productId, reason) => decisions.rejectOffer.mutate({ productId, reason }),
    onRemoveCollaborator: (userId) => removeCollaboratorMutation.mutate(userId),
    onReopenConversation: () => reopenConversationMutation.mutate(),
    onRun: () => decisions.runRfi.mutate(),
    onSave: (payload, onSuccess) => intakeMutation.mutate(payload, { onSuccess }),
    onSend: (message, onSuccess) => chatMutation.mutate(message, { onSuccess }),
    onSubmit: () => submitMutation.mutate(),
  };
  const pending: TicketWorkspacePending = {
    accepting: decisions.acceptOffer.isPending,
    adding: informationMutation.isPending,
    attaching: attachmentMutation.isPending,
    cancelling: cancelMutation.isPending,
    choosingCollect: decisions.collectChoice.isPending,
    collaborating: addCollaboratorMutation.isPending || removeCollaboratorMutation.isPending,
    consenting: decisions.noMatchConsent.isPending,
    rejecting: decisions.rejectOffer.isPending,
    reopening: reopenConversationMutation.isPending,
    running: decisions.runRfi.isPending,
    saving: intakeMutation.isPending,
    sending: chatMutation.isPending,
    submitting: submitMutation.isPending,
  };

  return {
    actions,
    clearActionError,
    decideProductOutcome: (
      ticketId: string,
      meetsRequirement: boolean,
      reason: string,
      unmetCriteria: string[],
    ) => decisions.productOutcome.mutate({ ticketId, meetsRequirement, reason, unmetCriteria }),
    isDecidingProductOutcome: decisions.productOutcome.isPending,
    isResolvingSimilarRequest:
      decisions.joinSimilar.isPending || decisions.continueSimilar.isPending,
    continueAfterSimilarRequest: () => decisions.continueSimilar.mutate(),
    joinSimilarRequest: (ticketId: string) => decisions.joinSimilar.mutate(ticketId),
    retryActiveWorkSearch: () => decisions.retryActiveWork.mutate(),
    pending,
  };
}
