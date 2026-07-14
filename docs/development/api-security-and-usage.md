# API Security And Usage

The FastAPI surface is under `/api/v1`. Treat every example as synthetic. Do
not send real intelligence, private schemas, credentials or internal URLs to a
local demo or an externally configured model.

## Browser authentication

Login creates an HttpOnly session cookie and returns a CSRF token. Every unsafe
authenticated request must send that token in `X-CSRF-Token`; scripts must also
retain the session cookie. Authorisation is checked again at the requested
object and action. A role or broad permission never proves draft-product or
ticket need-to-know.

Asset download grants are short-lived and bound to the current user, product
and asset. Send the grant in `X-Asset-Token`, not in a URL. Redemption repeats
the live access decision, so a revoked assignment, ACG or account cannot keep
access through an older token.

## Conflict and limit responses

| Status | Meaning | Safe client behaviour |
| ------ | ------- | --------------------- |
| `409` | Expected aggregate version or workflow state is stale | Refresh the object, preserve unsent input and let the user retry the intended action |
| `413` | Upload wire bytes or declared size exceed the supported boundary | Keep the form state and select a smaller synthetic file |
| `429` | Principal or deployment admission is saturated | Honour `Retry-After` when present; do not fan out retries or change identifiers to evade the limit |

Authentication endpoints may return `429 password_capacity_exhausted`. The
capacity is shared across login verification, registration hashing, password
change and administrative reset. Treat the response as non-enumerating, use
bounded backoff and never switch usernames or endpoints to evade it.

Validation failures use `422`; authentication and CSRF failures use `401` or
`403`; hidden object denials may intentionally use `404`. Error bodies expose a
stable code and safe message, not database detail, payloads or secrets.

QC claim and release use `POST` and `DELETE` respectively at
`/api/v1/qc/products/{ticket_id}/claim`, and therefore require the session CSRF
header. A competing reviewer receives `409 qc_already_claimed`; clients should
refresh the queue and must not retry approval or rejection against that item.
Unassigned and other-assigned product detail deliberately returns `404`.

## Upload, search and provider boundaries

Authenticate before multipart parsing. Upload clients provide bounded content
length and must tolerate rejection before file acquisition. The server streams
to an isolated temporary file, verifies measured size and SHA-256, publishes
bytes atomically and removes staging artefacts on failure.

Search, RFI, similarity, remote provider, upload and retained-ticket work have
finite principal and deployment budgets. Remote embedding cache misses use the
provider ledger; cache hits and offline providers do not consume a remote call.
`/api/v1/metrics` exposes only low-cardinality admission labels and should be
restricted to the hosted monitoring network.

## Automation and compatibility

Use the committed OpenAPI document and generated TypeScript declarations as the
contract. CI rejects semantic breaking changes against the frozen baseline.
Never rely on private service attributes, database tables or current error text
when a stable schema field or error code exists.
