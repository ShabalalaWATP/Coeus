# Local-First Security And Quality Remediation Threat Model

## Status

Reopened for Sprint 14B. The original 16 findings are closed at `7165e49e`.
Verification scan `a089e83c` reported three Low/P3 integrity findings whose
post-scan fixes require a final immutable verification scan.

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

| Threat                                                                           | Required local-first control                                                                                                                            |
| -------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Cached product metadata crosses current policy.                                  | Actor-scoped response projection re-checks Store access at serialization time.                                                                          |
| Similarity and search requests consume corpus-sized work.                        | Access-filtered candidate budgets, pairwise checks and query-level pagination.                                                                          |
| Public events overwrite privileged audit history.                                | Append-only local forensic evidence independent of bounded UI reads.                                                                                    |
| Churn evicts active login enforcement state.                                     | Active enforcement histories remain retained for their full window.                                                                                     |
| Concurrent registration bypasses capacity.                                       | One atomic local reservation covers count, duplicate checks and insert.                                                                                 |
| QC integrity fields differ from served bytes.                                    | Size and SHA-256 are derived after constructing the exact stored bytes.                                                                                 |
| Multiple writers accept or resurrect stale security state.                       | Current and reference runtime enforce one writer until distributed controls exist.                                                                      |
| Login rollback overwrites a concurrent failure or lock.                          | Per-username reset tokens restore prior state only when no later mutation occurred.                                                                     |
| Concurrent reviewers approve or reject the same registration twice.              | One service decision lock serialises the complete decision, account and audit transaction.                                                              |
| A failed object write leaves partial bytes at the final key.                     | Local writes use temporary files plus atomic replacement; callers clean every attempted key.                                                            |
| Synchronous embeddings block unrelated API requests.                             | Similarity HTTP handlers run in FastAPI's worker thread pool and candidate work is capped.                                                              |
| Actor-scoped response checks create unbounded N+1 work.                          | Analyst task responses and linked-product collections have explicit budgets.                                                                            |
| Lockout configuration disables enforcement.                                      | Pydantic rejects thresholds or durations below one.                                                                                                     |
| Dormant cloud automation activates an unsupported runtime.                       | GitHub performs validation and local builds only; Terraform has a default-deny migration gate.                                                          |
| Green CI hides weak branch coverage.                                             | Independent line and branch thresholds fail below 95 percent.                                                                                           |
| Mocked browser tests miss API integration failures.                              | At least one real browser-to-FastAPI lifecycle runs in CI.                                                                                              |
| A local-network peer authenticates to a wildcard-published PostgreSQL superuser. | Bind PostgreSQL to loopback, generate an uncommitted credential and use a least-privilege application role.                                             |
| Synchronous Store or RFI provider calls stall unrelated work.                    | Use async providers or bounded offload with liveness and concurrency tests.                                                                             |
| Synchronous LLM catalogue or connection-test calls stall unrelated work.         | Run the admin endpoints in FastAPI's worker thread pool, retain provider timeouts and exercise concurrent liveness.                                     |
| Repeated bounded records create unbounded aggregate state and responses.         | Enforce domain count and byte budgets and return paginated or bounded summaries.                                                                        |
| Concurrent downloads multiply whole-object process memory.                       | Stream bytes and enforce per-user and global in-flight byte budgets.                                                                                    |
| Anonymous readiness traffic fans out database connections.                       | Coalesce checks or use a small shared semaphore and dedicated timeout; restrict ingress.                                                                |
| Audit event churn hides older evidence from the shipped UI.                      | Preserve cursors, expose older-event navigation and label page counts honestly.                                                                         |
| ZAP reports warnings while its required status remains green.                    | Remove warning suppression, maintain a reviewed rules file and test a blocking fixture.                                                                 |
| A ticket save succeeds but its required central audit append fails.              | Hold the repository mutation behind a save-plus-confirmation boundary and restore the exact prior snapshot, including absence, before exposing failure. |
| Long-running offloaded work saves or restores a stale aggregate.                 | Apply complete-record changes with atomic expected-snapshot compare-and-swap and conditionally roll back only the exact saved snapshot.                 |
| Compact ticket listing causes detail fan-out or hides older requests.            | Page compact summaries by cursor and fetch full detail only for the selected ticket.                                                                    |
| Browser dictation sends audio through an implementation-dependent provider.      | Require an explicit user action and disclose possible remote browser processing before microphone use; synthetic data remains mandatory.                |

## Validation Requirements

- Re-run each original exploit reproduction after its patch.
- Exercise a legitimate control through the same boundary.
- Review equivalent callers and alternate malicious inputs.
- Run the complete backend, frontend and security gate set.
- Seal a fresh repository-wide security scan at the final revision.
- Re-run all 16 sealed finding PoCs and record equivalent-sink review.
- Re-run the three verification-scan reproductions for exact audit rollback and
  coordinated stale-write rejection.
- Verify that current uncommitted feature work is either integrated into the
  scanned revision or explicitly excluded from the release candidate.

## Deferred Future-Migration Risks

- Distributed persistence, rate limiting and session revocation.
- GCS, Pub/Sub and worker adapters.
- Live GCP identity, network, rollback and observability validation.
- Malware scanning and strong MIME enforcement for untrusted production files.
