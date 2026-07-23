import { BarChart3, Bot, CheckCircle2, PackageCheck, Search, XCircle } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import type {
  RfiProductOffer,
  RfiSearchMetrics,
  RfiSearchResults,
} from "../../lib/api-client/rfi-search";
import type { Ticket } from "../../lib/api-client/tickets";
import { formatWorkflowState } from "../../lib/workflow/state-format";
import { productTypeLabel } from "../store/store-options";

type ProductOffersPanelProps = {
  canManageOffers: boolean;
  canRunSearch: boolean;
  isAccepting: boolean;
  isError?: boolean;
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
  canManageOffers,
  canRunSearch,
  isAccepting,
  isError = false,
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
  const canRetry = canRunSearch && ticket?.state === "RFI_SEARCH_INCOMPLETE";
  const heading =
    offers.length === 0
      ? "Product search"
      : offers.length === 1
        ? "Matching product"
        : "Matching products";

  return (
    <section className="surface product-offers-panel" aria-labelledby="product-offers-title">
      <div className="section-heading access-heading">
        <PackageCheck aria-hidden="true" size={20} />
        <h2 id="product-offers-title">{heading}</h2>
      </div>
      {ticket === undefined ? <p>No ticket selected</p> : null}
      {ticket !== undefined ? (
        <>
          {ticket.state === "RFI_SEARCH_INCOMPLETE" ? (
            <div className="offer-toolbar">
              <button disabled={!canRetry || isRunning} onClick={onRun} type="button">
                <Search aria-hidden="true" size={18} />
                {isRunning ? "Retrying..." : "Retry search"}
              </button>
            </div>
          ) : null}
          {results?.degradedReason ? (
            <p className="workspace-alert" role="alert">
              Search is degraded ({(results.retrievalMode ?? "lexical_only").replaceAll("_", " ")}).
              No definitive no-match decision will be made until semantic retrieval recovers.
            </p>
          ) : null}
          {ticket.state === "RFI_SEARCHING" ? (
            <p role="status">Searching the Intelligence Store automatically...</p>
          ) : null}
          {isLoading ? <p>Loading product offers</p> : null}
          {isError ? (
            <p className="auth-error" role="alert">
              Product offers could not be loaded. Refresh and try again.
            </p>
          ) : offers.length ? (
            <div className="offer-list">
              {offers.map((offer) => (
                <OfferCard
                  isAccepting={isAccepting}
                  isRejecting={isRejecting}
                  canManageOffers={canManageOffers}
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
          <SearchDetails
            metrics={results?.metrics}
            retrievalMode={results?.retrievalMode}
            state={ticket.state}
          />
        </>
      ) : null}
    </section>
  );
}

function SearchDetails({
  metrics,
  retrievalMode,
  state,
}: {
  metrics?: RfiSearchMetrics | null;
  retrievalMode?: string;
  state: Ticket["state"];
}) {
  return (
    <details className="search-details">
      <summary>Search details</summary>
      <div className="search-details__content">
        <div className="search-details__overview">
          <span className="offer-state">{formatWorkflowState(state)}</span>
          <span className="agent-chip">
            <Bot aria-hidden="true" size={13} />
            RFI search agent
          </span>
        </div>
        {metrics ? <SearchMetrics metrics={metrics} retrievalMode={retrievalMode} /> : null}
      </div>
    </details>
  );
}

function SearchMetrics({
  metrics,
  retrievalMode,
}: {
  metrics: RfiSearchMetrics;
  retrievalMode?: string;
}) {
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
      <div>
        <dt>Retrieval</dt>
        <dd>{(metrics.retrievalMode ?? retrievalMode ?? "metadata_only").replaceAll("_", " ")}</dd>
      </div>
      <div>
        <dt>Assurance</dt>
        <dd>{metrics.assurance}</dd>
      </div>
    </dl>
  );
}

type OfferCardProps = {
  canManageOffers: boolean;
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
  canManageOffers,
  isAccepting,
  isRejecting,
  offer,
  onAccept,
  onReasonChange,
  onReject,
  reason,
  ticket,
}: OfferCardProps) {
  const canAct =
    canManageOffers && ticket.state === "RFI_MATCH_OFFERED" && offer.status === "offered";
  const rejectId = `reject-${offer.productId}`;
  const passages = offer.passages ?? [];
  return (
    <article className="offer-card">
      <div className="offer-card__header">
        <div>
          <span className="offer-card__classification">Class {offer.classificationLevel}</span>
          <h3>
            {offer.offerableToUser ? (
              <Link
                className="offer-card__title"
                to={`/store/products/${encodeURIComponent(offer.productId)}`}
              >
                {offer.title}
              </Link>
            ) : (
              offer.title
            )}
          </h3>
        </div>
      </div>
      <p>{offer.summary}</p>
      {offer.rejectionReason ? <p>{offer.rejectionReason}</p> : null}
      <div className="offer-actions">
        <button
          disabled={!canAct || isAccepting}
          onClick={() => onAccept(offer.productId)}
          type="button"
        >
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
        <button
          disabled={!canAct || reason.trim().length < 3 || isRejecting}
          onClick={onReject}
          type="button"
        >
          <XCircle aria-hidden="true" size={18} />
          Reject
        </button>
      </div>
      <details className="offer-details">
        <summary>Product details</summary>
        <div className="offer-details__content">
          <div className="offer-meta">
            <span>{productTypeLabel(offer.productType)}</span>
            <span>{offer.region}</span>
            <span>{offer.assetTypes.join(", ") || "metadata"}</span>
            <ScoreBadge offer={offer} />
          </div>
          <div className="offer-reasons">
            {offer.matchReasons.map((reasonItem) => (
              <span key={reasonItem}>{reasonLabel(reasonItem)}</span>
            ))}
          </div>
          {passages.length ? (
            <section className="offer-evidence" aria-label="Grounded evidence">
              <h4>Grounded evidence ({passages.length})</h4>
              {passages.map((passage) => (
                <blockquote key={passage.chunkId}>
                  <p>{passage.excerpt}</p>
                  <cite>{passage.citation}</cite>
                </blockquote>
              ))}
            </section>
          ) : null}
        </div>
      </details>
    </article>
  );
}

function ScoreBadge({ offer }: { offer: RfiProductOffer }) {
  return (
    <span
      aria-label={`Retrieval relevance ${Math.round(offer.matchScore * 100)} percent`}
      className={`score-badge score-badge--${offer.status}`}
      title="Retrieval relevance, not analytic confidence"
    >
      <BarChart3 aria-hidden="true" size={16} />
      {Math.round(offer.matchScore * 100)}%
    </span>
  );
}

function reasonLabel(reason: string) {
  const [kind, value] = reason.split(":", 2);
  const labels: Record<string, string> = {
    "full-text": "Matched term",
    "lexical-rank": "Text result rank",
    metadata: "Metadata fit",
    retrieval: "Retrieval mode",
    semantic: "Related term",
    "semantic-label": "Topic",
    "vector-similarity": "Semantic similarity",
  };
  const label = labels[kind] ?? "Match signal";
  return `${label}: ${(value ?? reason).replaceAll("-", " ")}`;
}
