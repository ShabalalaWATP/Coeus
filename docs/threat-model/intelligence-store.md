# Intelligence Store Threat Model

## Scope

Sprint 5 product metadata, asset metadata, upload wizard, search, product detail
and controlled asset access.

## Assets

- Product metadata, tags, source metadata and access caveats.
- ACG assignments and clearance requirements.
- Asset metadata, hashes and object keys.
- Search result counts, facets and product identifiers.
- Signed asset download tokens.

## Threats And Controls

| Threat | Control in Sprint 5 |
|---|---|
| Browsing enumerates everything a user's ACGs allow without a stated need. | Unfiltered listing requires the curator-only `store:browse_all` permission (Intelligence Store Manager, administrators); everyone else must supply a search term or filter (`422 search_criteria_required`), so bulk enumeration of visible holdings requires deliberate, logged queries. |
| Search leaks unauthorised product existence through counts or facets. | Search applies RBAC, active ACG, clearance and status filtering before result counts or facet values are calculated. |
| PostgreSQL search predicates drift from the API access rules. | SQL search applies shared-ACG, clearance, draft and archive predicates first, then the Store service rechecks the same API policy before producing counts, facets or product results. |
| Unbounded search text causes expensive database predicates or noisy parser errors. | Search query, metadata filter and pagination inputs are bounded at the FastAPI boundary before they reach PostgreSQL full-text and `ILIKE` predicates. |
| Product detail IDOR exposes metadata for restricted products. | Product detail uses a SQL visible-product lookup, then returns a not-found style error when the API policy denies the current user. |
| Asset object key bypasses product access controls. | Asset access is only through API endpoints that use the SQL visible-product lookup, re-evaluate product access and return or redeem signed asset tokens. Token grant and download responses are `no-store`. Break-glass asset tokens carry an explicit emergency flag, require current restricted-read permission at redemption and are issued only after a reasoned audit event. |
| Product is published without ACGs, required metadata or publication authority. | Product creation defaults to draft and validates required metadata, at least one ACG and at least one asset. Explicit published creation requires `product:publish` in the shared ingestion service used by JSON and multipart routes. Unsupported initial states are rejected before persistence. |
| Product team adds products into unauthorised ACGs. | Non-administrators can create products only with active ACGs they belong to and the matching team permission. |
| Store Manager role becomes blanket report reader. | Store Managers can administer product metadata, assets and ACG assignment, but they do not receive `product:read_restricted`; product detail and downloads still require at least one shared active ACG plus clearance. |
| Site administrator reads restricted report contents through normal store routes. | Normal product search, detail and download paths ignore `product:read_restricted`; administrators outside a product ACG receive not-found. The denied product page shows emergency access only to users with `product:read_restricted`; submitting a reason calls `POST /api/v1/store/products/{id}/break-glass`, requires CSRF and writes `product_break_glass_accessed`. Emergency asset grants use `POST /api/v1/store/products/{id}/assets/{asset_id}/break-glass-access`, require the same restricted-read permission and write `product_asset_break_glass_accessed`. |
| Hybrid browse returns unrelated products because every embedded row is ranked. | Free-text browse hits require lexical membership or vector similarity at the shared floor. Zero-signal candidates are excluded from totals, pages and reasons. |
| Metadata suggestions silently assign access groups. | Suggestions include tags, entities and semantic labels only. ACG assignment remains explicit user input. |
| Real intelligence data enters the public repository. | Sprint 5 stores only synthetic metadata and marks seed products as `MOCK DATA ONLY`; no real product bytes are committed. |

## Deferred Risks

- Malware scanning and stronger MIME verification are still deferred.
- Database-level row security and immutable audit constraints are still deferred.
  Store search, detail and asset grants now apply PostgreSQL-side visibility
  predicates and still recheck API authorisation before returning results.
- Vector-search leakage and embedding privacy are covered in
  `hybrid-search-and-duplicate-detection.md`; production deployments still need
  to classify embeddings as sensitive derived data.
