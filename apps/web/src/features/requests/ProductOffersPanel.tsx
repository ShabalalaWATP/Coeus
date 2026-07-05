import { BarChart3, CheckCircle2, PackageCheck, Search, XCircle } from "lucide-react";
import { useState } from "react";

import type {
  RfiProductOffer,
  RfiSearchMetrics,
  RfiSearchResults,
} from "../../lib/api-client/rfi-search";
import type { Ticket } from "../../lib/api-client/tickets";

type ProductOffersPanelProps = {
  isAccepting: boolean;
  isLoading: boolean;
  isRejecting: boolean;
  isRunning: boolean;
  onAccept: (productId: string) => void;
  onReject: (productId: string, reason: string) => void;
  onRun: () => void;
  results?: RfiSearchResults;
  ticket?: Ticket;
};

export function ProductOffersPanel({
  isAccepting,
  isLoading,
  isRejecting,
  isRunning,
  onAccept,
  onReject,
  onRun,
  results,
  ticket,
}: ProductOffersPanelProps) {
  const [reasons, setReasons] = useState<Record<string, string>>({});
  const offers = results?.offers ?? [];
  const canRun = ticket?.state === "RFI_SEARCHING";

  return (
    <section className="surface product-offers-panel" aria-labelledby="product-offers-title">
      <div className="section-heading access-heading">
        <PackageCheck aria-hidden="true" size={20} />
        <h2 id="product-offers-title">Product Offers</h2>
      </div>
      {ticket === undefined ? <p>No ticket selected</p> : null}
      {ticket !== undefined ? (
        <>
          <div className="offer-toolbar">
            <span className="offer-state">{ticket.state.replaceAll("_", " ")}</span>
            <button disabled={!canRun || isRunning} onClick={onRun} type="button">
              <Search aria-hidden="true" size={18} />
              Run search
            </button>
          </div>
          {results?.metrics ? <SearchMetrics metrics={results.metrics} /> : null}
          {isLoading ? <p>Loading product offers</p> : null}
          {offers.length ? (
            <div className="offer-list">
              {offers.map((offer) => (
                <OfferCard
                  isAccepting={isAccepting}
                  isRejecting={isRejecting}
                  key={offer.productId}
                  offer={offer}
                  onAccept={onAccept}
                  onReasonChange={(reason) =>
                    setReasons((current) => ({ ...current, [offer.productId]: reason }))
                  }
                  onReject={() => onReject(offer.productId, reasons[offer.productId] ?? "")}
                  reason={reasons[offer.productId] ?? ""}
                  ticket={ticket}
                />
              ))}
            </div>
          ) : (
            <p>No product offers</p>
          )}
        </>
      ) : null}
    </section>
  );
}

function SearchMetrics({ metrics }: { metrics: RfiSearchMetrics }) {
  return (
    <dl className="search-metrics" aria-label="RFI search metrics">
      <div>
        <dt>Offered</dt>
        <dd>{metrics.offeredCount}</dd>
      </div>
      <div>
        <dt>Candidates</dt>
        <dd>{metrics.candidateCount}</dd>
      </div>
      <div>
        <dt>Rejected</dt>
        <dd>{metrics.rejectedCount}</dd>
      </div>
    </dl>
  );
}

type OfferCardProps = {
  isAccepting: boolean;
  isRejecting: boolean;
  offer: RfiProductOffer;
  onAccept: (productId: string) => void;
  onReasonChange: (reason: string) => void;
  onReject: () => void;
  reason: string;
  ticket: Ticket;
};

function OfferCard({
  isAccepting,
  isRejecting,
  offer,
  onAccept,
  onReasonChange,
  onReject,
  reason,
  ticket,
}: OfferCardProps) {
  const canAct = ticket.state === "RFI_MATCH_OFFERED" && offer.status === "offered";
  const rejectId = `reject-${offer.productId}`;
  return (
    <article className="offer-card">
      <div className="offer-card__header">
        <div>
          <strong>{offer.title}</strong>
          <span>{offer.productType.replaceAll("_", " ")}</span>
        </div>
        <ScoreBadge offer={offer} />
      </div>
      <p>{offer.summary}</p>
      <div className="offer-meta">
        <span>Class {offer.classificationLevel}</span>
        <span>{offer.region}</span>
        <span>{offer.assetTypes.join(", ") || "metadata"}</span>
      </div>
      <div className="offer-reasons">
        {offer.matchReasons.map((reasonItem) => (
          <span key={reasonItem}>{reasonItem}</span>
        ))}
      </div>
      {offer.rejectionReason ? <p>{offer.rejectionReason}</p> : null}
      <div className="offer-actions">
        <button disabled={!canAct || isAccepting} onClick={() => onAccept(offer.productId)}>
          <CheckCircle2 aria-hidden="true" size={18} />
          Accept
        </button>
        <label htmlFor={rejectId}>
          Rejection reason
          <input
            disabled={!canAct}
            id={rejectId}
            maxLength={1000}
            onChange={(event) => onReasonChange(event.target.value)}
            value={reason}
          />
        </label>
        <button disabled={!canAct || reason.trim().length < 3 || isRejecting} onClick={onReject}>
          <XCircle aria-hidden="true" size={18} />
          Reject
        </button>
      </div>
    </article>
  );
}

function ScoreBadge({ offer }: { offer: RfiProductOffer }) {
  return (
    <span className={`score-badge score-badge--${offer.status}`}>
      <BarChart3 aria-hidden="true" size={16} />
      {Math.round(offer.matchScore * 100)}%
    </span>
  );
}
