import { ArrowLeft, History, Route, SlidersHorizontal } from "lucide-react";
import { Link } from "react-router-dom";

import { CancelRequestPanel } from "./CancelRequestPanel";
import { ChatPanel } from "./ChatPanel";
import { CollaboratorsPanel } from "./CollaboratorsPanel";
import { CollectChoicePanel } from "./CollectChoicePanel";
import { IntakePanel } from "./IntakePanel";
import { NoMatchConsentPanel } from "./NoMatchConsentPanel";
import { ProductOffersPanel } from "./ProductOffersPanel";
import { RequestJourney } from "./RequestJourney";
import { SimilarRequestNoticePanel } from "./SimilarRequestNoticePanel";
import { SIMILAR_NOTICE_STATES } from "./request-state-sets";
import { TimelinePanel } from "./TimelinePanel";
import { StatusPill } from "../../components/ui/StatusPill";
import type { RfiSearchResults } from "../../lib/api-client/rfi-search";
import type { SimilarRequestNotice } from "../../lib/api-client/similar-requests";
import type { AttachmentMetadataInput, IntakeUpdate, Ticket } from "../../lib/api-client/tickets";
import { useAuth } from "../../lib/auth/auth-context";
import { hasPermissions } from "../../lib/permissions/route-access";

const INTAKE_STATES = new Set(["DRAFT_INTAKE", "INFO_REQUIRED"]);
const PRODUCT_OFFER_STATES = new Set(["RFI_SEARCHING", "RFI_MATCH_OFFERED", "RFI_NO_MATCH"]);
const CANCELABLE_STATES = new Set([
  "DRAFT_INTAKE",
  "INFO_REQUIRED",
  "RFI_SEARCHING",
  "RFI_MATCH_OFFERED",
  "RFI_NO_MATCH",
  "JIOC_REVIEW",
  "COLLECT_CHOICE",
  "ANALYST_ASSIGNMENT",
  "ANALYST_IN_PROGRESS",
  "MANAGER_APPROVAL",
  "QC_REVIEW",
  "REWORK_REQUIRED",
]);

export type TicketWorkspaceActions = {
  onAccept: (productId: string) => void;
  onAddAttachment: (payload: AttachmentMetadataInput, onSuccess?: () => void) => void;
  onAddCollaborator: (
    username: string,
    access: "editor" | "viewer",
    onSuccess?: () => void,
  ) => void;
  onAddInformation: (body: string) => void;
  onCancel: (reason: string, onSuccess?: () => void) => void;
  onCollectChoice: (analysed: boolean) => void;
  onNoMatchConsent: (taskAsNewRequest: boolean) => void;
  onReject: (productId: string, reason: string) => void;
  onRemoveCollaborator: (userId: string) => void;
  onRun: () => void;
  onSave: (payload: IntakeUpdate) => void;
  onSend: (message: string, onSuccess?: () => void) => void;
  onSubmit: () => void;
};

export type TicketWorkspacePending = Record<
  | "accepting"
  | "collaborating"
  | "cancelling"
  | "choosingCollect"
  | "consenting"
  | "adding"
  | "attaching"
  | "rejecting"
  | "running"
  | "saving"
  | "sending"
  | "submitting",
  boolean
>;

type TicketWorkspaceProps = {
  actions: TicketWorkspaceActions;
  actionError: string | null;
  currentUserId: string;
  journeyOpen: boolean;
  onClearActionError: () => void;
  onJourneyToggle: (open: boolean) => void;
  pending: TicketWorkspacePending;
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
  const { session } = useAuth();
  const isOwner = ticket !== undefined && ticket.requesterUserId === currentUserId;
  const isEditor =
    ticket !== undefined &&
    ticket.collaborators.some(
      (collaborator) => collaborator.userId === currentUserId && collaborator.access === "editor",
    );
  const canWriteAll = session !== null && hasPermissions(session.user, ["ticket:write_all"]);
  const canEdit = ticket === undefined || isOwner || isEditor || canWriteAll;
  const canSubmit =
    ticket === undefined ||
    isOwner ||
    (session !== null && hasPermissions(session.user, ["ticket:transition"]));
  const canAddInformation =
    canEdit && session !== null && hasPermissions(session.user, ["ticket:add_information"]);
  const canRunRfiSearch =
    canEdit && session !== null && hasPermissions(session.user, ["rfi:search"]);
  const showIntakeTools = ticket === undefined || INTAKE_STATES.has(ticket.state);
  const showOffers = ticket !== undefined && PRODUCT_OFFER_STATES.has(ticket.state);
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
            <strong className="ticket-workspace__title">{ticket.intake.title}</strong>
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
          csrfToken={session?.csrfToken ?? ""}
          isSending={pending.sending}
          onSend={actions.onSend}
          readOnly={!canEdit || (ticket !== undefined && !showIntakeTools)}
          ticket={ticket}
        />
        <div className="request-side-panel">
          {ticket && showIntakeTools && canEdit ? (
            <details className="workspace-details">
              <summary>
                <SlidersHorizontal aria-hidden="true" size={16} />
                Edit details manually
              </summary>
              <IntakePanel
                canSubmit={canSubmit}
                isAddingAttachment={pending.attaching}
                isSaving={pending.saving}
                isSubmitting={pending.submitting}
                onAddAttachment={actions.onAddAttachment}
                onSave={actions.onSave}
                onSubmit={actions.onSubmit}
                ticket={ticket}
              />
            </details>
          ) : null}
          {ticket && showIntakeTools && canSubmit && !canEdit ? (
            <section className="workspace-panel" aria-label="Request submission">
              <p>You can submit this request when all required details are complete.</p>
              <button
                disabled={!ticket.isReadyForSubmission || pending.submitting}
                onClick={() => void actions.onSubmit()}
                type="button"
              >
                {pending.submitting ? "Submitting..." : "Submit"}
              </button>
            </section>
          ) : null}
          {ticket && isOwner && similarNotice && SIMILAR_NOTICE_STATES.has(ticket.state) ? (
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
          {ticket && isOwner && ticket.state === "RFI_NO_MATCH" ? (
            <NoMatchConsentPanel
              isPending={pending.consenting}
              onConsent={actions.onNoMatchConsent}
            />
          ) : null}
          {ticket && isOwner && ticket.state === "COLLECT_CHOICE" ? (
            <CollectChoicePanel
              isPending={pending.choosingCollect}
              onChoose={actions.onCollectChoice}
            />
          ) : null}
          {showOffers ? (
            <ProductOffersPanel
              canManageOffers={isOwner}
              canRunSearch={canRunRfiSearch}
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
              isOwner={isOwner || canWriteAll}
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
            currentUserId={currentUserId}
            isAdding={pending.adding}
            onAddInformation={actions.onAddInformation}
            readOnly={!canAddInformation}
            ticket={ticket}
          />
        </details>
      ) : null}
    </div>
  );
}
