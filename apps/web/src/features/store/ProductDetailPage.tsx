import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowLeft, FileText, ShieldAlert } from "lucide-react";
import { useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";

import { AssetGrant } from "./AssetGrant";
import { backNavigationFor } from "./store-navigation";
import { productTypeLabel } from "./store-options";
import { LoadingState } from "../../components/ui/PageState";
import { ApiError } from "../../lib/api-client/client";
import {
  breakGlassAssetAccess,
  breakGlassStoreProduct,
  getAssetAccess,
  getStoreProduct,
} from "../../lib/api-client/store";
import { useAuth } from "../../lib/auth/auth-context";

export default function ProductDetailPage() {
  const { assetId, productId } = useStoreRouteIds();
  const { session } = useAuth();
  const [breakGlassReason, setBreakGlassReason] = useState<string | null>(null);
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from;
  const back = backNavigationFor(from);
  const canDownload = session?.user.permissions.includes("product:download") ?? false;
  const productQuery = useQuery({
    enabled: productId !== undefined,
    queryKey: ["store-product", productId],
    queryFn: () => getStoreProduct(productId ?? ""),
    retry: false,
  });
  const breakGlassMutation = useMutation({
    mutationFn: (reason: string) =>
      breakGlassStoreProduct(productId ?? "", reason, session?.csrfToken ?? ""),
    onSuccess: (_product, reason) => setBreakGlassReason(reason),
  });
  const accessQuery = useQuery({
    enabled:
      productId !== undefined &&
      assetId !== undefined &&
      (productQuery.data !== undefined ||
        (breakGlassMutation.data !== undefined && breakGlassReason !== null)),
    queryKey: ["store-asset-access", productId, assetId],
    queryFn: () =>
      breakGlassMutation.data !== undefined && breakGlassReason !== null
        ? breakGlassAssetAccess(
            productId ?? "",
            assetId ?? "",
            breakGlassReason,
            session?.csrfToken ?? "",
          )
        : getAssetAccess(productId ?? "", assetId ?? ""),
    retry: false,
  });
  const emergencyProduct = breakGlassMutation.data;

  if (productQuery.isError && isNotFound(productQuery.error) && emergencyProduct === undefined) {
    return (
      <StoreDenied
        canBreakGlass={
          productId !== undefined &&
          (session?.user.permissions.includes("product:read_restricted") ?? false)
        }
        isPending={breakGlassMutation.isPending}
        onBreakGlass={(reason) => breakGlassMutation.mutate(reason)}
        showError={breakGlassMutation.isError}
      />
    );
  }
  if (productQuery.isLoading) {
    return (
      <section className="surface">
        <LoadingState label="Loading product" />
      </section>
    );
  }
  const product = emergencyProduct ?? productQuery.data;
  if (product === undefined) {
    return (
      <StoreDenied
        canBreakGlass={
          productId !== undefined &&
          (session?.user.permissions.includes("product:read_restricted") ?? false)
        }
        isPending={breakGlassMutation.isPending}
        onBreakGlass={(reason) => breakGlassMutation.mutate(reason)}
        showError={breakGlassMutation.isError}
      />
    );
  }

  return (
    <div className="store-page">
      <section className="overview-hero" aria-labelledby="product-title">
        <div>
          <span className="eyebrow">{product.reference}</span>
          <h1 id="product-title">{product.title}</h1>
          <p>{product.summary}</p>
        </div>
        <Link className="store-action store-action--secondary" to={back.path}>
          <ArrowLeft aria-hidden="true" size={18} />
          {back.label}
        </Link>
      </section>

      <section className="store-detail-grid">
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
            {product.geojsonRef !== null ? (
              <span className="store-chip">Geospatial layer</span>
            ) : null}
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

        <aside className="surface product-assets" aria-labelledby="assets-title">
          <h2 id="assets-title">Assets</h2>
          {canDownload ? null : (
            <p className="store-asset-hint">
              You do not have permission to download assets. Metadata remains visible.
            </p>
          )}
          <div className="stack-list">
            {product.assets.map((asset) => {
              const row = (
                <>
                  <FileText aria-hidden="true" size={18} />
                  <span>
                    {asset.name}
                    <small className="store-asset-meta">
                      {asset.mimeType} | {Math.max(1, Math.round(asset.sizeBytes / 1024))} KB |
                      SHA-256 {asset.sha256.slice(0, 12)}
                    </small>
                  </span>
                  <small>{asset.previewKind.replaceAll("_", " ")}</small>
                </>
              );
              if (!canDownload) {
                return (
                  <div className="stack-row store-asset-row" key={asset.id}>
                    {row}
                  </div>
                );
              }
              return (
                <Link
                  className="stack-row store-asset-row"
                  key={asset.id}
                  state={{ from }}
                  to={`/store/products/${encodeURIComponent(
                    product.id,
                  )}/assets/${encodeURIComponent(asset.id)}`}
                >
                  {row}
                </Link>
              );
            })}
          </div>
          {assetId !== undefined ? (
            <AssetGrant
              assetId={assetId}
              assetName={
                product.assets.find((asset) => asset.id === assetId)?.name ?? "asset-download"
              }
              grant={accessQuery.data}
              productId={product.id}
              status={accessQuery.status}
            />
          ) : null}
        </aside>
      </section>
    </div>
  );
}

function StoreDenied({
  canBreakGlass = false,
  isPending = false,
  onBreakGlass = () => undefined,
  showError = false,
}: {
  canBreakGlass?: boolean;
  isPending?: boolean;
  onBreakGlass?: (reason: string) => void;
  showError?: boolean;
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
              if (reasonIsValid) {
                onBreakGlass(reason.trim());
              }
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

function isNotFound(error: Error) {
  return error instanceof ApiError && error.status === 404;
}

function useStoreRouteIds() {
  const params = useParams();
  const location = useLocation();
  const match = /\/store\/products\/([^/]+)(?:\/assets\/([^/]+))?/.exec(location.pathname);
  return {
    productId: params.productId ?? match?.[1],
    assetId: params.assetId ?? match?.[2],
  };
}
