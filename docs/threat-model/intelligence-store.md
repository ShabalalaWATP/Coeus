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
- Personal folder names and saved-product references.

## Threats And Controls

| Threat | Control in Sprint 5 |
|---|---|
| Browsing enumerates everything a user's ACGs allow without a stated need. | Unfiltered listing requires the curator-only `store:browse_all` permission (Intelligence Store Manager, administrators); everyone else must supply a search term or filter (`422 search_criteria_required`), so bulk enumeration of visible holdings requires deliberate, logged queries. |
| Search leaks unauthorised product existence through counts or facets. | Search applies RBAC, active ACG, clearance and status filtering before result counts or facet values are calculated. |
| PostgreSQL search predicates drift from the API access rules. | SQL search applies shared-ACG, clearance, draft and archive predicates first, then the Store service rechecks the same API policy before producing counts, facets or product results. |
| Unbounded search text causes expensive database predicates or noisy parser errors. | Search query, metadata filter and pagination inputs are bounded at the FastAPI boundary before they reach PostgreSQL full-text and `ILIKE` predicates. |
| Product detail IDOR exposes metadata for restricted products. | Product detail uses a SQL visible-product lookup, then returns a not-found style error when the API policy denies the current user. |
| A user guesses another user's personal folder or saved-product identifiers. | Library ownership comes only from the authenticated session. Folder lookup is scoped to that user, mutations require CSRF, and cross-user identifiers receive a not-found response. |
| A saved product preserves access after a clearance, ACG, status or audience change. | The library stores references rather than product snapshots. Reads and saves resolve each product through the current Store visibility service; inaccessible items expose no metadata and contribute only to an aggregate unavailable count. |
| Personal folders become an unbounded storage or audit-flood surface. | Names and request bodies are bounded, names are unique per user, and each user is limited to 50 folders and 500 saved products. Successful mutations are audit logged. |
| A crafted product return path is treated as authority or becomes an open redirect. | Return context is presentation-only router state. The UI accepts only the internal `/app/requests/{id}` shape for an RFI return action, and all product access is independently authorised by the API. |
| Asset object key bypasses product access controls. | Asset access is only through API endpoints that use the SQL visible-product lookup, re-evaluate product access and return or redeem signed asset tokens. Token grant and download responses are `no-store`. Break-glass asset tokens carry an explicit emergency flag, require current restricted-read permission at redemption and are issued only after a reasoned audit event. |
| Product is published without ACGs, required metadata or publication authority. | Product creation defaults to draft and validates required metadata, at least one ACG and at least one asset. Explicit published creation requires `product:publish` in the shared ingestion service used by JSON and multipart routes. Unsupported initial states are rejected before persistence. |
| Product team adds products into unauthorised ACGs. | Non-administrators can create products only with active ACGs they belong to and the matching team permission. |
| An authenticated user without product-create authority consumes multipart parser and disk resources. | The upload route checks `product:create_existing` immediately after session and CSRF validation, before admission, multipart parsing or temporary-file creation. The service repeats full status and ACG policy checks before persistence. |
| Access grants, download tokens or protected preview bytes outlive their browser purpose. | Grants and tokens stay in component-local state, never query keys or the shared query cache. Preview Blobs become short-lived object URLs that are revoked on replacement, grant expiry, logout and unmount. |
| Project membership is mistaken for product authority. | Projects store product identifiers only. Every project response resolves each product through the current Store detail policy; hidden identifiers, titles, counts and product-specific activity are omitted. Membership never changes ACGs, clearance or product permissions. |
| Project or subscription identifiers allow cross-user discovery or mutation. | Services scope Projects to current members and Subscriptions to their owner, returning `404` outside that scope. All mutations require CSRF validation and are audited with rollback on audit failure. |
| Saved subscription results preserve information after access is revoked. | Subscriptions persist bounded search criteria only. Opening one performs a fresh Store search using current products and current authority; no result set or hidden count is stored. |
| An ACG administrator selects a group they can administer but have not been granted, or a user tampers with an ACG identifier in a subscription or search URL. | Subscription scope discovery returns active memberships rather than administratively visible groups. Create and update validate every selected ACG against current membership, Store search rejects a selected scope outside current authority with a not-found response, and retrieval uses the selected subset as a narrowing of the normal ACG visibility scope. |
| A controlled PDF preview gains active browser capabilities when made compatible with Edge. | Istari does not invoke the browser PDF plug-in. PDF.js reads the authorised, short-lived Blob in a worker, stops on parsing errors and paints only the selected page into a canvas. It does not attach PDF forms, links, annotations or scripts to the DOM. The application CSP excludes `unsafe-eval`, and other non-raster formats retain an empty iframe sandbox. |
| Store Manager role becomes blanket report reader. | Store Managers can administer product metadata, assets and ACG assignment, but they do not receive `product:read_restricted`; product detail and downloads still require at least one shared active ACG plus clearance. |
| Site administrator reads restricted report contents through normal store routes. | Normal product search, detail and download paths ignore `product:read_restricted`; administrators outside a product ACG receive not-found. The denied product page shows emergency access only to users with `product:read_restricted`; submitting a reason calls `POST /api/v1/store/products/{id}/break-glass`, requires CSRF and writes `product_break_glass_accessed`. Emergency asset grants use `POST /api/v1/store/products/{id}/assets/{asset_id}/break-glass-access`, require the same restricted-read permission and write `product_asset_break_glass_accessed`. |
| Hybrid browse returns unrelated products because every embedded row is ranked. | Free-text browse hits require lexical membership or vector similarity at the shared floor. Zero-signal candidates are excluded from totals, pages and reasons. |
| Metadata suggestions silently assign access groups. | Suggestions include tags, entities and semantic labels only. ACG assignment remains explicit user input. |
| Real intelligence data enters the public repository. | Sprint 5 stores only synthetic metadata and marks seed products as `MOCK DATA ONLY`; no real product bytes are committed. |

## Deferred Risks

- Hosted upload remains unavailable until a malware scanner is configured.
  Local synthetic-data processing performs signature, Office structure and
  hardened XML checks, but production rendition and malware inspection still
  belong in a non-networked resource-limited worker.
- Database-level row security and immutable audit constraints are still deferred.
  Store search, detail and asset grants now apply PostgreSQL-side visibility
  predicates and still recheck API authorisation before returning results.
- Vector-search leakage and embedding privacy are covered in
  `hybrid-search-and-duplicate-detection.md`; production deployments still need
  to classify embeddings as sensitive derived data.
