# Security scan remediation, 2026-07-21

## Goal

Close the 15 validated findings from sealed standard security scan
`59eb4efa-4acb-4504-b43c-bdab86f43cd7` of revision
`d1adc99fa6dc5585975c9fdd68a2bea551d2a769` without removing supported
features or changing successful API response shapes.

The scan is a standard review, not the clean-candidate deep scan required for
production release. Remediation must be followed by the repository quality
gates and a new security scan of the resulting revision.

## Security invariants

- JIOC oversight remains bounded. It does not grant access to the global audit
  stream, protected identifiers or unrestricted event metadata.
- RFI responses expose only product-derived state, outcomes, counts and evidence
  visible to the current caller.
- Cross-user team calendar writes require both current team-management
  permission and the exact current manager relationship.
- Asset-token redemption repeats current action and object authorisation. A
  pre-issued token cannot preserve a permission removed from the user.
- Credential reset and product submission cannot commit after the acting
  principal or relevant ACG authority has been revoked.
- Every Store and analyst upload passes the same content-derived, fail-closed
  document admission controls before durable publication.
- Office relationships are evaluated semantically, not by raw XML spelling.
- PDF and Office archive resource budgets are enforced before or during the
  work they govern.
- Provider responses are bounded while streaming and have an absolute total
  deadline in addition to inactivity timeouts.
- Store pagination cannot select an unbounded PostgreSQL result window.

## Compatibility requirements

- Valid PDF, DOCX, PPTX and supported image uploads retain their current
  successful workflows and byte identity.
- Current Administrators retain global audit access. JIOC review, intervention,
  consolidation, comments and analytics remain unchanged.
- Current managers may write team calendar entries for their team, and members
  may continue to write their own entries.
- Authorised users can still download and preview visible products with valid
  current permissions, including documented break-glass behaviour.
- Valid provider JSON and Realtime SDP responses retain current return shapes
  and error mapping.
- Normal Store page and page-size requests retain their response schema;
  out-of-policy result windows fail explicitly rather than consuming unbounded
  work.
- Valid analyst submissions and authorised administrative credential resets
  keep their existing success semantics and audit evidence.

## Acceptance criteria

- Each original PoC or a repository-native equivalent fails safely after the
  change, with a positive control through the same boundary.
- XML quoting and whitespace variants cannot bypass Office relationship policy.
- PDF extraction stops when its aggregate character budget is exceeded, and an
  over-member Office archive is rejected before object-heavy parsing.
- Store uploads use content-derived processing and leave no product or object
  residue after rejection.
- Provider slow-drip and oversized responses release bounded capacity without
  full buffering or indefinite retention.
- Deterministic race tests prove actor and relationship revocation wins before
  protected state commits.
- Hidden-positive and no-visible-result RFI responses are indistinguishable to
  an unauthorised collaborator.
- Backend and frontend line and branch coverage remain at least 95 percent.
- Formatting, linting, typing, line-limit, architecture and contract gates pass.
- Threat-model, ADR and remediation evidence identify residual operational risk
  and the need for a fresh scan.

## Completion evidence, 22 July 2026

All 15 reportable findings are mitigated. Repository-native regressions cover
the original exploit shapes and the additional mixed-visibility, cross-ticket,
authority-revocation, lock-order, slow-drip and ZIP64 compatibility variants
identified during independent review.

- Backend: 1,522 passed and one intentional PostgreSQL compatibility skip, at
  98.14 per cent line and 95.05 per cent branch coverage.
- Frontend: 536 passed, at 98.63 per cent line, 95.05 per cent branch and 95.10
  per cent function coverage.
- Production build, lint, formatting, strict typing, architecture, contracts,
  documentation, security policy, dead-code and 350-line gates passed.
- Bandit, `pip-audit` and `pnpm audit --audit-level high` passed with no known
  dependency vulnerabilities. Scoped pnpm overrides keep the transitive
  `brace-expansion` and `js-yaml` versions on patched releases.
- Independent code-quality and security re-reviews reported no remaining
  actionable findings in the settled diff.

This completion evidence closes the remediation milestone. A new sealed scan
of the resulting revision is still required before treating it as a clean
production release candidate.

## Follow-up scan

Standard scan `5af0222d-05d1-4c46-a090-018aff45db2d` subsequently found three
Medium and eight Low issues in the working-tree snapshot. Their separate
[remediation contract and focused evidence](security-scan-remediation-2026-07-22.md)
retain full repository gates and a fresh clean-revision scan as pending work.
