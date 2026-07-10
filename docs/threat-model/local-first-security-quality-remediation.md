# Local-First Security And Quality Remediation Threat Model

## Status

Implemented and locally verified. Final completion still requires a sealed
whole-repository scan of the immutable delivery revision.

## Scope

The local browser, FastAPI process, PostgreSQL/file state, local object storage,
optional integrations, inactive GCP migration reference and CI verification
changed by the remediation milestone.

## Assets

- Current user identity, roles, clearance and ACG membership.
- Session and login-enforcement state.
- Privileged audit evidence.
- Ticket, linked-product and Store metadata.
- Store asset bytes and integrity metadata.
- Local service availability and bounded compute capacity.

## Required Controls

| Threat | Required local-first control |
| --- | --- |
| Cached product metadata crosses current policy. | Actor-scoped response projection re-checks Store access at serialization time. |
| Similarity and search requests consume corpus-sized work. | Access-filtered candidate budgets, pairwise checks and query-level pagination. |
| Public events overwrite privileged audit history. | Append-only local forensic evidence independent of bounded UI reads. |
| Churn evicts active login enforcement state. | Active enforcement histories remain retained for their full window. |
| Concurrent registration bypasses capacity. | One atomic local reservation covers count, duplicate checks and insert. |
| QC integrity fields differ from served bytes. | Size and SHA-256 are derived after constructing the exact stored bytes. |
| Multiple writers accept or resurrect stale security state. | Current and reference runtime enforce one writer until distributed controls exist. |
| Login rollback overwrites a concurrent failure or lock. | Per-username reset tokens restore prior state only when no later mutation occurred. |
| Concurrent reviewers approve or reject the same registration twice. | One service decision lock serialises the complete decision, account and audit transaction. |
| A failed object write leaves partial bytes at the final key. | Local writes use temporary files plus atomic replacement; callers clean every attempted key. |
| Synchronous embeddings block unrelated API requests. | Similarity HTTP handlers run in FastAPI's worker thread pool and candidate work is capped. |
| Actor-scoped response checks create unbounded N+1 work. | Analyst task responses and linked-product collections have explicit budgets. |
| Lockout configuration disables enforcement. | Pydantic rejects thresholds or durations below one. |
| Dormant cloud automation activates an unsupported runtime. | GitHub performs validation and local builds only; Terraform has a default-deny migration gate. |
| Green CI hides weak branch coverage. | Independent line and branch thresholds fail below 95 percent. |
| Mocked browser tests miss API integration failures. | At least one real browser-to-FastAPI lifecycle runs in CI. |

## Validation Requirements

- Re-run each original exploit reproduction after its patch.
- Exercise a legitimate control through the same boundary.
- Review equivalent callers and alternate malicious inputs.
- Run the complete backend, frontend and security gate set.
- Seal a fresh repository-wide security scan at the final revision.

## Deferred Future-Migration Risks

- Distributed persistence, rate limiting and session revocation.
- GCS, Pub/Sub and worker adapters.
- Live GCP identity, network, rollback and observability validation.
- Malware scanning and strong MIME enforcement for untrusted production files.
