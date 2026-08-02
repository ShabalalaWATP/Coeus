import { Link, useLocation } from "react-router-dom";

import { ProductTypeIcon } from "./ProductTypeIcon";
import { StoreMatchReasons } from "./StoreMatchReasons";
import { assetSummary, classificationTone, formatCoverage } from "./store-format";
import { productTypeLabel, visibleProductTags } from "./store-options";
import { SpotlightCard } from "../../components/effects/SpotlightCard";
import type { StoreProduct } from "../../lib/api-client/store";

type StoreResultCardProps = {
  product: StoreProduct & { matchReasons?: string[] };
  showMatchReasons: boolean;
};

export function StoreResultCard({ product, showMatchReasons }: StoreResultCardProps) {
  const location = useLocation();
  const coverage = formatCoverage(product.timePeriodStart, product.timePeriodEnd);
  const assets = assetSummary(product.assets);
  const tags = visibleProductTags(product.tags).slice(0, 4);
  return (
    <SpotlightCard className="store-result-spot">
      <Link
        className="store-result"
        state={{ from: location.pathname, origin: "store", search: location.search }}
        to={`/store/products/${encodeURIComponent(product.id)}`}
      >
        <p className="store-marking">
          <span
            className={`store-marking__level store-marking__level--${classificationTone(product.classificationLevel)}`}
          >
            Class {product.classificationLevel}
          </span>
          {product.status !== "published" ? (
            <span className="store-marking__status">{product.status}</span>
          ) : null}
          <span className="mono-ref">{product.reference}</span>
        </p>
        <div className="store-result__title">
          <span className="store-result__format" aria-hidden="true">
            <ProductTypeIcon productType={product.productType} />
          </span>
          <strong>{product.title}</strong>
        </div>
        <p className="store-result__summary">{product.summary}</p>
        <StoreMatchReasons reasons={product.matchReasons ?? []} show={showMatchReasons} />
        <dl className="store-result__facts">
          <div>
            <dt>Type</dt>
            <dd>{productTypeLabel(product.productType)}</dd>
          </div>
          <div>
            <dt>Region</dt>
            <dd>{product.areaOrRegion}</dd>
          </div>
          <div>
            <dt>Owner</dt>
            <dd>{product.ownerTeam}</dd>
          </div>
          <div>
            <dt>Coverage</dt>
            <dd>{coverage ?? "Not recorded"}</dd>
          </div>
          {assets !== null ? (
            <div>
              <dt>Contains</dt>
              <dd>{assets}</dd>
            </div>
          ) : null}
        </dl>
        {tags.length > 0 ? (
          <div className="store-facets">
            {tags.map((tag) => (
              <span className="store-chip store-chip--tag" key={tag}>
                {tag}
              </span>
            ))}
          </div>
        ) : null}
      </Link>
    </SpotlightCard>
  );
}
