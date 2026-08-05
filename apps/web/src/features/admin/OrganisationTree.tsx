import { useQuery } from "@tanstack/react-query";
import { ChevronRight, Network } from "lucide-react";
import type { CSSProperties } from "react";
import { useState } from "react";

import { ErrorState, LoadingState } from "../../components/ui/PageState";
import {
  listOrganisationUnits,
  type OrganisationUnit,
} from "../../lib/api-client/organisation-admin";

type OrganisationTreeProps = {
  onBootstrap: () => void;
  onSelect: (unit: OrganisationUnit) => void;
  selectedId?: string;
};

export function OrganisationTree({ onBootstrap, onSelect, selectedId }: OrganisationTreeProps) {
  const roots = useQuery({
    queryKey: ["organisation-units", "roots"],
    queryFn: () => listOrganisationUnits(),
  });

  if (roots.isLoading) return <LoadingState label="Loading organisation structure" />;
  if (roots.isError) {
    return (
      <ErrorState
        message="Organisation management is unavailable or has not been enabled."
        onRetry={() => void roots.refetch()}
      />
    );
  }
  if (!roots.data?.length) {
    return (
      <div className="organisation-tree__empty">
        <Network aria-hidden="true" size={26} />
        <h2>No organisation root</h2>
        <p>Complete the protected bootstrap ceremony before adding teams.</p>
        <button onClick={onBootstrap} type="button">
          Set up organisation
        </button>
      </div>
    );
  }

  return (
    <ul className="organisation-tree" aria-label="Organisation hierarchy">
      {roots.data.map((unit) => (
        <OrganisationBranch
          depth={0}
          key={unit.id}
          onSelect={onSelect}
          selectedId={selectedId}
          unit={unit}
        />
      ))}
    </ul>
  );
}

type BranchProps = Omit<OrganisationTreeProps, "onBootstrap"> & {
  depth: number;
  unit: OrganisationUnit;
};

function OrganisationBranch({ depth, onSelect, selectedId, unit }: BranchProps) {
  const [expanded, setExpanded] = useState(false);
  const children = useQuery({
    enabled: expanded,
    queryKey: ["organisation-units", unit.id],
    queryFn: () => listOrganisationUnits(unit.id),
  });

  return (
    <li className="organisation-tree__branch">
      <div className="organisation-tree__row" style={{ "--tree-depth": depth } as CSSProperties}>
        <button
          aria-expanded={expanded}
          aria-label={`${expanded ? "Collapse" : "Expand"} ${unit.name}`}
          className="organisation-tree__toggle"
          onClick={() => setExpanded((current) => !current)}
          type="button"
        >
          <ChevronRight aria-hidden="true" size={16} />
        </button>
        <button
          aria-current={selectedId === unit.id ? "true" : undefined}
          className="organisation-tree__unit"
          onClick={() => onSelect(unit)}
          type="button"
        >
          <strong>{unit.shortName}</strong>
          <span>{unit.name}</span>
          {!unit.isActive ? <small>Inactive</small> : null}
        </button>
      </div>
      {expanded ? (
        <div className="organisation-tree__children">
          {children.isLoading ? <p role="status">Loading child units…</p> : null}
          {children.isError ? (
            <button onClick={() => void children.refetch()} type="button">
              Child units could not be loaded. Retry
            </button>
          ) : null}
          {children.data?.length === 0 ? <p>No child units</p> : null}
          {children.data?.length ? (
            <ul>
              {children.data.map((child) => (
                <OrganisationBranch
                  depth={depth + 1}
                  key={child.id}
                  onSelect={onSelect}
                  selectedId={selectedId}
                  unit={child}
                />
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
    </li>
  );
}
