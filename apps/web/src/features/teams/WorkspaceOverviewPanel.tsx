import { useMutation, useQuery } from "@tanstack/react-query";
import { Download, RefreshCw } from "lucide-react";

import { ErrorState, LoadingState } from "../../components/ui/PageState";
import {
  createWorkspaceExport,
  downloadWorkspaceExport,
  getWorkspaceAnalytics,
  getWorkspaceOverview,
  type WorkspaceScope,
} from "../../lib/api-client/workspace-operations";

export function WorkspaceOverviewPanel({
  csrfToken,
  exportGrant,
  includeDescendants,
  unitId,
}: {
  csrfToken: string;
  exportGrant?: { id: string; version: number };
  includeDescendants: boolean;
  unitId: string;
}) {
  const scope: WorkspaceScope = includeDescendants ? "descendants" : "direct";
  const overview = useQuery({
    queryKey: ["workspace-overview", unitId, scope],
    queryFn: () => getWorkspaceOverview(unitId, scope),
    retry: false,
  });
  const analytics = useQuery({
    queryKey: ["workspace-analytics", unitId, scope],
    queryFn: () => getWorkspaceAnalytics(unitId, scope),
    retry: false,
  });
  const exporting = useMutation({
    mutationFn: async () => {
      if (!exportGrant) return;
      const job = await createWorkspaceExport(unitId, includeDescendants, exportGrant, csrfToken);
      const content = await downloadWorkspaceExport(job.exportId);
      const url = URL.createObjectURL(content);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "istari-team-export-" + job.exportId + ".csv";
      anchor.click();
      URL.revokeObjectURL(url);
    },
  });

  if (overview.isLoading) return <LoadingState label="Loading team overview" />;
  if (overview.isError) {
    return (
      <ErrorState
        message="The team overview could not be loaded."
        onRetry={() => void overview.refetch()}
      />
    );
  }
  const result = overview.data!;
  return (
    <div className="workspace-overview">
      <header className="workspace-panel-heading">
        <div>
          <h4>Operational overview</h4>
          <p>
            {scope === "descendants" ? "Direct and child-team scope" : "Direct team scope"} ·
            refreshed {new Date(result.generatedAt).toLocaleString("en-GB")}
          </p>
        </div>
        <div className="workspace-panel-actions">
          <button onClick={() => void overview.refetch()} type="button">
            <RefreshCw aria-hidden="true" size={15} /> Refresh
          </button>
          {exportGrant ? (
            <button disabled={exporting.isPending} onClick={() => exporting.mutate()} type="button">
              <Download aria-hidden="true" size={15} />
              {exporting.isPending ? "Preparing export" : "Export operational summary"}
            </button>
          ) : null}
        </div>
      </header>
      <p className="workspace-freshness">
        Snapshot valid until {new Date(result.freshUntil).toLocaleTimeString("en-GB")}.
        {result.suppressed
          ? " Small descendant cohorts are shown as fewer than five to protect privacy."
          : " Every measure states its period and scope."}
      </p>
      <dl className="workspace-metrics">
        {result.metrics.map((metric) => (
          <div key={metric.key}>
            <dt>{metric.label}</dt>
            {/* The scope note belongs inside the value: a definition list may
                only pair dt with dd, so a sibling element is invalid. */}
            <dd>
              <strong>{metric.display}</strong>
              <small>
                {metric.scope === "descendants" ? "Direct and descendants" : "Direct team"} ·{" "}
                {metric.period}
              </small>
            </dd>
          </div>
        ))}
      </dl>
      {analytics.data ? (
        <section aria-labelledby="workspace-assurance-title" className="workspace-assurance">
          <h5 id="workspace-assurance-title">Planning signals</h5>
          <p>{analytics.data.privacyNotice}</p>
          <ul>
            {analytics.data.metrics.map((metric) => (
              <li key={metric.key}>
                <span>{metric.label}</span>
                <strong>{metric.display}</strong>
                <small>{metric.period}</small>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
      {exporting.isError ? (
        <p className="workspace-alert" role="alert">
          The export could not be prepared. Refresh the workspace and try again.
        </p>
      ) : null}
    </div>
  );
}
