import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { MessageSquarePlus } from "lucide-react";
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

  const updateTicketCache = (ticket: Ticket) => {
    queryClient.setQueryData<Ticket[]>(["tickets"], (current) => upsertTicket(current, ticket));
    if (ticket.id !== ticketId) {
      void navigate(`/app/requests/${ticket.id}`, { replace: true });
    }
  };
  const updateRfiCache = (result: RfiSearchResults) => {
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
  const chatMutation = useMutation({
    mutationFn: (message: string) =>
      sendChatMessage({ ticketId: selectedTicket?.id, message }, csrfToken),
    onSuccess: updateTicketCache,
  });
  const intakeMutation = useMutation({
    mutationFn: (payload: IntakeUpdate) => updateTicketIntake(selectedTicketId, payload, csrfToken),
    onSuccess: updateTicketCache,
  });
  const submitMutation = useMutation({
    mutationFn: () => submitTicket(selectedTicketId, csrfToken),
    onSuccess: updateTicketCache,
  });
  const attachmentMutation = useMutation({
    mutationFn: (payload: AttachmentMetadataInput) =>
      addTicketAttachment(selectedTicketId, payload, csrfToken),
    onSuccess: updateTicketCache,
  });
  const informationMutation = useMutation({
    mutationFn: (body: string) => addTicketInformation(selectedTicketId, body, csrfToken),
    onSuccess: updateTicketCache,
  });
  const runRfiMutation = useMutation({
    mutationFn: () => runRfiSearch(selectedTicketId, csrfToken),
    onSuccess: updateRfiCache,
  });
  const acceptOfferMutation = useMutation({
    mutationFn: (productId: string) => acceptProductOffer(selectedTicketId, productId, csrfToken),
    onSuccess: updateRfiCache,
  });
  const rejectOfferMutation = useMutation({
    mutationFn: ({ productId, reason }: { productId: string; reason: string }) =>
      rejectProductOffer(selectedTicketId, productId, reason, csrfToken),
    onSuccess: updateRfiCache,
  });
  const addCollaboratorMutation = useMutation({
    mutationFn: ({ username, access }: { username: string; access: "editor" | "viewer" }) =>
      addTicketCollaborator(selectedTicketId, username, access, csrfToken),
    onSuccess: updateTicketCache,
  });
  const removeCollaboratorMutation = useMutation({
    mutationFn: (userId: string) => removeTicketCollaborator(selectedTicketId, userId, csrfToken),
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
            onReject: (productId, reason) => rejectOfferMutation.mutate({ productId, reason }),
            onRemoveCollaborator: (userId) => removeCollaboratorMutation.mutate(userId),
            onRun: () => runRfiMutation.mutate(),
            onSave: (payload) => intakeMutation.mutate(payload),
            onSend: (message) => chatMutation.mutate(message),
            onSubmit: () => submitMutation.mutate(),
          }}
          currentUserId={session?.user.id ?? ""}
          pending={{
            accepting: acceptOfferMutation.isPending,
            adding: informationMutation.isPending,
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
            onOpen={(id) => void navigate(`/app/requests/${id}`)}
            tickets={tickets}
          />
          <FeedbackPanel csrfToken={csrfToken} />
        </>
      )}
    </div>
  );
}
