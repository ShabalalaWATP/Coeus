# Backend Developer Boundaries

Coeus uses inward dependencies and composition at the application edge:

- `domain` owns pure values, invariants and state vocabulary. It imports no
  service, repository, persistence or API module.
- `application/ports` owns focused protocols for passwords, admission,
  embeddings, draft audiences, outbox and workflow transactions.
- `services` orchestrate use cases through those ports. Routes remain thin.
- `repositories` own aggregate collections. `persistence` owns PostgreSQL,
  codec and projection adapters. Neither imports services or API code.
- `composition.py` and explicitly named builders select concrete adapters.

The AST architecture gate enforces lower-layer import rules. Add an interface
only for a real boundary, not to wrap a function with one caller. Prefer
immutable domain values, composition, explicit side effects and typed failures.

## Security-sensitive mutations

Hosted workflow mutations use an expected version or snapshot and commit the
ticket, Store relationship, audit evidence and deterministic outbox intent in
one transaction. Do not add save-then-audit compensation to a hosted path.
Provider calls, email delivery and object bytes remain outside the database
transaction: reserve before acquisition, stage safely, persist durable intent,
then dispatch idempotently.

Unknown codec IDs, canonical-hash disagreement, projection drift and outbox
content collisions fail closed. Stable semantic codec IDs are the writer
format; legacy module-qualified IDs remain readers only through the rollback
window.

## Verification

Run `uv run --directory apps/api pytest`, strict mypy, Ruff, the architecture
gate and `pnpm line-limit`. PostgreSQL-sensitive work must use the disposable
real-database fixtures, not only fake engines. Security changes update the
relevant spec, ADR, threat model and runbook in the same commit.
