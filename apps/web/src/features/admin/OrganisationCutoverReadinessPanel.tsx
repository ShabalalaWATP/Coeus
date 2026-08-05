import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, CircleX, RefreshCw, ShieldCheck } from "lucide-react";

import {
  getCutoverReadiness,
  type CutoverReadinessCheck,
  type CutoverReadinessCheckCode,
} from "../../lib/api-client/cutover-readiness";

const CHECK_LABELS: Record<CutoverReadinessCheckCode, string> = {
  migration_head: "Database changes are up to date",
  organisation_topology: "The organisation structure is consistent",
  identity_projection: "User accounts are prepared",
  identity_reference_parity: "User references agree",
  blocking_findings: "No blocking data issues remain",
  workflow_ownership: "Every workflow has an owner",
  package_integrity: "Work packages are consistent",
  reservation_integrity: "Capacity reservations are consistent",
  routing_leaf_coverage: "Delivery teams are covered",
  routing_capability_mappings: "Capabilities are mapped to teams",
  jioc_service_grant: "The JIOC service has the required access",
  routing_approval_evidence: "Routing approval evidence is recorded",
  browser_evidence: "User journeys have been checked",
  ci_evidence: "Automated checks have passed",
  security_evidence: "Security checks have passed",
};

function countText(check: CutoverReadinessCheck) {
  return `${check.observedCount} of ${check.requiredCount}`;
}

export function OrganisationCutoverReadinessPanel() {
  const query = useQuery({
    queryKey: ["organisation-cutover-readiness"],
    queryFn: getCutoverReadiness,
    retry: false,
  });

  if (query.isPending) {
    return (
      <section className="cutover-readiness" aria-busy="true" aria-live="polite">
        <p>Checking whether the organisation is ready for a controlled service change…</p>
      </section>
    );
  }

  if (query.isError) {
    return (
      <section
        className="cutover-readiness cutover-readiness--error"
        aria-labelledby="readiness-title"
      >
        <div>
          <CircleX aria-hidden="true" size={22} />
          <div>
            <h2 id="readiness-title">Readiness could not be checked</h2>
            <p>The organisation remains on its current service. Try the read-only check again.</p>
          </div>
        </div>
        <button onClick={() => void query.refetch()} type="button">
          <RefreshCw aria-hidden="true" size={16} /> Retry readiness check
        </button>
      </section>
    );
  }

  const checks = query.data.checks;
  if (checks.length === 0) {
    return (
      <section
        className="cutover-readiness cutover-readiness--error"
        aria-labelledby="readiness-title"
      >
        <div>
          <AlertTriangle aria-hidden="true" size={22} />
          <div>
            <h2 id="readiness-title">No readiness checks were returned</h2>
            <p>No service change should be considered until the checks are available.</p>
          </div>
        </div>
        <button onClick={() => void query.refetch()} type="button">
          <RefreshCw aria-hidden="true" size={16} /> Check again
        </button>
      </section>
    );
  }

  const passed = checks.filter((check) => check.status === "passed");
  const blocked = checks.filter((check) => check.status !== "passed");

  return (
    <section
      className={`cutover-readiness cutover-readiness--${query.data.ready ? "ready" : "blocked"}`}
      aria-labelledby="readiness-title"
    >
      <header>
        {query.data.ready ? (
          <CheckCircle2 aria-hidden="true" size={23} />
        ) : (
          <ShieldCheck aria-hidden="true" size={23} />
        )}
        <div>
          <span className="eyebrow">Read-only readiness check</span>
          <h2 id="readiness-title">
            {query.data.ready
              ? "Ready for a controlled service change"
              : "Not ready to change services"}
          </h2>
          <p>
            {query.data.ready
              ? "Every required check has passed. This page does not make or approve a change."
              : "Current services stay in place. Resolve the items below before considering a change."}
          </p>
        </div>
        <dl className="cutover-readiness__counts" aria-label="Readiness check totals">
          <div>
            <dt>Passed</dt>
            <dd>{passed.length}</dd>
          </div>
          <div>
            <dt>Need attention</dt>
            <dd>{blocked.length}</dd>
          </div>
          <div>
            <dt>Total</dt>
            <dd>{checks.length}</dd>
          </div>
        </dl>
      </header>

      {blocked.length > 0 && (
        <div className="cutover-readiness__blockers" aria-labelledby="readiness-blockers-title">
          <h3 id="readiness-blockers-title">What needs attention</h3>
          <ul>
            {blocked.map((check) => (
              <li key={check.code}>
                <AlertTriangle aria-hidden="true" size={17} />
                <span>
                  <strong>{CHECK_LABELS[check.code]}</strong>
                  <small>
                    {check.status === "error" ? "Could not be verified" : "Requirement not met"}
                    {` · ${countText(check)}`}
                  </small>
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <details className="cutover-readiness__technical">
        <summary>Technical details</summary>
        <ul>
          {checks.map((check) => (
            <li key={check.code}>
              <code>{check.code}</code>
              <span>{check.status}</span>
              <span>{countText(check)}</span>
            </li>
          ))}
        </ul>
      </details>
    </section>
  );
}
