# Documentation maintenance

## Purpose

Keep Istari documentation accurate, navigable and explicit about time. A valid
link is not enough: readers must be able to tell whether a document describes
the shipped system, a decision at a point in time, an acceptance contract, or
historical evidence.

## Sources of truth

Use this order when documents appear to disagree:

1. Shipped code, configuration, migrations, generated OpenAPI and executable
   checks define actual behaviour.
2. Current guides and runbooks describe the supported operator and user
   journeys.
3. The [current delivery tracker](../MASTER_IMPLEMENTATION_PLAN.md) summarises
   implementation, residual risk and release gates. The
   [root blueprint](../../coeus_spec_driven_implementation_plan.md) preserves
   the original design and carries a reciprocal current-delivery overlay.
4. Feature specifications define acceptance contracts. They remain useful
   historical evidence after implementation or supersession.
5. ADRs record why a decision was accepted. Later ADRs may narrow or supersede
   an earlier decision without rewriting its history.
6. Threat models describe the boundary and residual risks for their stated
   scope. They are cumulative unless a later model explicitly retires a risk.
7. Development stories and dated security ledgers are chronology and evidence,
   not current operating instructions.

If code and current documentation differ, update the documentation in the same
change or record a blocking issue. Do not silently reinterpret a historical
record to make it look current.

## Required document updates

| Change                            | Documentation that must be reviewed                                              |
| --------------------------------- | -------------------------------------------------------------------------------- |
| User journey, role or permission  | User Guide, Roles and User Stories, relevant spec and threat model               |
| API or automation boundary        | API usage guide, AI Agents, OpenAPI, relevant spec and threat model              |
| Persistence or service topology   | Architecture, deployment guide, setup/runbook and ADR                            |
| Security control or residual risk | Threat model, security evidence, delivery tracker and applicable ADR/spec        |
| Configuration or command          | `.env.example`, Setup, component README and applicable runbook                   |
| Release evidence                  | Delivery tracker, applicable remediation spec/threat model and development story |

Security scan closure and production-release closure are different claims.
Production requires authorised staging verification and a fresh sealed
whole-repository deep scan of the exact immutable release candidate, with no
unresolved baseline occurrence or new reportable finding.

## Lifecycle and linking rules

- Put current, supported instructions in guides and runbooks. Include the
  supported boundary, such as synthetic local/test, hosted reference, or
  production.
- Give dated evidence an explicit date, inspected revision and unresolved gate.
- Link companion spec, ADR and threat model records in both directions.
- When a record is superseded, keep it and add a prominent clickable successor
  link. Do not delete the decision history.
- Use the [specification index](../specs/README.md), [ADR index](../adr/README.md)
  and [threat-model index](../threat-model/README.md) to keep every record
  discoverable.
- Keep local links relative, include heading fragments where they improve
  navigation, and avoid code-formatted paths when a clickable link is possible.

## Audit checklist

From the repository root:

```powershell
corepack pnpm docs:check
corepack pnpm mermaid:check
corepack pnpm format:check
corepack pnpm line-limit
corepack pnpm architecture:check
corepack pnpm security-policy:check
docker compose config --quiet
```

`docs:check` enumerates every tracked or non-ignored new Markdown file through
Git and validates local files, images and GitHub-style heading anchors.
`mermaid:check` parses every Mermaid block with the pinned local renderer and
requires Atlas diagrams to use the stable allowlisted types plus `accTitle` and
`accDescr`. It does not prove compatibility with GitHub's future renderer
versions, so visual review remains part of pull-request review. External links
still need periodic review because CI deliberately does not make network
availability a documentation gate.

For a deep audit, also compare current guides with route policy, settings,
migrations, Compose, workflow definitions and the latest immutable verification
evidence. Record material corrections in the current development story.
