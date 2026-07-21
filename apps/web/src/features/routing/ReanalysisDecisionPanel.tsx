import { Link } from "react-router-dom";

import type { RoutingTicket } from "../../lib/api-client/routing";

type ReanalysisDecisionPanelProps = {
  isJioc: boolean;
  pending: boolean;
  rationale: string;
  onDecide: (decision: "agree" | "refer_to_jioc" | "reanalyse" | "close") => void;
  onRationaleChange: (value: string) => void;
  ticket: RoutingTicket;
};

export function ReanalysisDecisionPanel({
  isJioc,
  pending,
  rationale,
  onDecide,
  onRationaleChange,
  ticket,
}: ReanalysisDecisionPanelProps) {
  const context = ticket.reanalysisContext;
  const disabled = pending || rationale.trim().length < 3;
  return (
    <section className="routing-reanalysis" aria-labelledby="reanalysis-decision-title">
      <h3 id="reanalysis-decision-title">
        {isJioc ? "Final re-analysis decision" : "Customer re-analysis request"}
      </h3>
      {context ? (
        <>
          <p>
            <strong>Customer reason:</strong> {context.customerReason}
          </p>
          {context.unmetCriteria.length > 0 ? (
            <div>
              <strong>Unmet criteria</strong>
              <ul>
                {context.unmetCriteria.map((criterion) => (
                  <li key={criterion}>{criterion}</li>
                ))}
              </ul>
            </div>
          ) : null}
          {context.managerRationale ? (
            <p>
              <strong>Manager rationale:</strong> {context.managerRationale}
            </p>
          ) : null}
          <Link to={`/store/products/${encodeURIComponent(context.productId)}`}>
            Review the released product
          </Link>
        </>
      ) : (
        <p className="workspace-alert">Decision context is unavailable. Do not proceed.</p>
      )}
      <label>
        Decision rationale
        <textarea
          disabled={pending}
          onChange={(event) => onRationaleChange(event.target.value)}
          value={rationale}
        />
      </label>
      <div className="routing-actions">
        <button
          disabled={disabled || context === null || context === undefined}
          onClick={() => onDecide(isJioc ? "reanalyse" : "agree")}
          type="button"
        >
          {isJioc ? "Order re-analysis" : "Agree and return to analysis"}
        </button>
        <button
          disabled={disabled || context === null || context === undefined}
          onClick={() => onDecide(isJioc ? "close" : "refer_to_jioc")}
          type="button"
        >
          {isJioc ? "Close without re-analysis" : "Disagree and refer to JIOC"}
        </button>
      </div>
    </section>
  );
}
