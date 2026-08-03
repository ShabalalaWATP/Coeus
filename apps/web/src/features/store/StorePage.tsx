import { Rss, SearchCheck, Upload } from "lucide-react";
import { Link } from "react-router-dom";

import { PaginationControls, PaginationSummary } from "./StorePagination";
import { StoreWorkspaceHeader } from "./StoreWorkspaceHeader";
import { StoreFacetRail } from "./StoreFacetRail";
import { StoreResultCard } from "./StoreResultCard";
import { StoreSearchBar } from "./StoreSearchBar";
import { activeFilterCount, toggleFacet, writeStoreSearch } from "./store-search-params";
import { useStoreSearch } from "./useStoreSearch";
import { AdminReturnLink } from "../../components/ui/AdminReturnLink";
import { EmptyState, ErrorState } from "../../components/ui/PageState";
import { useAuth } from "../../lib/auth/auth-context";
import { hasPermissions } from "../../lib/permissions/route-access";

type StorePageProps = {
  description?: string;
  ownerTeam?: string;
  scope?: "all" | "mine";
  title?: string;
};

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

function ownerTeamForRoles(roleNames: readonly string[]): string | undefined {
  const matched = Object.entries(OWNER_TEAM_ROLES).find(([, owners]) =>
    roleNames.some((role) => owners.includes(role)),
  );
  return matched ? (matched[0] === "rfa" ? "RFA" : "Collection") : undefined;
}

export default function StorePage({
  description = "Search controlled intelligence holdings you are cleared to see.",
  ownerTeam,
  scope = "all",
  title,
}: StorePageProps) {
  const { session } = useAuth();
  const activeOwnerTeam =
    ownerTeam ?? (scope === "mine" && session ? ownerTeamForRoles(session.user.roles) : undefined);
  // The store never lists holdings unprompted: catalogue curators may browse
  // everything, owner-scoped pages carry a criterion, everyone else searches.
  const canBrowseAll = session !== null && hasPermissions(session.user, ["store:browse_all"]);
  const canUpload = session !== null && hasPermissions(session.user, ["product:create_existing"]);
  const hasOwnedProductScope = scope !== "mine" || activeOwnerTeam !== undefined;
  const search = useStoreSearch({
    canBrowseAll,
    canSearch: hasOwnedProductScope,
    ownerTeam: activeOwnerTeam,
  });
  const { applied, data } = search;
  // A shared or bookmarked link can name a page that a narrower result set no
  // longer has. That is not "nothing matched", and must not read as it.
  const pastLastPage = data.total > 0 && data.products.length === 0 && applied.page > 1;

  return (
    <div className="store-page">
      <StoreWorkspaceHeader
        action={
          canUpload ? (
            <Link className="store-action" to="/store/upload">
              <Upload aria-hidden="true" size={17} />
              Upload product
            </Link>
          ) : null
        }
        before={<AdminReturnLink />}
        description={description}
        showNav={scope === "all"}
        title={title ?? (scope === "mine" ? "My Products" : "Intelligence Store")}
        titleId="store-title"
      />

      {!hasOwnedProductScope ? (
        <section className="workspace-alert" role="status">
          <span>
            My Products is for RFA and Collection teams. Store managers administer the full
            catalogue instead.
          </span>
          <Link to="/store">Open the full Intelligence Store</Link>
        </section>
      ) : null}

      {hasOwnedProductScope ? (
        <>
          <StoreSearchBar
            draft={search.draft}
            hint={search.hint}
            onChange={search.setDraft}
            onSubmit={() => search.apply({ ...search.draft, page: 1 })}
            refinedCount={activeFilterCount(search.draft)}
          />
          {scope === "all" && search.enabled ? (
            <div className="store-subscribe-search">
              <span>Want to review this search again as the Store changes?</span>
              <Link to={`/store/subscriptions?${writeStoreSearch(applied).toString()}`}>
                <Rss aria-hidden="true" size={16} />
                Create subscription
              </Link>
            </div>
          ) : null}
        </>
      ) : null}

      {!hasOwnedProductScope ? null : !search.enabled ? (
        <section className="surface store-results store-search-first" aria-live="polite">
          <SearchCheck aria-hidden="true" size={30} />
          <h2>Search the Intelligence Store</h2>
          <p>
            Products are shown on a need-to-know basis. Search for a subject, region or title to see
            the holdings you are cleared for.
          </p>
        </section>
      ) : (
        <section className="store-layout">
          <StoreFacetRail
            facets={data.facets}
            onClear={() =>
              search.apply({
                ...applied,
                productType: "",
                region: "",
                tag: "",
                page: 1,
              })
            }
            onToggle={(field, value) => search.apply(toggleFacet(applied, field, value))}
            state={applied}
          />

          <section className="surface store-results" aria-live="polite">
            <div className="store-results__header">
              <div>
                <span className="eyebrow">Results</span>
                <h2>{data.total} products</h2>
                <PaginationSummary page={data.page} pageSize={data.pageSize} total={data.total} />
              </div>
              <label className="store-sort">
                Sort by
                <select
                  onChange={(event) =>
                    search.apply({
                      ...applied,
                      sort: event.target.value as typeof applied.sort,
                      page: 1,
                    })
                  }
                  value={applied.sort}
                >
                  <option value="relevance">Relevance</option>
                  <option value="title">Title</option>
                  <option value="coverage">Newest coverage</option>
                </select>
              </label>
              {search.isFetching ? <span className="store-chip">Refreshing</span> : null}
            </div>

            {data.relaxed ? (
              <p className="store-broadened" role="status">
                No products match all of your terms. Showing the closest matches instead.
              </p>
            ) : null}

            {search.isError ? (
              <ErrorState onRetry={search.refetch} />
            ) : (
              <div className="store-result-list">
                {data.products.map((product) => (
                  <StoreResultCard
                    key={product.id}
                    product={product}
                    showMatchReasons={applied.query !== ""}
                  />
                ))}
                {data.products.length === 0 ? (
                  pastLastPage ? (
                    <div className="store-past-end" role="status">
                      <p>
                        Page {applied.page} is past the end of these {data.total} results.
                      </p>
                      <button
                        className="store-action"
                        onClick={() => search.apply({ ...applied, page: 1 })}
                        type="button"
                      >
                        Back to the first page
                      </button>
                    </div>
                  ) : (
                    <EmptyState
                      hint="Try a different term, remove a filter, or widen the coverage dates."
                      title="No products match this search"
                    />
                  )
                ) : null}
              </div>
            )}

            <PaginationControls
              onSelect={(page) => search.apply({ ...applied, page })}
              page={data.page}
              totalPages={data.totalPages}
            />
          </section>
        </section>
      )}
    </div>
  );
}
