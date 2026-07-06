import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";

import { ChatPanel } from "./ChatPanel";
import { ErrorState } from "../../components/ui/PageState";
import { IntakePanel } from "./IntakePanel";
import { ProductOffersPanel } from "./ProductOffersPanel";
import { RequestDashboard } from "./RequestDashboard";
import { TimelinePanel } from "./TimelinePanel";
import { upsertTicket } from "./ticket-collection";
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
  addTicketInformation,
  listTickets,
  sendChatMessage,
  submitTicket,
  updateTicketIntake,
  type AttachmentMetadataInput,
  type IntakeUpdate,
  type Ticket,
} from "../../lib/api-client/tickets";
import { useAuth } from "../../lib/auth/auth-context";

const EMPTY_TICKETS: Ticket[] = [];

export default function RequestsPage() {
  const { session } = useAuth();
  const queryClient = useQueryClient();
  const [selectedTicketId, setSelectedTicketId] = useState<string>();
  const csrfToken = session?.csrfToken ?? "";
  const ticketsQuery = useQuery({
    queryKey: ["tickets"],
    queryFn: listTickets,
    placeholderData: EMPTY_TICKETS,
  });
  const tickets = useMemo(() => ticketsQuery.data ?? EMPTY_TICKETS, [ticketsQuery.data]);
  const selectedTicket = tickets.find((ticket) => ticket.id === selectedTicketId) ?? tickets[0];
  const selectedRfiKey = ["rfi-search", selectedTicket?.id] as const;
  const hasCachedRfiResults =
    selectedTicket !== undefined && queryClient.getQueryData(selectedRfiKey) !== undefined;
  const rfiResultsQuery = useQuery({
    enabled:
      selectedTicket !== undefined &&
      selectedTicket.state !== "DRAFT_INTAKE" &&
      selectedTicket.state !== "INFO_REQUIRED" &&
      selectedTicket.state !== "RFI_SEARCHING" &&
      !hasCachedRfiResults,
    queryFn: () => getRfiSearchResults(selectedTicket?.id ?? ""),
    queryKey: selectedRfiKey,
  });

  useEffect(() => {
    if (selectedTicketId === undefined && tickets[0] !== undefined) {
      setSelectedTicketId(tickets[0].id);
    }
  }, [selectedTicketId, tickets]);

  const updateTicketCache = (ticket: Ticket) => {
    queryClient.setQueryData<Ticket[]>(["tickets"], (current) => upsertTicket(current, ticket));
    setSelectedTicketId(ticket.id);
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
    setSelectedTicketId(result.ticketId);
  };
  const chatMutation = useMutation({
    mutationFn: (message: string) =>
      sendChatMessage({ ticketId: selectedTicket?.id, message }, csrfToken),
    onSuccess: updateTicketCache,
  });
  const intakeMutation = useMutation({
    mutationFn: (payload: IntakeUpdate) =>
      updateTicketIntake(selectedTicket.id, payload, csrfToken),
    onSuccess: updateTicketCache,
  });
  const submitMutation = useMutation({
    mutationFn: () => submitTicket(selectedTicket.id, csrfToken),
    onSuccess: updateTicketCache,
  });
  const attachmentMutation = useMutation({
    mutationFn: (payload: AttachmentMetadataInput) =>
      addTicketAttachment(selectedTicket.id, payload, csrfToken),
    onSuccess: updateTicketCache,
  });
  const informationMutation = useMutation({
    mutationFn: (body: string) => addTicketInformation(selectedTicket.id, body, csrfToken),
    onSuccess: updateTicketCache,
  });
  const runRfiMutation = useMutation({
    mutationFn: () => runRfiSearch(selectedTicket.id, csrfToken),
    onSuccess: updateRfiCache,
  });
  const acceptOfferMutation = useMutation({
    mutationFn: (productId: string) => acceptProductOffer(selectedTicket.id, productId, csrfToken),
    onSuccess: updateRfiCache,
  });
  const rejectOfferMutation = useMutation({
    mutationFn: ({ productId, reason }: { productId: string; reason: string }) =>
      rejectProductOffer(selectedTicket.id, productId, reason, csrfToken),
    onSuccess: updateRfiCache,
  });

  return (
    <div className="requests-page">
      <section className="overview-hero" aria-labelledby="requests-title">
        <div>
          <h1 id="requests-title">Requests</h1>
          <p>MOCK DATA ONLY ticket intake and customer request timeline.</p>
        </div>
        <div className="classification-note">MOCK DATA ONLY</div>
      </section>
      {ticketsQuery.isError ? (
        <section className="surface">
          <ErrorState onRetry={() => void ticketsQuery.refetch()} />
        </section>
      ) : null}
      <RequestDashboard
        onSelect={setSelectedTicketId}
        selectedTicketId={selectedTicket?.id}
        tickets={tickets}
      />
      <section className="request-workspace" aria-label="Ticket intake workspace">
        <ChatPanel
          isSending={chatMutation.isPending}
          onSend={(message) => chatMutation.mutate(message)}
          ticket={selectedTicket}
        />
        <div className="request-side-panel">
          <IntakePanel
            isSaving={intakeMutation.isPending}
            isSubmitting={submitMutation.isPending}
            onAddAttachment={(payload) => attachmentMutation.mutate(payload)}
            onSave={(payload) => intakeMutation.mutate(payload)}
            onSubmit={() => submitMutation.mutate()}
            ticket={selectedTicket}
          />
          <ProductOffersPanel
            isAccepting={acceptOfferMutation.isPending}
            isLoading={rfiResultsQuery.isLoading}
            isRejecting={rejectOfferMutation.isPending}
            isRunning={runRfiMutation.isPending}
            onAccept={(productId) => acceptOfferMutation.mutate(productId)}
            onReject={(productId, reason) => rejectOfferMutation.mutate({ productId, reason })}
            onRun={() => runRfiMutation.mutate()}
            results={rfiResultsQuery.data}
            ticket={selectedTicket}
          />
          <FeedbackPanel csrfToken={csrfToken} />
        </div>
      </section>
      <TimelinePanel
        isAdding={informationMutation.isPending}
        onAddInformation={(body) => informationMutation.mutate(body)}
        ticket={selectedTicket}
      />
    </div>
  );
}
