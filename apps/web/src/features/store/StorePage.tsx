import { useQuery } from "@tanstack/react-query";
import { Search, Upload } from "lucide-react";
import { useMemo, useState } from "react";
import { Link, useLocation } from "react-router-dom";

import { ProductTypeIcon } from "./ProductTypeIcon";
import { productTypeLabel, productTypeOptions } from "./store-options";
import { EmptyState, ErrorState } from "../../components/ui/PageState";
import { searchStoreProducts, type StoreSearchFilters } from "../../lib/api-client/store";
import { useAuth } from "../../lib/auth/auth-context";
import { hasPermissions } from "../../lib/permissions/route-access";

const emptySearch = {
  products: [],
  total: 0,
  facets: { productTypes: [], regions: [], tags: [] },
};

type StorePageProps = {
  description?: string;
  ownerTeam?: string;
  scope?: "all" | "mine";
  title?: string;
};

export default function StorePage({
  description = "MOCK DATA ONLY controlled product search, metadata review and asset access.",
  ownerTeam,
  scope = "all",
  title,
}: StorePageProps) {
  const { session } = useAuth();
  const location = useLocation();
  const [draftFilters, setDraftFilters] = useState({
    query: "",
    productType: "",
    region: "",
    tag: "",
    sourceType: "",
    dateFrom: "",
    dateTo: "",
  });
  const [submittedFilters, setSubmittedFilters] = useState<StoreSearchFilters>({});
  const productsQuery = useQuery({
    queryKey: ["store-products", submittedFilters],
    queryFn: () => searchStoreProducts(submittedFilters),
    placeholderData: emptySearch,
  });
  const visibleProducts = useMemo(() => {
    const products = productsQuery.data?.products ?? [];
    if (ownerTeam !== undefined) {
      return products.filter((product) => product.ownerTeam === ownerTeam);
    }
    if (scope === "all" || session === null) {
      return products;
    }
    const roleText = session.user.roles.join(" ").toLowerCase();
    return products.filter((product) => roleText.includes(product.ownerTeam.toLowerCase()));
  }, [ownerTeam, productsQuery.data?.products, scope, session]);
  const canUpload = session !== null && hasPermissions(session.user, ["product:create_existing"]);

  return (
    <div className="store-page">
      <section className="overview-hero" aria-labelledby="store-title">
        <div>
          <h1 id="store-title">
            {title ?? (scope === "mine" ? "My Products" : "Intelligence Store")}
          </h1>
          <p>{description}</p>
        </div>
        {canUpload ? (
          <Link className="store-action" to="/store/upload">
            <Upload aria-hidden="true" size={18} />
            Upload product
          </Link>
        ) : (
          <div className="classification-note">MOCK DATA ONLY</div>
        )}
      </section>

      <section className="store-layout">
        <form
          className="surface store-filters"
          onSubmit={(event) => {
            event.preventDefault();
            setSubmittedFilters(cleanFilters(draftFilters));
          }}
        >
          <div className="section-heading">
            <h2>Search</h2>
            <p>Filters run after ACG and classification checks.</p>
          </div>
          <label>
            Full text
            <input
              onChange={(event) =>
                setDraftFilters((current) => ({ ...current, query: event.target.value }))
              }
              placeholder="Search title, summary, tags"
              value={draftFilters.query}
            />
          </label>
          <label>
            Product type
            <select
              onChange={(event) =>
                setDraftFilters((current) => ({ ...current, productType: event.target.value }))
              }
              value={draftFilters.productType}
            >
              <option value="">Any type</option>
              {productTypeOptions.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <div className="store-filter-grid">
            <label>
              Region
              <input
                onChange={(event) =>
                  setDraftFilters((current) => ({ ...current, region: event.target.value }))
                }
                value={draftFilters.region}
              />
            </label>
            <label>
              Tag
              <input
                onChange={(event) =>
                  setDraftFilters((current) => ({ ...current, tag: event.target.value }))
                }
                value={draftFilters.tag}
              />
            </label>
          </div>
          <label>
            Source type
            <input
              onChange={(event) =>
                setDraftFilters((current) => ({ ...current, sourceType: event.target.value }))
              }
              value={draftFilters.sourceType}
            />
          </label>
          <div className="store-filter-grid">
            <label>
              Coverage from
              <input
                onChange={(event) =>
                  setDraftFilters((current) => ({ ...current, dateFrom: event.target.value }))
                }
                type="date"
                value={draftFilters.dateFrom}
              />
            </label>
            <label>
              Coverage to
              <input
                onChange={(event) =>
                  setDraftFilters((current) => ({ ...current, dateTo: event.target.value }))
                }
                type="date"
                value={draftFilters.dateTo}
              />
            </label>
          </div>
          <button type="submit">
            <Search aria-hidden="true" size={18} />
            Search products
          </button>
        </form>

        <section className="surface store-results" aria-live="polite">
          <div className="store-results__header">
            <div>
              <span className="eyebrow">Visible results</span>
              <h2>{visibleProducts.length} products</h2>
            </div>
            {productsQuery.isFetching ? <span className="store-chip">Refreshing</span> : null}
          </div>
          <div className="store-facets" aria-label="Visible facets">
            {(productsQuery.data?.facets.productTypes ?? []).map((type) => (
              <span className="store-chip" key={type}>
                {productTypeLabel(type)}
              </span>
            ))}
          </div>
          {productsQuery.isError ? (
            <ErrorState onRetry={() => void productsQuery.refetch()} />
          ) : (
            <div className="store-result-list">
              {visibleProducts.map((product) => (
                <Link
                  className="store-result"
                  key={product.id}
                  state={{ from: location.pathname }}
                  to={`/store/products/${product.id}`}
                >
                  <div>
                    <div className="store-result__title">
                      <span className="store-result__format" aria-hidden="true">
                        <ProductTypeIcon productType={product.productType} />
                      </span>
                      <strong>{product.title}</strong>
                    </div>
                    <p>{product.summary}</p>
                    <div className="store-facets">
                      <span className="store-chip">{productTypeLabel(product.productType)}</span>
                      <span className="store-chip">Class {product.classificationLevel}</span>
                      {product.timePeriodStart ? (
                        <span className="store-chip">
                          {product.timePeriodStart} to {product.timePeriodEnd ?? "ongoing"}
                        </span>
                      ) : null}
                    </div>
                  </div>
                  <dl>
                    <div>
                      <dt>Owner</dt>
                      <dd>{product.ownerTeam}</dd>
                    </div>
                    <div>
                      <dt>Region</dt>
                      <dd>{product.areaOrRegion}</dd>
                    </div>
                  </dl>
                </Link>
              ))}
              {visibleProducts.length === 0 ? (
                <EmptyState
                  hint="Adjust the filters or clear the search to see more of your authorised products."
                  title="No visible products match these filters"
                />
              ) : null}
            </div>
          )}
        </section>
      </section>
    </div>
  );
}

function cleanFilters(filters: Record<string, string>) {
  return Object.fromEntries(
    Object.entries(filters)
      .map(([key, value]) => [key, value.trim()])
      .filter(([, value]) => value !== ""),
  ) as StoreSearchFilters;
}
