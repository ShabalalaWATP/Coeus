import { useQuery } from "@tanstack/react-query";
import { SearchCheck, Upload } from "lucide-react";
import { useMemo, useState } from "react";
import { Link, useLocation } from "react-router-dom";

import { PaginationControls, PaginationSummary } from "./StorePagination";
import { StoreMatchReasons } from "./StoreMatchReasons";
import { ProductTypeIcon } from "./ProductTypeIcon";
import { StoreSearchFiltersPanel, type StoreFilterDraft } from "./StoreSearchFiltersPanel";
import { productTypeLabel } from "./store-options";
import { SpotlightCard } from "../../components/effects/SpotlightCard";
import { AdminReturnLink } from "../../components/ui/AdminReturnLink";
import { EmptyState, ErrorState } from "../../components/ui/PageState";
import { searchStoreProducts, type StoreSearchFilters } from "../../lib/api-client/store";
import { useAuth } from "../../lib/auth/auth-context";
import { hasPermissions } from "../../lib/permissions/route-access";

const emptySearch = {
  products: [],
  total: 0,
  page: 1,
  pageSize: 6,
  totalPages: 0,
  facets: { productTypes: [], regions: [], tags: [] },
};

type StorePageProps = {
  description?: string;
  ownerTeam?: string;
  scope?: "all" | "mine";
  title?: string;
};

type StoreSort = "relevance" | "title" | "coverage";

const sorters: Record<StoreSort, (a: SortableProduct, b: SortableProduct) => number> = {
  relevance: () => 0,
  title: (a, b) => a.title.localeCompare(b.title),
  coverage: (a, b) => (b.timePeriodStart ?? "").localeCompare(a.timePeriodStart ?? ""),
};

type SortableProduct = { title: string; timePeriodStart: string | null };

// Owner-team labels stored on products map to the roles that own them. An
// explicit role-name map (covering current and legacy role names) keeps
// "My Products" correct; substring matching broke when roles were renamed.
const OWNER_TEAM_ROLES: Record<string, readonly string[]> = {
  rfa: [
    "RFA Manager",
    "RFA Team Member",
    "Request for Assessment Manager",
    "Request for Assessment Team Member",
  ],
  collection: ["CM Manager", "CM Team Member", "Collection Manager", "Collection Team Member"],
};
const STORE_PAGE_SIZE = 6;

function ownsTeamProduct(roleNames: readonly string[], ownerTeam: string): boolean {
  const owners = OWNER_TEAM_ROLES[ownerTeam.toLowerCase()];
  return owners !== undefined && roleNames.some((role) => owners.includes(role));
}

function ownerTeamForRoles(roleNames: readonly string[]): string | undefined {
  const matched = Object.entries(OWNER_TEAM_ROLES).find(([, owners]) =>
    roleNames.some((role) => owners.includes(role)),
  );
  return matched ? (matched[0] === "rfa" ? "RFA" : "Collection") : undefined;
}

export default function StorePage({
  description = "MOCK DATA ONLY controlled product search, metadata review and asset access.",
  ownerTeam,
  scope = "all",
  title,
}: StorePageProps) {
  const { session } = useAuth();
  const location = useLocation();
  const [sort, setSort] = useState<StoreSort>("relevance");
  const [page, setPage] = useState(1);
  const [hasSearched, setHasSearched] = useState(false);
  const [searchHint, setSearchHint] = useState(false);
  const [draftFilters, setDraftFilters] = useState<StoreFilterDraft>({
    query: "",
    productType: "",
    region: "",
    tag: "",
    sourceType: "",
    dateFrom: "",
    dateTo: "",
  });
  const [submittedFilters, setSubmittedFilters] = useState<StoreSearchFilters>({});
  const activeOwnerTeam =
    ownerTeam ?? (scope === "mine" && session ? ownerTeamForRoles(session.user.roles) : undefined);
  // The store never lists holdings unprompted: catalogue curators may browse
  // everything, owner-scoped pages carry a criterion, everyone else searches.
  const canBrowseAll = session !== null && hasPermissions(session.user, ["store:browse_all"]);
  const queryEnabled =
    activeOwnerTeam !== undefined || (scope === "all" && (canBrowseAll || hasSearched));
  const searchFilters = useMemo<StoreSearchFilters>(
    () => ({
      ...submittedFilters,
      ...(activeOwnerTeam ? { ownerTeam: activeOwnerTeam } : {}),
      page,
      pageSize: STORE_PAGE_SIZE,
    }),
    [activeOwnerTeam, page, submittedFilters],
  );
  const productsQuery = useQuery({
    enabled: queryEnabled,
    queryKey: ["store-products", searchFilters],
    queryFn: () => searchStoreProducts(searchFilters),
    placeholderData: emptySearch,
  });
  const visibleProducts = useMemo(() => {
    const products = productsQuery.data?.products ?? [];
    const scoped =
      ownerTeam !== undefined
        ? products.filter((product) => product.ownerTeam === ownerTeam)
        : scope === "all" || session === null
          ? products
          : products.filter((product) => ownsTeamProduct(session.user.roles, product.ownerTeam));
    return [...scoped].sort(sorters[sort]);
  }, [ownerTeam, productsQuery.data?.products, scope, session, sort]);
  const canUpload = session !== null && hasPermissions(session.user, ["product:create_existing"]);
  // When the "mine" scope cannot be pushed to the server (no owner team maps
  // to the user's roles) the filter runs client-side, so server totals and
  // pagination would be wrong. Use the filtered list for counts instead.
  const clientScoped = scope === "mine" && activeOwnerTeam === undefined;
  const hasOwnedProductScope = scope !== "mine" || activeOwnerTeam !== undefined;
  const totalVisible = clientScoped
    ? visibleProducts.length
    : (productsQuery.data?.total ?? visibleProducts.length);

  return (
    <div className="store-page">
      <section className="overview-hero store-hero" aria-labelledby="store-title">
        <div>
          <AdminReturnLink />
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

      {!hasOwnedProductScope ? (
        <section className="workspace-alert" role="status">
          <span>
            My Products is for RFA and Collection teams. Store managers administer the full
            catalogue instead.
          </span>
          <Link to="/store">Open the full Intelligence Store</Link>
        </section>
      ) : null}

      <section className="store-layout">
        <StoreSearchFiltersPanel
          filters={draftFilters}
          onFiltersChange={setDraftFilters}
          onSubmit={(filters) => {
            const cleaned = cleanFilters(filters);
            if (scope === "all" && !canBrowseAll && Object.keys(cleaned).length === 0) {
              setSearchHint(true);
              return;
            }
            setSearchHint(false);
            setSubmittedFilters(cleaned);
            setPage(1);
            setHasSearched(true);
          }}
        />

        {!queryEnabled && scope === "all" ? (
          <section className="surface store-results store-search-first" aria-live="polite">
            <SearchCheck aria-hidden="true" size={30} />
            <h2>Search the Intelligence Store</h2>
            <p>
              Products are shown on a need-to-know basis: enter a search term or filter, or arrive
              from an RFI search, to view matching holdings you are cleared for.
            </p>
            {searchHint ? (
              <p className="store-search-first__hint" role="alert">
                Enter a search term or pick at least one filter first.
              </p>
            ) : null}
          </section>
        ) : null}

        {queryEnabled ? (
          <section className="surface store-results" aria-live="polite">
            <div className="store-results__header">
              <div>
                <span className="eyebrow">Visible results</span>
                <h2>{totalVisible} products</h2>
              </div>
              <label className="store-sort">
                Sort by
                <select onChange={(event) => setSort(event.target.value as StoreSort)} value={sort}>
                  <option value="relevance">Relevance</option>
                  <option value="title">Title</option>
                  <option value="coverage">Newest coverage</option>
                </select>
              </label>
              {productsQuery.isFetching ? <span className="store-chip">Refreshing</span> : null}
            </div>
            <PaginationSummary
              page={clientScoped ? 1 : (productsQuery.data?.page ?? page)}
              pageSize={
                clientScoped
                  ? Math.max(visibleProducts.length, 1)
                  : (productsQuery.data?.pageSize ?? STORE_PAGE_SIZE)
              }
              total={totalVisible}
            />
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
                  <SpotlightCard className="store-result-spot" key={product.id}>
                    <Link
                      className="store-result"
                      state={{ from: location.pathname }}
                      to={`/store/products/${encodeURIComponent(product.id)}`}
                    >
                      <div>
                        <div className="store-result__title">
                          <span className="store-result__format" aria-hidden="true">
                            <ProductTypeIcon productType={product.productType} />
                          </span>
                          <div>
                            <span className="mono-ref">{product.reference}</span>
                            <strong>{product.title}</strong>
                          </div>
                        </div>
                        <p>{product.summary}</p>
                        <StoreMatchReasons
                          reasons={product.matchReasons}
                          show={Boolean(submittedFilters.query)}
                        />
                        <div className="store-facets">
                          <span className="store-chip">
                            {productTypeLabel(product.productType)}
                          </span>
                          <span className="store-chip">Class {product.classificationLevel}</span>
                          {product.timePeriodStart ? (
                            <span className="store-chip">
                              {product.timePeriodStart} to {product.timePeriodEnd ?? "ongoing"}
                            </span>
                          ) : null}
                          {product.tags.slice(0, 4).map((tag) => (
                            <span className="store-chip store-chip--tag" key={tag}>
                              {tag}
                            </span>
                          ))}
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
                  </SpotlightCard>
                ))}
                {visibleProducts.length === 0 ? (
                  <EmptyState
                    hint="Try related terms, fewer filters or a broader coverage date range."
                    title="No visible products match these filters"
                  />
                ) : null}
              </div>
            )}
            <PaginationControls
              onNext={() => setPage((current) => current + 1)}
              onPrevious={() => setPage((current) => Math.max(1, current - 1))}
              page={productsQuery.data?.page ?? page}
              totalPages={clientScoped ? 0 : (productsQuery.data?.totalPages ?? 0)}
            />
          </section>
        ) : null}
      </section>
    </div>
  );
}

function cleanFilters(filters: StoreFilterDraft) {
  return Object.fromEntries(
    Object.entries(filters)
      .map(([key, value]) => [key, value.trim()])
      .filter(([, value]) => value !== ""),
  ) as StoreSearchFilters;
}
