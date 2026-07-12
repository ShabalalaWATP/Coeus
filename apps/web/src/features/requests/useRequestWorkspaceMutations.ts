import { type InfiniteData, useMutation, useQueryClient } from "@tanstack/react-query";
import type { Dispatch, SetStateAction } from "react";
import { useNavigate } from "react-router-dom";

import type { TicketWorkspaceActions, TicketWorkspacePending } from "./TicketWorkspace";
import {
  acceptProductOffer,
  rejectProductOffer,
  runRfiSearch,
  type RfiSearchResults,
} from "../../lib/api-client/rfi-search";
import { joinSimilarRequest } from "../../lib/api-client/similar-requests";
import {
  addTicketAttachment,
  addTicketCollaborator,
  addTicketInformation,
  cancelTicket,
  chooseCollectOption,
  consentNoMatch,
  confirmTicketDelivery,
  removeTicketCollaborator,
  sendChatMessage,
  submitTicket,
  updateTicketIntake,
  type AttachmentMetadataInput,
  type IntakeUpdate,
  type Ticket,
  type TicketSummary,
  type TicketSummaryPage,
} from "../../lib/api-client/tickets";
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
  const failAction = (message: string) => (error: unknown) =>
    setActionError(actionErrorMessage(error, message));

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
  const joinSimilarMutation = useMutation({
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
  const runRfiMutation = useMutation({
    mutationFn: () => runRfiSearch(selectedTicketId, csrfToken),
    onError: failAction("The product search could not be started. Try again."),
    onMutate: clearActionError,
    onSuccess: updateRfiCache,
  });
  const acceptOfferMutation = useMutation({
    mutationFn: (productId: string) => acceptProductOffer(selectedTicketId, productId, csrfToken),
    onError: failAction("The product offer could not be accepted. Try again."),
    onMutate: clearActionError,
    onSuccess: updateRfiCache,
  });
  const rejectOfferMutation = useMutation({
    mutationFn: ({ productId, reason }: { productId: string; reason: string }) =>
      rejectProductOffer(selectedTicketId, productId, reason, csrfToken),
    onError: failAction("The product offer could not be rejected. Try again."),
    onMutate: clearActionError,
    onSuccess: updateRfiCache,
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
  const noMatchConsentMutation = useMutation({
    mutationFn: (taskAsNewRequest: boolean) =>
      consentNoMatch(selectedTicketId, taskAsNewRequest, csrfToken),
    onError: failAction("The tasking decision could not be recorded. Try again."),
    onMutate: clearActionError,
    onSuccess: updateTicketCache,
  });
  const collectChoiceMutation = useMutation({
    mutationFn: (analysed: boolean) => chooseCollectOption(selectedTicketId, analysed, csrfToken),
    onError: failAction("The collect choice could not be recorded. Try again."),
    onMutate: clearActionError,
    onSuccess: updateTicketCache,
  });
  const confirmDeliveryMutation = useMutation({
    mutationFn: (confirmTicketId: string) => confirmTicketDelivery(confirmTicketId, csrfToken),
    onError: failAction("Delivery could not be confirmed. Refresh and try again."),
    onMutate: clearActionError,
    onSuccess: (ticket) => {
      setActionError(null);
      queryClient.setQueryData(["tickets", "detail", ticket.id], ticket);
      updateTicketSummary(queryClient, ticketSummary(ticket));
    },
  });

  const actions: TicketWorkspaceActions = {
    onAccept: (productId) => acceptOfferMutation.mutate(productId),
    onAddAttachment: (payload, onSuccess) => attachmentMutation.mutate(payload, { onSuccess }),
    onAddCollaborator: (username, access, onSuccess) =>
      addCollaboratorMutation.mutate({ username, access }, { onSuccess }),
    onAddInformation: (body) => informationMutation.mutate(body),
    onCancel: (reason, onSuccess) => cancelMutation.mutate(reason, { onSuccess }),
    onCollectChoice: (analysed) => collectChoiceMutation.mutate(analysed),
    onNoMatchConsent: (taskAsNewRequest) => noMatchConsentMutation.mutate(taskAsNewRequest),
    onReject: (productId, reason) => rejectOfferMutation.mutate({ productId, reason }),
    onRemoveCollaborator: (userId) => removeCollaboratorMutation.mutate(userId),
    onRun: () => runRfiMutation.mutate(),
    onSave: (payload) => intakeMutation.mutate(payload),
    onSend: (message, onSuccess) => chatMutation.mutate(message, { onSuccess }),
    onSubmit: () => submitMutation.mutate(),
  };
  const pending: TicketWorkspacePending = {
    accepting: acceptOfferMutation.isPending,
    adding: informationMutation.isPending,
    attaching: attachmentMutation.isPending,
    cancelling: cancelMutation.isPending,
    choosingCollect: collectChoiceMutation.isPending,
    collaborating: addCollaboratorMutation.isPending || removeCollaboratorMutation.isPending,
    consenting: noMatchConsentMutation.isPending,
    rejecting: rejectOfferMutation.isPending,
    running: runRfiMutation.isPending,
    saving: intakeMutation.isPending,
    sending: chatMutation.isPending,
    submitting: submitMutation.isPending,
  };

  return {
    actions,
    clearActionError,
    confirmDelivery: (ticketId: string) => confirmDeliveryMutation.mutate(ticketId),
    isConfirmingDelivery: confirmDeliveryMutation.isPending,
    isJoiningSimilarRequest: joinSimilarMutation.isPending,
    joinSimilarRequest: (ticketId: string) => joinSimilarMutation.mutate(ticketId),
    pending,
  };
}

function withAcceptedProduct(current: string[], acceptedProductId: string | null) {
  if (acceptedProductId === null || current.includes(acceptedProductId)) {
    return current;
  }
  return [...current, acceptedProductId];
}

function updateTicketSummary(
  queryClient: ReturnType<typeof useQueryClient>,
  summary: TicketSummary,
) {
  queryClient.setQueryData<InfiniteData<TicketSummaryPage>>(["tickets"], (current) => {
    if (!current) return current;
    let found = false;
    const pages = current.pages.map((page) => ({
      ...page,
      tickets: page.tickets.map((ticket) => {
        if (ticket.id !== summary.id) return ticket;
        found = true;
        return summary;
      }),
    }));
    if (!found && pages[0]) pages[0] = { ...pages[0], tickets: [summary, ...pages[0].tickets] };
    return { ...current, pages };
  });
}

function updateTicketSummaryState(
  queryClient: ReturnType<typeof useQueryClient>,
  ticketId: string,
  state: Ticket["state"],
  releasedProductId: string | null,
) {
  queryClient.setQueryData<InfiniteData<TicketSummaryPage>>(["tickets"], (current) =>
    current
      ? {
          ...current,
          pages: current.pages.map((page) => ({
            ...page,
            tickets: page.tickets.map((ticket) =>
              ticket.id === ticketId
                ? {
                    ...ticket,
                    state,
                    releasedProductId: releasedProductId ?? ticket.releasedProductId,
                  }
                : ticket,
            ),
          })),
        }
      : current,
  );
}

function ticketSummary(ticket: Ticket): TicketSummary {
  return {
    id: ticket.id,
    reference: ticket.reference,
    requesterUserId: ticket.requesterUserId,
    state: ticket.state,
    title: ticket.intake.title,
    priority: ticket.intake.priority,
    isReadyForSubmission: ticket.isReadyForSubmission,
    collaboratorCount: ticket.collaborators.length,
    releasedProductId: ticket.releasedProductIds[0] ?? null,
    createdAt: ticket.createdAt,
    updatedAt: ticket.updatedAt,
  };
}
