import { MessageCircleQuestion } from "lucide-react";

import { AssignAnalystPanel } from "./AssignAnalystPanel";
import { AdvisoryEvidencePanel } from "./AdvisoryEvidencePanel";
import { ManagerApprovalPanel } from "./ManagerApprovalPanel";
import { SimilarRequestsPanel } from "./SimilarRequestsPanel";
import { ReanalysisDecisionPanel } from "./ReanalysisDecisionPanel";
import { RoutingPriorityAssessment } from "./RoutingPriorityAssessment";
import {
  canApprove,
  canApproveWithOverride,
  canReject,
  canSubmitClarification,
  isRouteOverride,
} from "./routing-model";
import { PlanUpdates, Recommendation, Review } from "./routing-sections";
import { EmptyState } from "../../components/ui/PageState";
import { StatusPill } from "../../components/ui/StatusPill";
import type { AnalystTask } from "../../lib/api-client/analyst";
import type { RoutingRoute, RoutingTicket } from "../../lib/api-client/routing";
import type { SimilarRequestList } from "../../lib/api-client/similar-requests";

export type RoutingDetailState = {
  actionError: string | null;
  actionPending: boolean;
  canDecide: boolean;
  clarificationQuestion: string;
  clarificationReason: string;
  csrfToken: string;
  decisionRoute: RoutingRoute;
  isApprovePending: boolean;
  isLinkingSimilar: boolean;
  isRunningReviews: boolean;
  isSimilarLoading: boolean;
  isSimilarQueryError: boolean;
  overrideReason: string;
  rejectReason: string;
  reanalysisPending: boolean;
  reanalysisRationale: string;
  route: RoutingRoute;
  selectedTicket: RoutingTicket | undefined;
  similarMatches: SimilarRequestList | undefined;
};

export type RoutingDetailActions = {
  onApprove: () => void;
  onAssigned: (task: AnalystTask) => void;
  onClarificationQuestionChange: (value: string) => void;
  onClarificationReasonChange: (value: string) => void;
  onDecisionRouteChange: (route: RoutingRoute) => void;
  onLinkSimilar: (ticketId: string) => void;
  onMarkDuplicate: (ticketId: string, withdrawSource: boolean) => void;
  onManagerDecision: (ticket: RoutingTicket) => void;
  onOverrideReasonChange: (value: string) => void;
  onReject: () => void;
  onReanalysisDecision: (decision: "agree" | "refer_to_jioc" | "reanalyse" | "close") => void;
  onReanalysisRationaleChange: (value: string) => void;
  onRejectReasonChange: (value: string) => void;
  onRequestClarification: () => void;
  onRetrySimilar: () => void;
  onRunReviews: () => void;
};

export function RoutingDetailPanel({
  actions,
  state,
}: {
  actions: RoutingDetailActions;
  state: RoutingDetailState;
}) {
  const {
    actionError,
    actionPending,
    canDecide,
    clarificationQuestion,
    clarificationReason,
    csrfToken,
    decisionRoute,
    isApprovePending,
    isLinkingSimilar,
    isRunningReviews,
    isSimilarLoading,
    isSimilarQueryError,
    overrideReason,
    rejectReason,
    reanalysisPending,
    reanalysisRationale,
    route,
    selectedTicket,
    similarMatches,
  } = state;
  const {
    onApprove,
    onAssigned,
    onClarificationQuestionChange,
    onClarificationReasonChange,
    onDecisionRouteChange,
    onLinkSimilar,
    onManagerDecision,
    onMarkDuplicate,
    onOverrideReasonChange,
    onReanalysisDecision,
    onReanalysisRationaleChange,
    onReject,
    onRejectReasonChange,
    onRequestClarification,
    onRetrySimilar,
    onRunReviews,
  } = actions;
  const isReanalysisDecision =
    selectedTicket?.state === "MANAGER_REANALYSIS_REVIEW" ||
    selectedTicket?.state === "JIOC_REANALYSIS_ADJUDICATION";
  if (selectedTicket && isReanalysisDecision) {
    return (
      <section className="surface routing-detail" aria-label="Re-analysis decision">
        <div className="section-heading">
          <h2>{selectedTicket.reference}</h2>
          <p>{selectedTicket.title}</p>
        </div>
        <StatusPill state={selectedTicket.state} />
        <ReanalysisDecisionPanel
          isJioc={selectedTicket.state === "JIOC_REANALYSIS_ADJUDICATION"}
          onDecide={onReanalysisDecision}
          onRationaleChange={onReanalysisRationaleChange}
          pending={reanalysisPending}
          rationale={reanalysisRationale}
          ticket={selectedTicket}
        />
        {actionError ? (
          <p className="auth-error" role="alert">
            {actionError}
          </p>
        ) : null}
      </section>
    );
  }
  return (
    <section
      className="surface routing-detail"
      aria-label={canDecide ? "Route recommendation" : "Team assignment and review"}
    >
      {selectedTicket ? (
        <>
          <div className="section-heading">
            <h2>{selectedTicket.reference}</h2>
            <p>{selectedTicket.title}</p>
          </div>
          <StatusPill state={selectedTicket.state} />
          <RoutingPriorityAssessment ticket={selectedTicket} />
          {!canDecide ? (
            <p className="workspace-alert" role="status">
              {`This request is already routed to the ${
                route === "cm" ? "Collection" : "RFA"
              } team. The recommendations below are retained as decision context.`}
            </p>
          ) : null}
          <Recommendation ticket={selectedTicket} />
          <AdvisoryEvidencePanel runs={selectedTicket.advisoryRuns} />
          <Review title="RFA recommendation" review={selectedTicket.rfaReview} />
          <Review title="CM recommendation" review={selectedTicket.cmReview} />
          <PlanUpdates ticket={selectedTicket} />
          {canDecide && selectedTicket.state === "JIOC_REVIEW" && !canApprove(selectedTicket) ? (
            <p className="workspace-alert" role="status">
              Run capability checks before approval. Both capability reviews and a route
              recommendation are required.
            </p>
          ) : null}
          <SimilarRequestsPanel
            isMutating={actionPending || isLinkingSimilar}
            isLoading={isSimilarLoading}
            isQueryError={isSimilarQueryError}
            matches={similarMatches}
            onLink={onLinkSimilar}
            onMarkDuplicate={onMarkDuplicate}
            onRetry={onRetrySimilar}
          />
          {canDecide && canApprove(selectedTicket) ? (
            <fieldset className="routing-override">
              <legend>Route decision</legend>
              <label>
                <input
                  checked={decisionRoute === "rfa"}
                  disabled={actionPending}
                  name="jioc-decision-route"
                  onChange={() => onDecisionRouteChange("rfa")}
                  type="radio"
                />
                Collection not required: route to RFA
              </label>
              <label>
                <input
                  checked={decisionRoute === "cm"}
                  disabled={actionPending}
                  name="jioc-decision-route"
                  onChange={() => onDecisionRouteChange("cm")}
                  type="radio"
                />
                Collection required: route to CM
              </label>
            </fieldset>
          ) : null}
          {canDecide && canApprove(selectedTicket) && isRouteOverride(selectedTicket, route) ? (
            <div className="routing-override">
              <label htmlFor="routing-override-reason">Override reason</label>
              <textarea
                id="routing-override-reason"
                disabled={actionPending}
                onChange={(event) => onOverrideReasonChange(event.target.value)}
                placeholder="Explain why the recommendation should not be followed."
                value={overrideReason}
              />
              <small>
                The orchestrator recommended a different route. An override reason of at least 3
                characters is required.
              </small>
            </div>
          ) : null}
          {canDecide ? (
            <div className="routing-actions">
              {selectedTicket.state === "JIOC_REVIEW" ? (
                <button
                  disabled={actionPending || isRunningReviews}
                  onClick={onRunReviews}
                  type="button"
                >
                  Run capability checks
                </button>
              ) : null}
              <button
                disabled={
                  !canApproveWithOverride(selectedTicket, route, overrideReason) ||
                  actionPending ||
                  isApprovePending
                }
                onClick={onApprove}
                type="button"
              >
                Approve route
              </button>
            </div>
          ) : null}
          {actionError ? (
            <p className="auth-error" role="alert">
              {actionError}
            </p>
          ) : null}
          {selectedTicket.state === "MANAGER_APPROVAL" && !canDecide ? (
            <ManagerApprovalPanel
              csrfToken={csrfToken}
              key={selectedTicket.ticketId}
              onDecided={onManagerDecision}
              route={route}
              ticketId={selectedTicket.ticketId}
            />
          ) : null}
          {selectedTicket.state === "ANALYST_ASSIGNMENT" && !canDecide ? (
            <AssignAnalystPanel
              csrfToken={csrfToken}
              key={selectedTicket.ticketId}
              onAssigned={onAssigned}
              route={route}
              suggestedTeamName={teamNameForAssignment(selectedTicket, route)}
              ticketId={selectedTicket.ticketId}
            />
          ) : canDecide ? (
            <details className="workspace-details">
              <summary>
                <MessageCircleQuestion aria-hidden="true" size={16} />
                Query or reject this route
              </summary>
              <div className="routing-forms">
                <label>
                  Clarification reason
                  <textarea
                    disabled={actionPending}
                    onChange={(event) => onClarificationReasonChange(event.target.value)}
                    value={clarificationReason}
                  />
                </label>
                <label>
                  Clarification question
                  <input
                    disabled={actionPending}
                    onChange={(event) => onClarificationQuestionChange(event.target.value)}
                    value={clarificationQuestion}
                  />
                </label>
                <button
                  disabled={
                    !canSubmitClarification(
                      selectedTicket,
                      clarificationReason,
                      clarificationQuestion,
                    ) || actionPending
                  }
                  onClick={onRequestClarification}
                  type="button"
                >
                  Request clarification
                </button>
                <label>
                  Rejection reason
                  <textarea
                    disabled={actionPending}
                    onChange={(event) => onRejectReasonChange(event.target.value)}
                    value={rejectReason}
                  />
                </label>
                <button
                  disabled={!canReject(selectedTicket, rejectReason) || actionPending}
                  onClick={onReject}
                  type="button"
                >
                  Reject route
                </button>
              </div>
            </details>
          ) : null}
        </>
      ) : (
        <EmptyState
          hint="Approved and routed tickets leave this queue automatically."
          title="No ticket selected"
        />
      )}
    </section>
  );
}

function teamNameForAssignment(ticket: RoutingTicket, route: RoutingRoute) {
  if (route === "rfa") {
    return ticket.rfaReview?.suggestedTeamName ?? "";
  }
  return ticket.cmReview?.suggestedCollectionTeamName ?? "";
}
