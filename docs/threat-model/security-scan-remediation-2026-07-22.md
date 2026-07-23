# Follow-up security scan remediation threat model, 2026-07-22

## Scope

Remediation of the three Medium and eight Low findings from standard scan
`5af0222d-05d1-4c46-a090-018aff45db2d`. The scan covered a working-tree snapshot
based on revision `d1adc99fa6dc5585975c9fdd68a2bea551d2a769`, not a clean
release candidate. The supported deployment remains local, loopback-bound and
single-writer.

## Assets and actors

Protected assets include administrator role and clearance authority, account
status, active sessions, ticket and conversation state, RFI and active-work
results, QC decisions, published product bytes, indexes, dissemination and audit
evidence. Availability assets include the API event loop, document-processing
capacity and provider circuit state.

Relevant attackers are an initially authorised principal whose authority is
revoked during a request, a concurrent administrator, a malicious analyst
document and a compromised or malfunctioning configured provider.

## Trust boundaries

- Request-time identity and object checks to the final transactional commit.
- The exact initiating session to delayed interactive workflow commits.
- Mutable user, session and permission state to protected workflow effects.
- ACG, product, team, draft and recipient visibility to RFI and QC effects.
- Compressed PDF content and Form streams to decoded parser work.
- DOCX relationship and table XML to the `python-docx` object model.
- Bounded provider bytes to recursive JSON decoding, fallback and circuit state.
- FastAPI's event loop to synchronous third-party document parsers.

## Threats and controls

| Threat | Required and implemented control |
| --- | --- |
| A revoked administrator changes another user's role, clearance or status. | All three mutations atomically compare exact current actor and target state under the repository authority boundary, including the required action permission. |
| Ticket creation commits after the creator is disabled, logged out or loses `CHAT_USE`. | The transaction receives the exact expected live `UserAccount` and required permission, then confirms authority inside the same commit as ticket and audit state. |
| Active-work or RFI results persist after the actor or initiating session loses authority. | The final mutation requires the exact live account, permission and initiating session. Active-work results and audit commit atomically. RFI confirms requester active-ACG membership, then locks and revalidates the union of offered product IDs and all persisted grounded-evidence product IDs. |
| Provider-assisted chat persists after current chat authority is revoked. | Chat mutation carries exact live user, `CHAT_USE`, object authority and the initiating session to the final transaction rather than trusting the request-time snapshot. |
| QC publication completes after reviewer, initiating-session or release-scope revocation. | Guarded release requires the exact initiating session and confirms exact live reviewer, QC-team membership, draft access, release ACG authority and recipient visibility. Another session cannot authorise the old operation; restoring the exact initiating session is the positive control. Publication, indexing, dissemination, outbox and audit occur only after confirmation. |
| Added authority checks introduce deadlocks. | Every protected workflow and submission path acquires mutable subjects in the order users, sessions, access, teams, products, then ticket. Local guards preserve the equivalent serial order. |
| An alternate workflow composition silently omits live authority. | Composition fails closed unless it supplies the required authority guard; three focused tests cover this denial contract. |
| Deep provider JSON escapes fallback or circuit accounting. | Nesting is preflighted to depth 32, recursion and validation failures normalise to safe invalid output, and provider failure is counted exactly once. |
| A compact PDF expands into excessive decoded work. | Content and Form streams are limited to 1,000,000 decoded bytes each and 8,000,000 per document, with 2,048 stream invocations, 2,048 Form invocations, 100,000 operations and Form depth 32. Inherited resources, resource-free content, repeated Forms and cyclic Forms are counted or rejected safely. |
| DOCX `w:gridSpan` or XML structure expands excessive work. | Bounded XML preflight limits rows to 1,024 logical cells, documents to 10,000 cells, XML depth to 64 and semantic work to 50,000 units before `python-docx` constructs the table model. |
| Document parsing blocks unrelated asynchronous work. | Analyst PDF and DOCX extraction is dispatched with `asyncio.to_thread`; admission and semantic limits bound known amplification dimensions. |
| Request cancellation releases capacity or removes a file while parsing still uses it. | Staging and multipart exit are cancellation-safe. Submission retains its admission reservation and staged file until the parser thread exits, then performs deterministic cleanup without publication residue. |

## Verification evidence

- Seventeen administrator authority tests cover role, clearance and status
  success, revocation, target conflict and rollback behaviour.
- Ninety-nine local and four real PostgreSQL workflow authority tests cover
  creation, initiating sessions, discovery, RFI, chat, QC release, visibility,
  lock order, atomic audit and fail-closed composition.
- The combined real-PostgreSQL lock-order suite passed 5/5 after
  workflow and submission paths adopted the canonical order. It includes QC
  session-deletion denial and a restored-session positive control.
- The expanded local focused compatibility suite passed 77/77, including QC
  initiating-session and non-offered RFI evidence-product races.
- One hundred and twenty-four broader parser and cancellation tests cover JSON,
  PDF, DOCX, staging, multipart exit and submission compatibility controls.
- Five submission-race tests and 31 product/indexing tests cover publication,
  cleanup and compatibility effects.
- Parser-service coverage is 98.53 per cent and upload-route coverage is
  95.92 per cent. Ruff, mypy, line-limit and diff-focused checks passed.
- Python and pnpm dependency audits reported no known vulnerabilities.

## Residual risk and release gates

- `asyncio.to_thread` protects event-loop scheduling but is not a killable
  process sandbox. Unexpected third-party parser CPU, memory or native-code
  behaviour still shares the API process.
- Format-specific limits cover the demonstrated PDF, DOCX and JSON dimensions;
  new parser types and semantic expansion features require variant review.
- Exact live-account guards protect only callers that carry the authority
  requirement to the commit owner. New protected writes must use the same
  fail-closed contract.
- Full PostgreSQL-backed verification passed 1,606 tests with one intentional
  skip at 98.23/95.33 per cent line/branch coverage; the 537-test frontend suite
  passed at 98.63/95.03 per cent line/branch coverage.
- A fresh sealed scan of a clean immutable revision is required before the 11
  findings can be treated as release-closed.
