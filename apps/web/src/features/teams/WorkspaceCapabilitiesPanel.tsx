import { useQuery } from "@tanstack/react-query";
import { BadgeCheck, CircleAlert } from "lucide-react";

import { ErrorState, LoadingState } from "../../components/ui/PageState";
import {
  getWorkspaceCapabilities,
  type WorkspaceScope,
} from "../../lib/api-client/workspace-operations";

export function WorkspaceCapabilitiesPanel({
  includeDescendants,
  unitId,
}: {
  includeDescendants: boolean;
  unitId: string;
}) {
  const scope: WorkspaceScope = includeDescendants ? "descendants" : "direct";
  const capabilities = useQuery({
    queryKey: ["workspace-capabilities", unitId, scope],
    queryFn: () => getWorkspaceCapabilities(unitId, scope),
    retry: false,
  });
  if (capabilities.isLoading) return <LoadingState label="Loading capability coverage" />;
  if (capabilities.isError) {
    return (
      <ErrorState
        message="Capability coverage could not be loaded."
        onRetry={() => void capabilities.refetch()}
      />
    );
  }
  return (
    <section className="workspace-capabilities" aria-labelledby="workspace-capabilities-title">
      <header className="workspace-panel-heading">
        <div>
          <h4 id="workspace-capabilities-title">Capabilities</h4>
          <p>
            Required team capabilities compared with current verified competencies. These are
            coverage signals, not individual performance scores.
          </p>
        </div>
      </header>
      {capabilities.data!.items.length === 0 ? (
        <p>No capability requirements are configured.</p>
      ) : null}
      <table>
        <caption>Verified team capability coverage</caption>
        <thead>
          <tr>
            <th scope="col">Capability</th>
            <th scope="col">Required level</th>
            <th scope="col">Verified people</th>
            <th scope="col">Coverage</th>
          </tr>
        </thead>
        <tbody>
          {capabilities.data!.items.map((capability) => (
            <tr key={capability.capabilityId}>
              <th scope="row">{capability.capabilityId.replaceAll("_", " ")}</th>
              <td>{capability.requiredProficiency}</td>
              <td>{capability.display}</td>
              <td>
                {capability.gap === null ? (
                  "Suppressed"
                ) : capability.gap ? (
                  <span className="status-chip status-chip--warning">
                    <CircleAlert aria-hidden="true" size={14} /> Gap
                  </span>
                ) : (
                  <span className="status-chip status-chip--success">
                    <BadgeCheck aria-hidden="true" size={14} /> Covered
                  </span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
