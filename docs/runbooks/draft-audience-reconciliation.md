# Draft Audience Reconciliation

Run this procedure before enabling relational draft-audience reads on a release
candidate, after restoring a database, and after any incident involving ticket
assignments or linked draft products. The command derives relationships only
from validated relational ticket aggregates.

## Inspect

Set `COEUS_DATABASE_URL` and `COEUS_PERSISTENCE_PROVIDER=postgres`, then run:

```powershell
uv run --directory apps/api python -m coeus.tools.reconcile_draft_audiences
```

The default is read-only. Use `--json` to preserve machine-readable cutover
evidence. A non-zero exit means the indexed projection has missing or extra
relationships and cutover must remain blocked.

Expected rows cover active analyst assignments, the responsible manager who
made each assignment and the active assigned QC reviewer for every linked draft
product. Creator and privileged-role access are validated directly from the
current product and user objects. Legacy unclaimed QC tickets intentionally
produce no QC audience row and must never be widened to every QC-role user.

## Apply a reviewed repair

```powershell
uv run --directory apps/api python -m coeus.tools.reconcile_draft_audiences `
  --apply --operator "release-operator" `
  --reason "release candidate audience reconciliation"
```

The repair runs at PostgreSQL `SERIALIZABLE` isolation. It first validates every
ticket's canonical hash, identity, requester, lifecycle and capacity projection.
It then inserts only missing relationships, deletes only extra audience rows,
recomputes the complete set and commits the repair with one
`draft_audience_reconciled` audit event. A serialization conflict or audit
failure rolls the whole operation back and must be retried from inspection.

## Cutover evidence

Before approval, preserve:

- a zero-drift JSON report after any repair;
- the release-candidate revision and database migration revision;
- the full creator, analyst, manager, administrator, store-manager, unrelated
  user and multi-role test matrix;
- explicit denial evidence for absent or inactive relationships;
- ACG removal, clearance reduction, publication and archive tests; and
- atomic QC claim/release, competing-reviewer denial and QC audience revocation
  evidence.

Do not treat a zero-drift report as proof that the whole authorisation matrix
passes. It proves only that the implemented relational reasons match their
validated ticket source at that database snapshot.
