import { useState } from "react";
import { ArrowLeft, FileText, ShieldAlert } from "lucide-react";
import { Link } from "react-router-dom";

import { AssetGrant } from "./AssetGrant";
import { productTypeLabel } from "./store-options";
import type { AssetAccessGrant, StoreProduct } from "../../lib/api-client/store";

export function ProductMetadata({ product }: { product: StoreProduct }) {
  return (
    <article className="surface product-main" aria-labelledby="product-metadata-title">
      <h2 id="product-metadata-title">Metadata</h2>
      <p>{product.description}</p>
      <dl className="detail-list detail-list--wide">
        <div>
          <dt>Type</dt>
          <dd>{productTypeLabel(product.productType)}</dd>
        </div>
        <div>
          <dt>Owner</dt>
          <dd>{product.ownerTeam}</dd>
        </div>
        <div>
          <dt>Region</dt>
          <dd>{product.areaOrRegion}</dd>
        </div>
        <div>
          <dt>Classification</dt>
          <dd>{product.classificationLevel}</dd>
        </div>
        <div>
          <dt>Coverage</dt>
          <dd>
            {product.timePeriodStart
              ? `${product.timePeriodStart} to ${product.timePeriodEnd ?? "ongoing"}`
              : "Not recorded"}
          </dd>
        </div>
        <div>
          <dt>Source</dt>
          <dd>{product.sourceType.replaceAll("_", " ")}</dd>
        </div>
        <div>
          <dt>Releasability</dt>
          <dd>{product.releasability.join(", ") || "Not recorded"}</dd>
        </div>
        <div>
          <dt>Caveats</dt>
          <dd>{product.handlingCaveats.join(", ") || "None"}</dd>
        </div>
        <div>
          <dt>Status</dt>
          <dd>{product.status}</dd>
        </div>
      </dl>
      <div className="store-facets">
        {product.geojsonRef !== null ? <span className="store-chip">Geospatial layer</span> : null}
        {product.tags.map((tag) => (
          <span className="store-chip" key={tag}>
            {tag}
          </span>
        ))}
        {product.semanticLabels.map((label) => (
          <span className="store-chip store-chip--semantic" key={label}>
            {label}
          </span>
        ))}
      </div>
    </article>
  );
}

export function ProductAssets({
  accessGrant,
  accessStatus,
  assetId,
  canRequestAccess,
  from,
  product,
}: {
  accessGrant?: AssetAccessGrant;
  accessStatus: "error" | "pending" | "success";
  assetId?: string;
  canRequestAccess: boolean;
  from?: string;
  product: StoreProduct;
}) {
  return (
    <aside className="surface product-assets" aria-labelledby="assets-title">
      <h2 id="assets-title">Assets</h2>
      {!canRequestAccess ? (
        <p className="store-asset-hint">
          You do not have permission to download assets. Metadata remains visible.
        </p>
      ) : null}
      <div className="stack-list">
        {product.assets.map((asset) => {
          const row = (
            <>
              <FileText aria-hidden="true" size={18} />
              <span>
                {asset.name}
                <small className="store-asset-meta">
                  {asset.mimeType} | {Math.max(1, Math.round(asset.sizeBytes / 1024))} KB | SHA-256{" "}
                  {asset.sha256.slice(0, 12)}
                </small>
              </span>
              <small>{asset.previewKind.replaceAll("_", " ")}</small>
            </>
          );
          return canRequestAccess ? (
            <Link
              className="stack-row store-asset-row"
              key={asset.id}
              state={{ from }}
              to={`/store/products/${encodeURIComponent(product.id)}/assets/${encodeURIComponent(asset.id)}`}
            >
              {row}
            </Link>
          ) : (
            <div className="stack-row store-asset-row" key={asset.id}>
              {row}
            </div>
          );
        })}
      </div>
      {assetId !== undefined && canRequestAccess ? (
        <AssetGrant
          assetId={assetId}
          assetName={product.assets.find((asset) => asset.id === assetId)?.name ?? "asset-download"}
          grant={accessGrant}
          productId={product.id}
          status={accessStatus}
        />
      ) : null}
    </aside>
  );
}

export function ProductDenied({
  canBreakGlass,
  isPending,
  onBreakGlass,
  showError,
}: {
  canBreakGlass: boolean;
  isPending: boolean;
  onBreakGlass: (reason: string) => void;
  showError: boolean;
}) {
  const [reason, setReason] = useState("");
  const reasonIsValid = reason.trim().length >= 10;
  return (
    <section className="surface store-denied" aria-labelledby="store-denied-title">
      <ShieldAlert aria-hidden="true" size={22} />
      <div>
        <h1 id="store-denied-title">Product not available</h1>
        <p>The product either does not exist or is outside your active ACGs.</p>
        {canBreakGlass ? (
          <form
            className="break-glass-form"
            onSubmit={(event) => {
              event.preventDefault();
              if (reasonIsValid) onBreakGlass(reason.trim());
            }}
          >
            <label>
              Emergency support reason
              <textarea
                onChange={(event) => setReason(event.target.value)}
                placeholder="Explain the authorised site-administration need"
                value={reason}
              />
            </label>
            <button disabled={!reasonIsValid || isPending} type="submit">
              <ShieldAlert aria-hidden="true" size={18} />
              Access with audit log
            </button>
            {showError ? (
              <p className="auth-error" role="alert">
                Emergency access failed. Confirm the product ID and your permissions.
              </p>
            ) : null}
          </form>
        ) : null}
        <Link className="store-action store-action--secondary" to="/store">
          <ArrowLeft aria-hidden="true" size={18} />
          Back to store
        </Link>
      </div>
    </section>
  );
}
