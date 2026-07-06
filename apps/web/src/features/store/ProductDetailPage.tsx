import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Download, FileText, ShieldAlert } from "lucide-react";
import { Link, useLocation, useParams } from "react-router-dom";

import { backNavigationFor } from "./store-navigation";
import { productTypeLabel } from "./store-options";
import { LoadingState } from "../../components/ui/PageState";
import { ApiError } from "../../lib/api-client/client";
import { getAssetAccess, getStoreProduct, type AssetAccessGrant } from "../../lib/api-client/store";

export default function ProductDetailPage() {
  const { assetId, productId } = useStoreRouteIds();
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from;
  const back = backNavigationFor(from);
  const productQuery = useQuery({
    enabled: productId !== undefined,
    queryKey: ["store-product", productId],
    queryFn: () => getStoreProduct(productId ?? ""),
    retry: false,
  });
  const accessQuery = useQuery({
    enabled: productId !== undefined && assetId !== undefined && productQuery.data !== undefined,
    queryKey: ["store-asset-access", productId, assetId],
    queryFn: () => getAssetAccess(productId ?? "", assetId ?? ""),
    retry: false,
  });

  if (productQuery.isError && isNotFound(productQuery.error)) {
    return <StoreDenied />;
  }
  if (productQuery.isLoading) {
    return (
      <section className="surface">
        <LoadingState label="Loading product" />
      </section>
    );
  }
  const product = productQuery.data;
  if (product === undefined) {
    return <StoreDenied />;
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
          </dl>
          <div className="store-facets">
            {product.tags.map((tag) => (
              <span className="store-chip" key={tag}>
                {tag}
              </span>
            ))}
          </div>
        </article>

        <aside className="surface product-assets" aria-labelledby="assets-title">
          <h2 id="assets-title">Assets</h2>
          <div className="stack-list">
            {product.assets.map((asset) => (
              <Link
                className="stack-row store-asset-row"
                key={asset.id}
                to={`/store/products/${product.id}/assets/${asset.id}`}
              >
                <FileText aria-hidden="true" size={18} />
                <span>{asset.name}</span>
                <small>{asset.previewKind}</small>
              </Link>
            ))}
          </div>
          {assetId !== undefined ? (
            <AssetGrant grant={accessQuery.data} status={accessQuery.status} />
          ) : null}
        </aside>
      </section>
    </div>
  );
}

function AssetGrant({ grant, status }: { grant?: AssetAccessGrant; status: string }) {
  if (status === "error") {
    return (
      <div className="asset-grant asset-grant--denied">
        <ShieldAlert aria-hidden="true" size={18} />
        <span>Asset access denied or unavailable.</span>
      </div>
    );
  }
  if (grant === undefined) {
    return <div className="asset-grant">Preparing controlled access</div>;
  }
  return (
    <div className="asset-grant">
      <Download aria-hidden="true" size={18} />
      <div>
        <strong>Download authorised.</strong> Controlled token: <code>{grant.downloadToken}</code>
        <small> Expires in {Math.round(grant.expiresInSeconds / 60)} minutes.</small>
      </div>
    </div>
  );
}

function StoreDenied() {
  return (
    <section className="surface store-denied" aria-labelledby="store-denied-title">
      <ShieldAlert aria-hidden="true" size={22} />
      <div>
        <h1 id="store-denied-title">Product not available</h1>
        <p>The product either does not exist or is outside your active ACGs.</p>
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
