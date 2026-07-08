import { ArrowLeft, History, Route, SlidersHorizontal } from "lucide-react";
import { Link } from "react-router-dom";

import { CancelRequestPanel } from "./CancelRequestPanel";
import { ChatPanel } from "./ChatPanel";
import { CollaboratorsPanel } from "./CollaboratorsPanel";
import { DetailsChecklist } from "./DetailsChecklist";
import { IntakePanel } from "./IntakePanel";
import { ProductOffersPanel } from "./ProductOffersPanel";
import { RequestJourney } from "./RequestJourney";
import { SimilarRequestNoticePanel } from "./SimilarRequestNoticePanel";
import { TimelinePanel } from "./TimelinePanel";
import { StatusPill } from "../../components/ui/StatusPill";
import type { RfiSearchResults } from "../../lib/api-client/rfi-search";
import type { SimilarRequestNotice } from "../../lib/api-client/similar-requests";
import type { AttachmentMetadataInput, IntakeUpdate, Ticket } from "../../lib/api-client/tickets";

const INTAKE_STATES = new Set(["DRAFT_INTAKE", "INFO_REQUIRED"]);
const CANCELABLE_STATES = new Set([
  "DRAFT_INTAKE",
  "INFO_REQUIRED",
  "RFI_SEARCHING",
  "RFI_MATCH_OFFERED",
  "ROUTE_ASSESSMENT",
  "RFA_MANAGER_REVIEW",
  "CM_MANAGER_REVIEW",
  "ANALYST_ASSIGNMENT",
  "ANALYST_IN_PROGRESS",
  "QC_REVIEW",
  "REWORK_REQUIRED",
  "MANAGER_RELEASE",
]);

type TicketWorkspaceActions = {
  onAccept: (productId: string) => void;
  onAddAttachment: (payload: AttachmentMetadataInput) => void;
  onAddCollaborator: (username: string, access: "editor" | "viewer") => void;
  onAddInformation: (body: string) => void;
  onCancel: (reason: string) => void;
  onReject: (productId: string, reason: string) => void;
  onRemoveCollaborator: (userId: string) => void;
  onRun: () => void;
  onSave: (payload: IntakeUpdate) => void;
  onSend: (message: string) => void;
  onSubmit: () => void;
};

type TicketWorkspaceProps = {
  actions: TicketWorkspaceActions;
  actionError: string | null;
  currentUserId: string;
  journeyOpen: boolean;
  onClearActionError: () => void;
  onJourneyToggle: (open: boolean) => void;
  pending: Record<
    | "accepting"
    | "collaborating"
    | "cancelling"
    | "adding"
    | "rejecting"
    | "running"
    | "saving"
    | "sending"
    | "submitting",
    boolean
  >;
  rfiError?: boolean;
  rfiLoading: boolean;
  rfiResults?: RfiSearchResults;
  similarNotice?: {
    isJoining: boolean;
    isLoading: boolean;
    isQueryError: boolean;
    notice?: SimilarRequestNotice;
    onContinue: () => void;
    onJoin: (ticketId: string) => void;
    onRetry: () => void;
  };
  ticket?: Ticket;
};

export function TicketWorkspace({
  actions,
  actionError,
  currentUserId,
  journeyOpen,
  onClearActionError,
  onJourneyToggle,
  pending,
  rfiError = false,
  rfiLoading,
  rfiResults,
  similarNotice,
  ticket,
}: TicketWorkspaceProps) {
  const isOwner = ticket !== undefined && ticket.requesterUserId === currentUserId;
  const isEditor =
    ticket !== undefined &&
    ticket.collaborators.some(
      (collaborator) => collaborator.userId === currentUserId && collaborator.access === "editor",
    );
  const canEdit = ticket === undefined || isOwner || isEditor;
  const showIntakeTools = ticket === undefined || INTAKE_STATES.has(ticket.state);
  const showOffers = ticket !== undefined && !INTAKE_STATES.has(ticket.state);
  const canCancel = ticket !== undefined && isOwner && CANCELABLE_STATES.has(ticket.state);

  return (
    <div className="ticket-workspace">
      <div className="ticket-workspace__bar">
        <Link className="store-action store-action--secondary" to="/app/requests">
          <ArrowLeft aria-hidden="true" size={18} />
          Back to my requests
        </Link>
        {ticket ? (
          <div className="ticket-workspace__meta">
            <span className="mono-ref">{ticket.reference}</span>
            <StatusPill state={ticket.state} />
            <button className="journey-trigger" onClick={() => onJourneyToggle(true)} type="button">
              <Route aria-hidden="true" size={15} />
              Request journey
            </button>
          </div>
        ) : null}
      </div>
      {journeyOpen && ticket ? (
        <RequestJourney onClose={() => onJourneyToggle(false)} state={ticket.state} />
      ) : null}
      {actionError ? (
        <div className="workspace-alert" role="alert">
          <span>{actionError}</span>
          <button onClick={onClearActionError} type="button">
            Dismiss
          </button>
        </div>
      ) : null}

      <section className="request-workspace" aria-label="Request workspace">
        <ChatPanel
          isSending={pending.sending}
          onSend={actions.onSend}
          readOnly={!canEdit || (ticket !== undefined && !showIntakeTools)}
          ticket={ticket}
        />
        <div className="request-side-panel">
          {ticket ? <DetailsChecklist ticket={ticket} /> : null}
          {ticket && showIntakeTools && canEdit ? (
            <details className="workspace-details">
              <summary>
                <SlidersHorizontal aria-hidden="true" size={16} />
                Edit details manually
              </summary>
              <IntakePanel
                isSaving={pending.saving}
                isSubmitting={pending.submitting}
                onAddAttachment={actions.onAddAttachment}
                onSave={actions.onSave}
                onSubmit={actions.onSubmit}
                ticket={ticket}
              />
            </details>
          ) : null}
          {ticket && isOwner && similarNotice ? (
            <SimilarRequestNoticePanel
              isJoining={similarNotice.isJoining}
              isLoading={similarNotice.isLoading}
              isQueryError={similarNotice.isQueryError}
              notice={similarNotice.notice}
              onContinue={similarNotice.onContinue}
              onJoin={similarNotice.onJoin}
              onRetry={similarNotice.onRetry}
            />
          ) : null}
          {showOffers ? (
            <ProductOffersPanel
              isAccepting={pending.accepting}
              isError={rfiError}
              isLoading={rfiLoading}
              isRejecting={pending.rejecting}
              isRunning={pending.running}
              onAccept={actions.onAccept}
              onReject={actions.onReject}
              onRun={actions.onRun}
              results={rfiResults}
              ticket={ticket}
            />
          ) : null}
          {ticket ? (
            <CollaboratorsPanel
              isOwner={isOwner}
              isPending={pending.collaborating}
              onAdd={actions.onAddCollaborator}
              onRemove={actions.onRemoveCollaborator}
              ticket={ticket}
            />
          ) : null}
          {canCancel ? (
            <CancelRequestPanel isCancelling={pending.cancelling} onCancel={actions.onCancel} />
          ) : null}
        </div>
      </section>

      {ticket ? (
        <details className="workspace-details">
          <summary>
            <History aria-hidden="true" size={16} />
            Request history
          </summary>
          <TimelinePanel
            isAdding={pending.adding}
            onAddInformation={actions.onAddInformation}
            ticket={ticket}
          />
        </details>
      ) : null}
    </div>
  );
}
