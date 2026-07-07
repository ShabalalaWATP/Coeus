import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { MessageSquarePlus } from "lucide-react";
import { useEffect, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";

import { RequestDashboard } from "./RequestDashboard";
import { TicketWorkspace } from "./TicketWorkspace";
import { upsertTicket } from "./ticket-collection";
import { ErrorState } from "../../components/ui/PageState";
import { FeedbackPanel } from "../feedback/FeedbackPanel";
import {
  acceptProductOffer,
  getRfiSearchResults,
  rejectProductOffer,
  runRfiSearch,
  type RfiSearchResults,
} from "../../lib/api-client/rfi-search";
import {
  addTicketAttachment,
  addTicketCollaborator,
  addTicketInformation,
  cancelTicket,
  listTickets,
  removeTicketCollaborator,
  sendChatMessage,
  submitTicket,
  updateTicketIntake,
  type AttachmentMetadataInput,
  type IntakeUpdate,
  type Ticket,
} from "../../lib/api-client/tickets";
import { useAuth } from "../../lib/auth/auth-context";
import { hasPermissions } from "../../lib/permissions/route-access";

const EMPTY_TICKETS: Ticket[] = [];

export default function RequestsPage() {
  const { session } = useAuth();
  const { ticketId } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const isNewRequest = location.pathname.endsWith("/new");
  const [journeyOpen, setJourneyOpen] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const csrfToken = session?.csrfToken ?? "";
  const canCreate = session !== null && hasPermissions(session.user, ["chat:use"]);
  const ticketsQuery = useQuery({
    queryKey: ["tickets"],
    queryFn: listTickets,
    placeholderData: EMPTY_TICKETS,
  });
  const tickets = ticketsQuery.data ?? EMPTY_TICKETS;
  const selectedTicket = isNewRequest
    ? undefined
    : tickets.find((ticket) => ticket.id === ticketId);
  const selectedTicketId = selectedTicket?.id ?? "";
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
  useEffect(() => setActionError(null), [selectedTicketId]);

  const updateTicketCache = (ticket: Ticket) => {
    setActionError(null);
    queryClient.setQueryData<Ticket[]>(["tickets"], (current) => upsertTicket(current, ticket));
    if (ticket.id !== ticketId) {
      void navigate(`/app/requests/${encodeURIComponent(ticket.id)}`, { replace: true });
    }
  };
  const updateRfiCache = (result: RfiSearchResults) => {
    setActionError(null);
    queryClient.setQueryData(["rfi-search", result.ticketId], result);
    queryClient.setQueryData<Ticket[]>(["tickets"], (current) =>
      (current ?? EMPTY_TICKETS).map((ticket) =>
        ticket.id === result.ticketId
          ? {
              ...ticket,
              state: result.ticketState,
              visibleProductMatches: result.offers.map((offer) => offer.title),
            }
          : ticket,
      ),
    );
  };
  const failAction = (message: string) => () => setActionError(message);
  const clearActionError = () => setActionError(null);
  const chatMutation = useMutation({
    mutationFn: (message: string) =>
      sendChatMessage({ ticketId: selectedTicket?.id, message }, csrfToken),
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
      updateTicketCache(ticket);
      // Transient roadmap popup so the requester sees where their request goes next.
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
        ) : (
          <div className="classification-note">MOCK DATA ONLY</div>
        )}
      </section>
      {ticketsQuery.isError ? (
        <section className="surface">
          <ErrorState onRetry={() => void ticketsQuery.refetch()} />
        </section>
      ) : showWorkspace ? (
        <TicketWorkspace
          actions={{
            onAccept: (productId) => acceptOfferMutation.mutate(productId),
            onAddAttachment: (payload) => attachmentMutation.mutate(payload),
            onAddCollaborator: (username, access) =>
              addCollaboratorMutation.mutate({ username, access }),
            onAddInformation: (body) => informationMutation.mutate(body),
            onCancel: (reason) => cancelMutation.mutate(reason),
            onReject: (productId, reason) => rejectOfferMutation.mutate({ productId, reason }),
            onRemoveCollaborator: (userId) => removeCollaboratorMutation.mutate(userId),
            onRun: () => runRfiMutation.mutate(),
            onSave: (payload) => intakeMutation.mutate(payload),
            onSend: (message) => chatMutation.mutate(message),
            onSubmit: () => submitMutation.mutate(),
          }}
          actionError={actionError}
          currentUserId={session?.user.id ?? ""}
          journeyOpen={journeyOpen}
          onClearActionError={clearActionError}
          onJourneyToggle={setJourneyOpen}
          pending={{
            accepting: acceptOfferMutation.isPending,
            adding: informationMutation.isPending,
            cancelling: cancelMutation.isPending,
            collaborating:
              addCollaboratorMutation.isPending || removeCollaboratorMutation.isPending,
            rejecting: rejectOfferMutation.isPending,
            running: runRfiMutation.isPending,
            saving: intakeMutation.isPending,
            sending: chatMutation.isPending,
            submitting: submitMutation.isPending,
          }}
          rfiLoading={rfiResultsQuery.isLoading}
          rfiResults={rfiResultsQuery.data}
          ticket={selectedTicket}
        />
      ) : (
        <>
          <RequestDashboard
            canCreate={canCreate}
            onOpen={(id) => void navigate(`/app/requests/${encodeURIComponent(id)}`)}
            tickets={tickets}
          />
          <FeedbackPanel csrfToken={csrfToken} />
        </>
      )}
    </div>
  );
}
