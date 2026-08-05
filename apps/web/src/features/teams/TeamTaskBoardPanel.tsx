import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { ClipboardList, LayoutGrid, List } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { ErrorState, LoadingState } from "../../components/ui/PageState";
import {
  getTeamTaskBoard,
  type TeamBoardColumn,
  type TeamBoardQuery,
} from "../../lib/api-client/team-task-board";
import { TeamCapacitySummary } from "./TeamCapacitySummary";
import { PackageTemplatesPanel } from "./PackageTemplatesPanel";
import { SavedBoardViewsPanel } from "./SavedBoardViewsPanel";
import { TeamTaskBoardView, TeamTaskTableView } from "./TeamTaskBoardViews";
import type { BoardFilters } from "../../lib/api-client/workspace-productivity";

const statusOptions: [TeamBoardColumn, string][] = [
  ["awaiting_analyst_assignment", "Awaiting assignment"],
  ["ready", "Ready"],
  ["in_progress", "In progress"],
  ["blocked", "Blocked"],
  ["manager_review", "Manager review"],
  ["qc_review", "Quality review"],
  ["rework", "Rework"],
  ["on_hold", "On hold"],
  ["completed_recently", "Completed recently"],
];

type Filters = {
  status: TeamBoardColumn | "";
  priority: string;
  dueFrom: string;
  dueTo: string;
  teamId: string;
};

const emptyFilters: Filters = { status: "", priority: "", dueFrom: "", dueTo: "", teamId: "" };

export function TeamTaskBoardPanel({
  unitId,
  planningGrantId,
  configurationGrantId,
  configurationGrantVersion,
  includeDescendants = false,
}: {
  unitId: string;
  planningGrantId?: string | null;
  configurationGrantId?: string | null;
  configurationGrantVersion?: number | null;
  includeDescendants?: boolean;
}) {
  const [includeCompleted, setIncludeCompleted] = useState(false);
  const [filters, setFilters] = useState(emptyFilters);
  const [view, setView] = useState<"board" | "table">("board");
  const [cursors, setCursors] = useState<(string | null)[]>([null]);
  const heading = useRef<HTMLHeadingElement>(null);
  const pageIndex = cursors.length - 1;
  const options: TeamBoardQuery = {
    includeCompleted,
    scope: includeDescendants ? "descendants" : "direct",
    columns: filters.status ? [filters.status] : undefined,
    unitIds: filters.teamId ? [filters.teamId] : undefined,
    priority: filters.priority.trim() || undefined,
    dueFrom: filters.dueFrom || undefined,
    dueTo: filters.dueTo || undefined,
    cursor: cursors[pageIndex],
    limit: 50,
  };
  const query = useQuery({
    queryKey: ["team-task-board", unitId, options],
    queryFn: () => getTeamTaskBoard(unitId, options),
    // Every filter keystroke changes the key, so without the previous page the
    // board would unmount mid-edit and swallow the rest of what was typed.
    placeholderData: keepPreviousData,
    retry: false,
  });
  useEffect(() => {
    if (pageIndex > 0 && !query.isFetching) heading.current?.focus();
  }, [pageIndex, query.isFetching]);
  const teams = useMemo(() => {
    const values = new Map<string, string>();
    query.data?.cards.forEach((card) => {
      if (card.unitId && card.unitName) values.set(card.unitId, card.unitName);
    });
    query.data?.aggregates?.forEach((item) => values.set(item.unitId, item.unitName));
    return [...values.entries()].sort((left, right) => left[1].localeCompare(right[1]));
  }, [query.data]);

  function updateFilters(next: Partial<Filters>) {
    setFilters((current) => ({ ...current, ...next }));
    setCursors([null]);
  }

  const savedFilters: BoardFilters = {
    scope: includeDescendants ? "descendants" : "direct",
    includeCompleted,
    columns: filters.status ? [filters.status] : [],
    unitIds: filters.teamId ? [filters.teamId] : [],
    priority: filters.priority.trim() || null,
    dueFrom: filters.dueFrom || null,
    dueTo: filters.dueTo || null,
  };

  function applySavedFilters(saved: BoardFilters) {
    setIncludeCompleted(saved.includeCompleted);
    setFilters({
      status: saved.columns?.[0] ?? "",
      priority: saved.priority ?? "",
      dueFrom: saved.dueFrom ?? "",
      dueTo: saved.dueTo ?? "",
      teamId: saved.unitIds?.[0] ?? "",
    });
    setCursors([null]);
  }

  if (query.isLoading) return <LoadingState label="Loading team task board" />;
  if (query.isError) {
    return (
      <ErrorState
        message="The team task board could not be loaded."
        onRetry={() => void query.refetch()}
      />
    );
  }
  const result = query.data!;
  const aggregates = result.aggregates ?? [];
  return (
    <section className="team-task-board" aria-labelledby="team-task-board-title">
      {planningGrantId ? <TeamCapacitySummary grantId={planningGrantId} unitId={unitId} /> : null}
      <header>
        <div>
          <ClipboardList aria-hidden="true" size={18} />
          <h4 id="team-task-board-title" ref={heading} tabIndex={-1}>
            {includeDescendants ? "Management task board" : "Team task board"}
          </h4>
        </div>
        <label>
          <input
            checked={includeCompleted}
            onChange={(event) => {
              setIncludeCompleted(event.target.checked);
              setCursors([null]);
            }}
            type="checkbox"
          />{" "}
          Show completed from the last 30 days
        </label>
      </header>
      <div className="team-task-board__filters" aria-label="Board filters">
        <label>
          Status
          <select
            value={filters.status}
            onChange={(event) => updateFilters({ status: event.target.value as Filters["status"] })}
          >
            <option value="">All statuses</option>
            {statusOptions.map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        {includeDescendants && teams.length ? (
          <label>
            Team
            <select
              value={filters.teamId}
              onChange={(event) => updateFilters({ teamId: event.target.value })}
            >
              <option value="">All authorised teams</option>
              {teams.map(([id, name]) => (
                <option key={id} value={id}>
                  {name}
                </option>
              ))}
            </select>
          </label>
        ) : null}
        <label>
          Priority
          <input
            maxLength={40}
            value={filters.priority}
            onChange={(event) => updateFilters({ priority: event.target.value })}
          />
        </label>
        <label>
          Due from
          <input
            type="date"
            value={filters.dueFrom}
            onChange={(event) => updateFilters({ dueFrom: event.target.value })}
          />
        </label>
        <label>
          Due to
          <input
            type="date"
            value={filters.dueTo}
            onChange={(event) => updateFilters({ dueTo: event.target.value })}
          />
        </label>
        <button onClick={() => updateFilters(emptyFilters)} type="button">
          Clear filters
        </button>
        <div aria-label="Board result view" role="group">
          <button aria-pressed={view === "board"} onClick={() => setView("board")} type="button">
            <LayoutGrid aria-hidden="true" size={15} /> Board
          </button>
          <button aria-pressed={view === "table"} onClick={() => setView("table")} type="button">
            <List aria-hidden="true" size={15} /> Table
          </button>
        </div>
      </div>
      <div className="workspace-productivity-grid">
        <SavedBoardViewsPanel filters={savedFilters} onApply={applySavedFilters} unitId={unitId} />
        <PackageTemplatesPanel
          grant={
            configurationGrantId && configurationGrantVersion
              ? { id: configurationGrantId, version: configurationGrantVersion }
              : undefined
          }
          unitId={unitId}
        />
      </div>
      {result.cards.length === 0 && aggregates.length === 0 ? (
        <p className="team-task-board__empty">No assigned delivery work matches these filters.</p>
      ) : null}
      {view === "board" ? (
        <TeamTaskBoardView cards={result.cards} planningGrantId={planningGrantId} unitId={unitId} />
      ) : (
        <TeamTaskTableView cards={result.cards} />
      )}
      {aggregates.length ? (
        <section className="team-task-board__aggregates" aria-labelledby="restricted-work-title">
          <h5 id="restricted-work-title">Restricted child-team work</h5>
          <p>
            Only aggregate counts are available. Ticket details and hidden facets are not disclosed.
            Priority text does not narrow these counts.
          </p>
          <ul>
            {aggregates.map((item) => (
              <li key={`${item.unitId}:${item.column}`}>
                <strong>{item.unitName}</strong>
                <span>
                  {statusOptions.find(([value]) => value === item.column)?.[1] ?? item.column}:{" "}
                  {item.suppressed ? "Fewer than 5" : item.count}
                </span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
      <nav aria-label="Task board pages" className="team-task-board__paging">
        <button
          disabled={pageIndex === 0 || query.isFetching}
          onClick={() => setCursors((items) => items.slice(0, -1))}
          type="button"
        >
          Previous page
        </button>
        <span aria-live="polite">Page {pageIndex + 1}</span>
        <button
          disabled={!result.nextCursor || query.isFetching}
          onClick={() => setCursors((items) => [...items, result.nextCursor])}
          type="button"
        >
          Next page
        </button>
      </nav>
    </section>
  );
}
