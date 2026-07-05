# Intelligence Store Threat Model

## Scope

Sprint 5 product metadata, asset metadata, upload wizard, search, product detail
and controlled asset access.

## Assets

- Product metadata, tags, source metadata and access caveats.
- ACG assignments and clearance requirements.
- Asset metadata, hashes and object keys.
- Search result counts, facets and product identifiers.
- Controlled download token placeholders.

## Threats And Controls

| Threat | Control in Sprint 5 |
|---|---|
| Search leaks unauthorised product existence through counts or facets. | Search applies RBAC, active ACG, clearance and status filtering before result counts or facet values are calculated. |
| Product detail IDOR exposes metadata for restricted products. | Product detail returns a not-found style error when access policy denies the current user. |
| Asset object key bypasses product access controls. | Asset access is only through an API endpoint that re-evaluates product access and returns an opaque placeholder token. |
| Product is published without ACGs or required metadata. | Product creation validates required metadata, at least one ACG and at least one asset. |
| Product team adds products into unauthorised ACGs. | Non-administrators can create products only with active ACGs they belong to and the matching team permission. |
| Metadata suggestions silently assign access groups. | Suggestions include tags and entities only. ACG assignment remains explicit user input. |
| Real intelligence data enters the public repository. | Sprint 5 stores only synthetic metadata and marks seed products as `MOCK DATA ONLY`; no real product bytes are committed. |

## Deferred Risks

- Malware scanning, file-type validation and storage URL security are deferred
  until real uploads and object storage are implemented.
- Database-level row security and immutable audit constraints are deferred until
  the persistence sprint.
- Vector-search leakage and embedding privacy need a dedicated review when
  pgvector-backed search is introduced.
