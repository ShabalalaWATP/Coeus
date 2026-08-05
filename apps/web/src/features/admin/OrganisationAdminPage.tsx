import { Network } from "lucide-react";
import { useState } from "react";

import { OrganisationTree } from "./OrganisationTree";
import { OrganisationBootstrapPanel } from "./OrganisationBootstrapPanel";
import { OrganisationAuthorityPanel } from "./OrganisationAuthorityPanel";
import { OrganisationCutoverReadinessPanel } from "./OrganisationCutoverReadinessPanel";
import { OrganisationCutoverReleasePanel } from "./OrganisationCutoverReleasePanel";
import { OrganisationMutationPanel } from "./OrganisationMutationPanel";
import { OrganisationMergePanel } from "./OrganisationMergePanel";
import { OrganisationRosterPanel } from "./OrganisationRosterPanel";
import { OrganisationSplitPanel } from "./OrganisationSplitPanel";
import { OrganisationStructurePanel } from "./OrganisationStructurePanel";
import { OrganisationSyntheticFixturePanel } from "./OrganisationSyntheticFixturePanel";
import { OrganisationUnitInspector } from "./OrganisationUnitInspector";
import { AdminReturnLink } from "../../components/ui/AdminReturnLink";
import type { OrganisationUnit } from "../../lib/api-client/organisation-admin";

export default function OrganisationAdminPage() {
  const [selected, setSelected] = useState<OrganisationUnit>();
  const [target, setTarget] = useState<OrganisationUnit>();
  const [mutationMode, setMutationMode] = useState<
    | "authority"
    | "bootstrap"
    | "create"
    | "deactivate"
    | "edit"
    | "fixture"
    | "merge"
    | "reparent"
    | "roster"
    | "select-parent"
    | "split"
  >();

  return (
    <main className="organisation-admin-page">
      <header className="organisation-admin-page__header">
        <div>
          <AdminReturnLink />
          <span className="eyebrow">Management workspace</span>
          <h1>Organisation</h1>
          <p>Explore units, reporting lines and explicitly delegated management authority.</p>
        </div>
        <div className="organisation-admin-page__mode">
          <Network aria-hidden="true" size={19} />
          <span>
            <strong>
              {mutationMode === "select-parent" ? "Select a new parent" : "Management mode"}
            </strong>
            <small>
              {mutationMode === "select-parent"
                ? `Choose the new parent for ${selected?.shortName}`
                : "Operational routing is unchanged"}
            </small>
          </span>
        </div>
      </header>

      <OrganisationCutoverReadinessPanel />
      <OrganisationCutoverReleasePanel />

      <div className="organisation-admin-page__workspace">
        <section className="organisation-admin-page__tree" aria-labelledby="tree-title">
          <header>
            <div>
              <h2 id="tree-title">Hierarchy</h2>
              <p>Expand a unit to reveal its direct children.</p>
            </div>
            <button onClick={() => setMutationMode("fixture")} type="button">
              Exercise data
            </button>
          </header>
          <OrganisationTree
            onBootstrap={() => setMutationMode("bootstrap")}
            onSelect={(unit) => {
              if (mutationMode === "select-parent" && selected && unit.id !== selected.id) {
                setTarget(unit);
                setMutationMode("reparent");
                return;
              }
              setSelected(unit);
              setTarget(undefined);
              setMutationMode(undefined);
            }}
            selectedId={selected?.id}
          />
        </section>
        <aside className="organisation-admin-page__inspector" aria-label="Selected unit details">
          {mutationMode === "bootstrap" ? (
            <OrganisationBootstrapPanel onClose={() => setMutationMode(undefined)} />
          ) : mutationMode === "fixture" ? (
            <OrganisationSyntheticFixturePanel onClose={() => setMutationMode(undefined)} />
          ) : mutationMode === "authority" && selected ? (
            <OrganisationAuthorityPanel
              onClose={() => setMutationMode(undefined)}
              unit={selected}
            />
          ) : mutationMode === "roster" && selected ? (
            <OrganisationRosterPanel onClose={() => setMutationMode(undefined)} unit={selected} />
          ) : mutationMode === "merge" && selected ? (
            <OrganisationMergePanel
              onClose={() => setMutationMode(undefined)}
              successor={selected}
            />
          ) : mutationMode === "split" && selected ? (
            <OrganisationSplitPanel onClose={() => setMutationMode(undefined)} source={selected} />
          ) : (mutationMode === "reparent" || mutationMode === "deactivate") && selected ? (
            <OrganisationStructurePanel
              mode={mutationMode}
              onClose={() => {
                setMutationMode(undefined);
                setTarget(undefined);
              }}
              target={target}
              unit={selected}
            />
          ) : (mutationMode === "create" || mutationMode === "edit") && selected ? (
            <OrganisationMutationPanel
              mode={mutationMode}
              onClose={() => setMutationMode(undefined)}
              parent={mutationMode === "create" ? selected : undefined}
              unit={mutationMode === "edit" ? selected : undefined}
            />
          ) : (
            <OrganisationUnitInspector
              onCreate={() => setMutationMode("create")}
              onDeactivate={() => setMutationMode("deactivate")}
              onEdit={() => setMutationMode("edit")}
              onManageAuthority={() => setMutationMode("authority")}
              onManageRoster={() => setMutationMode("roster")}
              onMerge={() => setMutationMode("merge")}
              onReparent={() => setMutationMode("select-parent")}
              onSplit={() => setMutationMode("split")}
              unit={selected}
            />
          )}
        </aside>
      </div>
    </main>
  );
}
