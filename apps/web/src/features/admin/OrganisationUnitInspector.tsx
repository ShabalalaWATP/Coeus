import { useQuery } from "@tanstack/react-query";
import { CalendarClock, KeyRound } from "lucide-react";

import { OrganisationCalendarPanel } from "./OrganisationCalendarPanel";
import { LoadingState } from "../../components/ui/PageState";
import {
  listManagementGrants,
  type OrganisationUnit,
} from "../../lib/api-client/organisation-admin";

type InspectorProps = {
  onCreate: () => void;
  onDeactivate: () => void;
  onEdit: () => void;
  onManageAuthority: () => void;
  onManageRoster: () => void;
  onMerge: () => void;
  onReparent: () => void;
  onSplit: () => void;
  unit?: OrganisationUnit;
};

export function OrganisationUnitInspector({
  onCreate,
  onDeactivate,
  onEdit,
  onManageAuthority,
  onManageRoster,
  onMerge,
  onReparent,
  onSplit,
  unit,
}: InspectorProps) {
  const grants = useQuery({
    enabled: unit !== undefined,
    queryKey: ["organisation-grants", unit?.id],
    queryFn: () => listManagementGrants(unit?.id ?? ""),
  });

  if (unit === undefined) {
    return (
      <div className="organisation-inspector__empty">
        <p>Select a unit to inspect its details and delegated authority.</p>
      </div>
    );
  }

  return (
    <div className="organisation-inspector">
      <header>
        <span className="eyebrow">{formatCategory(unit.category)}</span>
        <h2>{unit.name}</h2>
        <p>{unit.description || "No description has been recorded."}</p>
        {unit.isActive ? (
          <div className="organisation-inspector__actions">
            <button onClick={onCreate} type="button">
              Add child unit
            </button>
            <button onClick={onEdit} type="button">
              Edit unit
            </button>
            <button onClick={onManageAuthority} type="button">
              Manage authority
            </button>
            <button onClick={onManageRoster} type="button">
              Manage roster
            </button>
            {unit.parentId ? (
              <button onClick={onMerge} type="button">
                Merge siblings into this unit
              </button>
            ) : null}
            {unit.parentId ? (
              <button onClick={onSplit} type="button">
                Split unit
              </button>
            ) : null}
            {unit.parentId ? (
              <button onClick={onReparent} type="button">
                Move unit
              </button>
            ) : null}
            <button className="organisation-inspector__danger" onClick={onDeactivate} type="button">
              Deactivate
            </button>
          </div>
        ) : null}
      </header>

      <dl className="organisation-inspector__facts">
        <div>
          <dt>Status</dt>
          <dd>{unit.isActive ? "Active" : "Inactive"}</dd>
        </div>
        <div>
          <dt>Time zone</dt>
          <dd>{unit.timeZone}</dd>
        </div>
        <div>
          <dt>Record version</dt>
          <dd>{unit.version}</dd>
        </div>
        <div>
          <dt>Effective from</dt>
          <dd>{new Date(unit.validFrom).toLocaleDateString("en-GB")}</dd>
        </div>
      </dl>

      <section className="organisation-inspector__authority" aria-labelledby="authority-title">
        <div>
          <KeyRound aria-hidden="true" size={18} />
          <h3 id="authority-title">Management authority</h3>
        </div>
        {grants.isLoading ? <LoadingState label="Loading management grants" /> : null}
        {grants.isError ? <p role="alert">Management grants could not be loaded.</p> : null}
        {grants.data?.length === 0 ? <p>No grants are rooted at this unit.</p> : null}
        {grants.data?.length ? (
          <ul>
            {grants.data.map((grant) => (
              <li key={grant.id}>
                <strong>{formatAction(grant.action)}</strong>
                <span>{grant.includeDescendants ? "Includes descendants" : "This unit only"}</span>
                <small>{grant.revokedAt ? "Revoked" : "Active"}</small>
              </li>
            ))}
          </ul>
        ) : null}
      </section>

      {unit.isActive ? <OrganisationCalendarPanel unit={unit} /> : null}

      <p className="organisation-inspector__routing-note">
        <CalendarClock aria-hidden="true" size={17} />
        Capacity and operational routing remain on the current service until cutover.
      </p>
    </div>
  );
}

function formatCategory(value: string) {
  return value.replaceAll("_", " ");
}

function formatAction(value: string) {
  return value.replace("organisation:", "").replaceAll("_", " ");
}
