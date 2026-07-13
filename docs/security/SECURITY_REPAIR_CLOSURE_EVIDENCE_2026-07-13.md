# Sprint 17 Security Repair Closure Evidence

## Status

Status: provisional implementation evidence, not release closure.

Applicable branch: `codex/security-repair-hardening-plan`.

Evidence revision at last update: substantive candidate `0246d4d2`.

Last verified: 2026-07-13 on Windows with PostgreSQL 16 plus pgvector, local
object storage and mock AI providers.

This ledger traces the baseline from deep scan
`abf0e143-4656-4646-b133-6fea0d6661ee`. The repository owner explicitly
deferred the fresh sealed scan on 2026-07-13. Consequently, this ledger records
implemented and verified controls but does not claim fresh-scan closure. Local
evidence is not staging or production accreditation.

## Reportable Finding Traceability

| Finding | Implemented control | Primary regression evidence | Current state |
| --- | --- | --- | --- |
| `COEUS-CAN-001` draft search | One object-aware draft policy plus indexed principal projection and query prefilter, including an atomically assigned QC reviewer. | `test_draft_audience_security.py`; `test_qc_draft_audience_api.py`; PostgreSQL claim/projection tests; PostgreSQL browser same-ACG denial; `postgres/test_ticket_shadow.py`. | Implemented and locally exercised for assigned QC and unrelated-reviewer denial; fresh-scan closure is deferred. |
| `COEUS-CAN-002` draft detail | Repository prefilter and selected-object checks consume the same audience policy and return non-enumerating errors. | `test_draft_audience_security.py`; `test_store_projection.py`; browser known-UUID draft denial. | Implemented and locally exercised. The full intended-audience matrix remains open; fresh-scan closure is deferred. |
| `COEUS-CAN-006` draft asset | Grant and redemption reauthorise permission, ACG, clearance, lifecycle, audience and user-bound token authority. QC review grants product detail but does not add `PRODUCT_DOWNLOAD`. | `test_draft_audience_security.py`; `test_analyst_linked_product_reauthorisation.py`; `test_qc_draft_audience_api.py`; browser known-asset grant denial and released-byte download. | Implemented. Assigned QC draft visibility does not broaden asset-download permission. |
| `COEUS-CAN-012` upload memory | Authentication-first parsing, cumulative receive cap, incremental hashing, staged promotion, deterministic cleanup and shared byte leases. | `test_upload_admission_security.py`; `postgres/test_shared_resource_admission.py`; browser `413` recovery with retained form input and no product; `SECURITY_REPAIR_BASELINE_2026-07-13.md`. | Implemented. Authorised ingress and multi-size staging measurements remain external release evidence. |
| `COEUS-CAN-026` chat cost | Principal and deployment provider leases, retained-ticket admission, bounded drafts, circuit breaker and exact refund semantics. | `test_provider_admission.py`; `test_ticket_admission.py`; `test_conversation_service.py`; PostgreSQL shared-admission suites; browser `429` recovery with retained message. | Implemented and locally exercised; fresh-scan closure is deferred. |
| `COEUS-CAN-027` corpus rewrite | Versioned per-ticket relational aggregate, compare-and-swap, ticket quotas and audited recovery. | `postgres/test_ticket_shadow.py::test_relational_mutation_statement_count_is_stable_at_ten_thousand_rows`; ticket-capacity recovery suites. | Implemented with stable-cost proof; fresh-scan closure is deferred. |
| `COEUS-CAN-028` pre-auth spool | Session and CSRF rejection occur before explicit multipart parsing; bodies without content length remain capped. | `test_upload_admission_security.py::test_security_rejection_happens_before_multipart_spooling`; content-length-free rejection test. | Implemented with zero-spool proof; staging ingress remains open. |
| `COEUS-CAN-030` auth history | Atomic bounded username and source histories with injected clocks, expiry and cardinality limits. | `test_auth_attempt_repositories.py::test_source_attempt_repository_bounds_denied_history`; `test_auth_service.py`. | Implemented with 10,000-attempt proof; fresh-scan closure is deferred. |
| `COEUS-CAN-035` embedding fan-out | Fixed candidate work limit, normalised single-flight cache and shared provider admission. | `test_similar_request_scoring.py::test_similarity_embedding_work_is_bounded_for_large_candidate_corpus`; provider-admission suites. | Implemented and bounded; fresh-scan closure is deferred. |
| `COEUS-CAN-036` Store embeddings | Store queries use normalised cached embeddings before shared provider reservation. | `test_embedding_admission_security.py::test_store_normalises_and_caches_queries_before_provider_admission`; `test_embeddings.py`. | Implemented with endpoint-level cache proof; fresh-scan closure is deferred. |
| `COEUS-CAN-037` RFI embeddings | One-run state gate, bounded ranking, ticket quotas and principal/deployment provider admission precede mutation. | `test_embedding_admission_security.py::test_rfi_one_run_gate_and_provider_budget_precede_mutation`; `test_async_search_limits.py`; PostgreSQL shared-admission suites. | Implemented and locally exercised; fresh-scan closure is deferred. |
| `COEUS-CAN-044` QC/cancel race | Every competing transition uses version predicates; QC release commits ticket, product, audit and outbox atomically. | Parametrised `test_qc_cancel_race_security.py`; `postgres/test_workflow_transaction.py`; PostgreSQL browser release. | Implemented with both winner orders and atomic transaction proof; fresh-scan closure is deferred. |

## Deferred Decision Traceability

| Decision | Current conclusion and control | Evidence | Remaining boundary |
| --- | --- | --- | --- |
| `COEUS-CAN-003` trusted proxy | Forwarded addresses are ignored unless the socket peer is in an explicit trusted CIDR; unsafe or incomplete configuration fails startup. | `test_hardening_units.py`; `test_runtime_security_config.py`; API security guide. | Authorised staging must prove the real proxy chain and prevent direct API reachability. |
| `COEUS-CAN-005` credentialed CORS | Wildcards, credentials in origins and non-origin URL components fail configuration; supported origins are explicit. | `test_runtime_security_config.py`; `.env.example`; deployment guide. | Authorised sibling-origin CORS plus CSRF exercise remains a staging gate. |
| `COEUS-CAN-007` releasability | Current public-safe runtime accepts only the synthetic `MOCK` marker; invalid persisted values fail closed during search and detail. | ADR 0027; `test_store_acg_policy_api.py::test_unsupported_persisted_release_markers_fail_closed_in_search_and_detail`. | Staging policy acceptance remains external; code policy is locally complete. |
| `COEUS-CAN-008` handling caveats | Current public-safe runtime accepts only `MOCK DATA ONLY`; invalid persisted values fail closed. | ADR 0027; the same Store search/detail regression and request/QC boundary tests. | Staging policy acceptance remains external; code policy is locally complete. |

## Structural And Compatibility Evidence

- `QcAssignmentService` owns eligibility, safe queue summaries, atomic
  self-claim, release, separation of duties and assigned-only detail. The
  existing QC service delegates assignment policy and retains its release
  orchestration responsibility.
- Application ports own draft audience, admission, ticket repository, workflow
  transaction, audit and outbox contracts. The architecture import gate rejects
  lower-layer dependencies on service or API modules.
- Broad backend and frontend orchestration modules were split behind existing
  contracts. Generated OpenAPI types and semantic compatibility checks remain
  release gates.
- N-1 revision `3e27c82d4b62efb683b3fbb81d2486bccafd8fb0`
  starts on the expanded schema, mutates a ticket, and exits. Forward
  reconciliation verifies canonical hashes, normalises the legacy payload and
  allows the next current relational compare-and-swap write.
- The ten-stage PostgreSQL browser suite migrates a disposable database and
  proves search plus known-object draft denial, oversized-upload `413` recovery
  without mutation, retained-ticket `429` recovery without lost input, customer
  intake, JIOC routing, RFA assignment, analyst production, manager approval,
  QC release, Store discovery and exact downloaded bytes.
- Default upload behaviour remains published. The new explicit Draft option
  permits security tests and authorised draft registration without changing
  existing successful submissions.

## Verification Snapshot

The complete local candidate suites reported:

- backend: 960 passed, one N-1 test skipped in the combined run and executed
  separately; the database-enabled full run measured 97.61 percent total
  coverage;
- frontend: 414 passed; 98.69 percent lines, 95.00 percent branches and 96.25
  percent functions;
- mocked/real-memory Playwright: 3 passed;
- PostgreSQL Playwright: 10 passed;
- Bandit, pip-audit, Semgrep, Gitleaks and Checkov: passed with no actionable
  local result;
- API and web production container builds: passed; current-image Trivy scans
  reported zero high or critical vulnerabilities.

After the final test-tool isolation and static recovery-query repair, the delta
gates reported:

- recovery backup unit tests: 9 passed;
- focused Semgrep Python rules: zero findings;
- Ruff formatting and linting: passed.

PR 109 protected GitHub results passed on substantive candidate `0246d4d2`:

- backend run `29271925745` and frontend run `29271925746`;
- CodeQL run `29271925750`, Semgrep run `29271926083`, Checkov run
  `29271926086` and Terraform run `29271925765`;
- Trivy run `29271925725`, ZAP run `29271925821`, and Gitleaks plus SBOM run
  `29271925715`;
- GitHub code-scanning checks for CodeQL, Semgrep OSS, Trivy and Checkov also
  passed.

A fresh sealed deep scan is deliberately deferred and therefore absent from
this evidence.

## Explicit Open Items

- Complete the protected GitHub gates for the final assigned-QC candidate.
- Run authorised staging proxy, CORS, CSRF and ingress checks. No local result
  can replace these topology-dependent checks.
- Record a managed or physical PostgreSQL and object-store restore in staging.
  The current automated drill proves logical application restore only.
- Run a fresh sealed deep scan when the repository owner resumes that work. No
  claim of fresh-scan closure is made in the meantime.
