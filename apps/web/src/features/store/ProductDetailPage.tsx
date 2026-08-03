import { ArrowLeft } from "lucide-react";
import { Link } from "react-router-dom";

import { ProductAssets, ProductDenied, ProductMetadata } from "./ProductDetailSections";
import { useProductDetailModel } from "./useProductDetailModel";
import { SaveProductControl } from "./SaveProductControl";
import { ProjectProductControl } from "./ProjectProductControl";
import { ErrorState, LoadingState } from "../../components/ui/PageState";

export default function ProductDetailPage() {
  const model = useProductDetailModel();
  const denied = (
    <ProductDenied
      canBreakGlass={model.canBreakGlass}
      isPending={model.breakGlassPending}
      onBreakGlass={model.requestBreakGlass}
      showError={model.breakGlassError}
    />
  );
  if (model.productNotFound && model.product === undefined) return denied;
  if (model.productQuery.isError && model.product === undefined)
    return (
      <section className="surface">
        <ErrorState onRetry={() => void model.productQuery.refetch()} />
      </section>
    );
  if (model.productQuery.isLoading)
    return (
      <section className="surface">
        <LoadingState label="Loading product" />
      </section>
    );
  if (model.product === undefined) return denied;
  const product = model.product;
  return (
    <div className="store-page">
      <section className="overview-hero" aria-labelledby="product-title">
        <div>
          <span className="eyebrow">{product.reference}</span>
          <h1 id="product-title">{product.title}</h1>
          <p>{product.summary}</p>
        </div>
        <div className="product-hero-actions">
          <SaveProductControl productId={product.id} />
          <ProjectProductControl productId={product.id} />
          <Link className="store-action store-action--secondary" to={model.back.path}>
            <ArrowLeft aria-hidden="true" size={18} />
            {model.back.label}
          </Link>
        </div>
      </section>
      <section className="store-detail-flow">
        <ProductAssets
          accessGrant={model.access.data}
          accessStatus={model.access.status}
          assetId={model.assetId}
          canRequestAccess={model.canRequestAssetAccess}
          from={model.from}
          navigation={model.navigation}
          product={product}
        />
        <ProductMetadata product={product} />
      </section>
    </div>
  );
}
