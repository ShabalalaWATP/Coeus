import { MessageCircleQuestion } from "lucide-react";

import { AssignAnalystPanel } from "./AssignAnalystPanel";
import { SimilarRequestsPanel } from "./SimilarRequestsPanel";
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

type RoutingDetailPanelProps = {
  actionError: string | null;
  clarificationQuestion: string;
  clarificationReason: string;
  csrfToken: string;
  isApprovePending: boolean;
  isLinkingSimilar: boolean;
  isRunningReviews: boolean;
  isSimilarLoading: boolean;
  isSimilarQueryError: boolean;
  onApprove: () => void;
  onAssigned: (task: AnalystTask) => void;
  onClarificationQuestionChange: (value: string) => void;
  onClarificationReasonChange: (value: string) => void;
  onLinkSimilar: (ticketId: string) => void;
  onOverrideReasonChange: (value: string) => void;
  onReject: () => void;
  onRejectReasonChange: (value: string) => void;
  onRequestClarification: () => void;
  onRetrySimilar: () => void;
  onRunReviews: () => void;
  overrideReason: string;
  rejectReason: string;
  route: RoutingRoute;
  selectedTicket: RoutingTicket | undefined;
  similarMatches: SimilarRequestList | undefined;
};

export function RoutingDetailPanel({
  actionError,
  clarificationQuestion,
  clarificationReason,
  csrfToken,
  isApprovePending,
  isLinkingSimilar,
  isRunningReviews,
  isSimilarLoading,
  isSimilarQueryError,
  onApprove,
  onAssigned,
  onClarificationQuestionChange,
  onClarificationReasonChange,
  onLinkSimilar,
  onOverrideReasonChange,
  onReject,
  onRejectReasonChange,
  onRequestClarification,
  onRetrySimilar,
  onRunReviews,
  overrideReason,
  rejectReason,
  route,
  selectedTicket,
  similarMatches,
}: RoutingDetailPanelProps) {
  return (
    <section className="surface routing-detail" aria-label="Route recommendation">
      {selectedTicket ? (
        <>
          <div className="section-heading">
            <h2>{selectedTicket.reference}</h2>
            <p>{selectedTicket.title}</p>
          </div>
          <StatusPill state={selectedTicket.state} />
          {selectedTicket.priorityAssessment ? (
            <div className="priority-assessment">
              <span
                className={`priority-badge priority-badge--${selectedTicket.priorityAssessment.tier.toLowerCase()}`}
              >
                {selectedTicket.priorityAssessment.tier}
              </span>
              <span>Internal priority score {selectedTicket.priorityAssessment.score}</span>
              <ul>
                {selectedTicket.priorityAssessment.reasons.map((reason) => (
                  <li key={reason}>{reason}</li>
                ))}
              </ul>
            </div>
          ) : null}
          <Recommendation ticket={selectedTicket} />
          <Review title="RFA recommendation" review={selectedTicket.rfaReview} />
          <Review title="CM recommendation" review={selectedTicket.cmReview} />
          <PlanUpdates ticket={selectedTicket} />
          <SimilarRequestsPanel
            isLinking={isLinkingSimilar}
            isLoading={isSimilarLoading}
            isQueryError={isSimilarQueryError}
            matches={similarMatches}
            onLink={onLinkSimilar}
            onRetry={onRetrySimilar}
          />
          {canApprove(selectedTicket, route) && isRouteOverride(selectedTicket, route) ? (
            <div className="routing-override">
              <label htmlFor="routing-override-reason">Override reason</label>
              <textarea
                id="routing-override-reason"
                onChange={(event) => onOverrideReasonChange(event.target.value)}
                placeholder="Explain why this queue should take the request instead."
                value={overrideReason}
              />
              <small>
                The orchestrator recommended a different route. An override reason of at least 3
                characters is required.
              </small>
            </div>
          ) : null}
          <div className="routing-actions">
            {selectedTicket.state === "ROUTE_ASSESSMENT" ? (
              <button disabled={isRunningReviews} onClick={onRunReviews} type="button">
                Run capability checks
              </button>
            ) : null}
            <button
              disabled={
                !canApproveWithOverride(selectedTicket, route, overrideReason) || isApprovePending
              }
              onClick={onApprove}
              type="button"
            >
              Approve route
            </button>
          </div>
          {actionError ? (
            <p className="auth-error" role="alert">
              {actionError}
            </p>
          ) : null}
          {selectedTicket.state === "ANALYST_ASSIGNMENT" ? (
            <AssignAnalystPanel
              csrfToken={csrfToken}
              onAssigned={onAssigned}
              suggestedTeamName={teamNameForAssignment(selectedTicket, route)}
              ticketId={selectedTicket.ticketId}
            />
          ) : (
            <details className="workspace-details">
              <summary>
                <MessageCircleQuestion aria-hidden="true" size={16} />
                Query or reject this route
              </summary>
              <div className="routing-forms">
                <label>
                  Clarification reason
                  <textarea
                    onChange={(event) => onClarificationReasonChange(event.target.value)}
                    value={clarificationReason}
                  />
                </label>
                <label>
                  Clarification question
                  <input
                    onChange={(event) => onClarificationQuestionChange(event.target.value)}
                    value={clarificationQuestion}
                  />
                </label>
                <button
                  disabled={
                    !canSubmitClarification(
                      selectedTicket,
                      route,
                      clarificationReason,
                      clarificationQuestion,
                    )
                  }
                  onClick={onRequestClarification}
                  type="button"
                >
                  Request clarification
                </button>
                <label>
                  Rejection reason
                  <textarea
                    onChange={(event) => onRejectReasonChange(event.target.value)}
                    value={rejectReason}
                  />
                </label>
                <button
                  disabled={!canReject(selectedTicket, route, rejectReason)}
                  onClick={onReject}
                  type="button"
                >
                  Reject route
                </button>
              </div>
            </details>
          )}
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
