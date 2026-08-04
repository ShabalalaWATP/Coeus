import { useQuery } from "@tanstack/react-query";
import { Building2, Network, UsersRound } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { OrganisationCalendarPanel } from "../admin/OrganisationCalendarPanel";
import { WorkUpdatesPanel } from "../profile/WorkUpdatesPanel";
import { TeamTaskBoardPanel } from "./TeamTaskBoardPanel";
import { WorkspaceCapabilitiesPanel } from "./WorkspaceCapabilitiesPanel";
import { WorkspaceOverviewPanel } from "./WorkspaceOverviewPanel";
import { WorkspacePeoplePanel } from "./WorkspacePeoplePanel";
import { WorkspaceSearchPanel } from "./WorkspaceSearchPanel";
import { WorkspaceSettingsPanel } from "./WorkspaceSettingsPanel";
import { ErrorState, LoadingState } from "../../components/ui/PageState";
import {
  listOrganisationWorkspaces,
  type OrganisationWorkspace,
} from "../../lib/api-client/organisation-workspaces";
import { useAuth } from "../../lib/auth/auth-context";

export function OrganisationWorkspacePanel() {
  const query = useQuery({
    queryKey: ["organisation-workspaces"],
    queryFn: listOrganisationWorkspaces,
    retry: false,
  });
  if (query.isLoading) return <LoadingState label="Loading your organisation workspace" />;
  if (query.isError) {
    return (
      <ErrorState
        message="Your organisation workspace could not be loaded."
        onRetry={() => void query.refetch()}
      />
    );
  }
  const workspaces = query.data?.workspaces ?? [];
  if (workspaces.length === 0) return null;
  return (
    <LoadedWorkspacePanel truncated={query.data?.truncated ?? false} workspaces={workspaces} />
  );
}

function LoadedWorkspacePanel({
  truncated,
  workspaces,
}: {
  truncated: boolean;
  workspaces: OrganisationWorkspace[];
}) {
  const { session } = useAuth();
  const [selectedId, setSelectedId] = useState<string>();
  const [view, setView] = useState<WorkspaceTab>("overview");
  const tabRefs = useRef<Array<HTMLButtonElement | null>>([]);
  const selected = workspaces.find((item) => item.unit.id === selectedId) ?? workspaces[0];
  const home = workspaces.filter((item) => item.relationship === "home");
  const managed = workspaces.filter((item) => item.relationship === "managed");
  const tabs = workspaceTabs(selected);
  // Which tabs exist depends on the selected workspace, so a tab that is no
  // longer offered must not stay selected. The identity list is the dependency
  // rather than the array, which is rebuilt on every render.
  const tabIds = tabs.map((tab) => tab.id).join(":");
  useEffect(() => {
    // "".split(":") is [""], not [], so an empty tab list must be handled first.
    const available = tabIds === "" ? [] : (tabIds.split(":") as WorkspaceTab[]);
    if (!available.includes(view)) setView(available[0] ?? "overview");
  }, [tabIds, view]);

  const selectTab = (index: number) => {
    const tab = tabs[index];
    if (!tab) return;
    setView(tab.id);
    tabRefs.current[index]?.focus();
  };

  return (
    <section className="team-workspaces" aria-labelledby="organisation-workspaces-title">
      <header className="team-workspaces__heading">
        <div>
          <Building2 aria-hidden="true" size={19} />
          <h2 id="organisation-workspaces-title">Organisation workspace</h2>
        </div>
        <p>Your current posting and teams you have been explicitly authorised to manage.</p>
      </header>
      <div className="team-workspaces__layout">
        <nav aria-label="Organisation workspaces" className="team-workspaces__switcher">
          <WorkspaceGroup
            icon={<UsersRound aria-hidden="true" size={16} />}
            label="My team"
            onSelect={setSelectedId}
            selectedId={selected.unit.id}
            workspaces={home}
          />
          <WorkspaceGroup
            icon={<Network aria-hidden="true" size={16} />}
            label="Managed teams"
            onSelect={setSelectedId}
            selectedId={selected.unit.id}
            workspaces={managed}
          />
        </nav>
        <div className="team-workspaces__content">
          <header>
            <p>{selected.relationship === "home" ? "Current home team" : "Managed scope"}</p>
            <h3>{selected.unit.name}</h3>
            <div className="team-workspaces__badges">
              {selected.relationship === "home" ? <span>My team</span> : null}
              {selected.managed ? <span>Managed</span> : null}
              {selected.includeDescendants ? <span>Includes child teams</span> : null}
            </div>
          </header>
          {selected.managed ? (
            <WorkspaceSearchPanel
              includeDescendants={selected.includeDescendants}
              unitId={selected.unit.id}
            />
          ) : null}
          {tabs.length > 1 ? (
            <div className="team-workspaces__tabs" role="tablist" aria-label="Team workspace view">
              {tabs.map((tab, index) => (
                <button
                  aria-controls={"team-workspace-panel-" + tab.id}
                  aria-selected={view === tab.id}
                  id={"team-workspace-tab-" + tab.id}
                  key={tab.id}
                  onClick={() => setView(tab.id)}
                  onKeyDown={(event) => {
                    const current = tabs.findIndex((item) => item.id === view);
                    if (event.key === "ArrowRight" || event.key === "ArrowLeft") {
                      event.preventDefault();
                      const direction = event.key === "ArrowRight" ? 1 : -1;
                      selectTab((current + direction + tabs.length) % tabs.length);
                    } else if (event.key === "Home" || event.key === "End") {
                      event.preventDefault();
                      selectTab(event.key === "Home" ? 0 : tabs.length - 1);
                    }
                  }}
                  ref={(node) => {
                    tabRefs.current[index] = node;
                  }}
                  role="tab"
                  tabIndex={view === tab.id ? 0 : -1}
                  type="button"
                >
                  {tab.label}
                </button>
              ))}
            </div>
          ) : null}
          {tabs.length ? (
            <div
              aria-labelledby={"team-workspace-tab-" + view}
              id={"team-workspace-panel-" + view}
              role="tabpanel"
            >
              <WorkspaceView
                csrfToken={session?.csrfToken ?? ""}
                currentUserId={session?.user.id ?? ""}
                selected={selected}
                view={view}
              />
            </div>
          ) : (
            <p className="team-workspaces__limited">
              Workspace views are not included in your authority for this team.
            </p>
          )}
        </div>
      </div>
      {truncated ? (
        <p className="team-workspaces__notice">
          Only the first 100 authorised workspaces are shown. Refine the organisation scope with an
          administrator.
        </p>
      ) : null}
      {session ? <WorkUpdatesPanel csrfToken={session.csrfToken} /> : null}
    </section>
  );
}

type WorkspaceTab = "overview" | "board" | "calendar" | "people" | "capabilities" | "settings";

function workspaceTabs(workspace: OrganisationWorkspace): { id: WorkspaceTab; label: string }[] {
  return [
    workspace.managed && { id: "overview" as const, label: "Overview" },
    workspace.canViewTasks && { id: "board" as const, label: "Board" },
    workspace.canViewAvailability && { id: "calendar" as const, label: "Calendar" },
    workspace.canViewPeople && { id: "people" as const, label: "People" },
    workspace.canViewCapabilities && { id: "capabilities" as const, label: "Capabilities" },
    workspace.canConfigure && { id: "settings" as const, label: "Settings" },
  ].filter((item): item is { id: WorkspaceTab; label: string } => Boolean(item));
}

function WorkspaceView({
  csrfToken,
  currentUserId,
  selected,
  view,
}: {
  csrfToken: string;
  currentUserId: string;
  selected: OrganisationWorkspace;
  view: WorkspaceTab;
}) {
  if (view === "overview") {
    return (
      <WorkspaceOverviewPanel
        csrfToken={csrfToken}
        exportGrant={
          selected.exportGrantId && selected.exportGrantVersion
            ? { id: selected.exportGrantId, version: selected.exportGrantVersion }
            : undefined
        }
        includeDescendants={selected.includeDescendants}
        unitId={selected.unit.id}
      />
    );
  }
  if (view === "board") {
    return (
      <TeamTaskBoardPanel
        configurationGrantId={selected.configurationGrantId}
        configurationGrantVersion={selected.configurationGrantVersion}
        includeDescendants={selected.includeDescendants}
        planningGrantId={selected.planningGrantId}
        unitId={selected.unit.id}
      />
    );
  }
  if (view === "calendar") {
    return (
      <OrganisationCalendarPanel
        allowDescendants={selected.includeDescendants}
        allowDetail={selected.canViewDetail}
        csrfToken={csrfToken}
        currentUserId={currentUserId}
        managementGrantId={selected.calendarManagementGrantId}
        unit={selected.unit}
      />
    );
  }
  if (view === "people") {
    return (
      <WorkspacePeoplePanel
        includeDescendants={selected.includeDescendants}
        unitId={selected.unit.id}
      />
    );
  }
  if (view === "capabilities") {
    return (
      <WorkspaceCapabilitiesPanel
        includeDescendants={selected.includeDescendants}
        unitId={selected.unit.id}
      />
    );
  }
  return (
    <WorkspaceSettingsPanel
      configurationGrant={{
        id: selected.configurationGrantId!,
        version: selected.configurationGrantVersion!,
      }}
      csrfToken={csrfToken}
      unitId={selected.unit.id}
    />
  );
}

function WorkspaceGroup({
  icon,
  label,
  onSelect,
  selectedId,
  workspaces,
}: {
  icon: React.ReactNode;
  label: string;
  onSelect: (id: string) => void;
  selectedId: string;
  workspaces: OrganisationWorkspace[];
}) {
  if (workspaces.length === 0) return null;
  return (
    <div>
      <p>
        {icon}
        {label}
      </p>
      {workspaces.map((workspace) => (
        <button
          aria-pressed={workspace.unit.id === selectedId}
          key={workspace.unit.id}
          onClick={() => onSelect(workspace.unit.id)}
          type="button"
        >
          <span>{workspace.unit.name}</span>
          <small>{workspace.unit.shortName}</small>
        </button>
      ))}
    </div>
  );
}
