import { useState } from "react";

import type { TeamTaskCard } from "../../lib/api-client/team-task-board";
import { WorkPackagePlanningForm } from "./WorkPackagePlanningForm";
import { WorkspaceStoreLinksPanel } from "./WorkspaceStoreLinksPanel";

const columns = [
  ["awaiting_analyst_assignment", "Awaiting assignment"],
  ["ready", "Ready"],
  ["in_progress", "In progress"],
  ["blocked", "Blocked"],
  ["manager_review", "Manager review"],
  ["qc_review", "Quality review"],
  ["rework", "Rework"],
  ["on_hold", "On hold"],
  ["completed_recently", "Completed"],
] as const;

export function TeamTaskBoardView({
  cards,
  planningGrantId,
  unitId,
}: {
  cards: TeamTaskCard[];
  planningGrantId?: string | null;
  unitId: string;
}) {
  return (
    <div className="team-task-board__columns">
      {columns.map(([key, label]) => {
        const items = cards.filter((card) => card.column === key);
        return items.length ? (
          <TaskColumn
            cards={items}
            key={key}
            label={label}
            planningGrantId={planningGrantId}
            unitId={unitId}
          />
        ) : null;
      })}
    </div>
  );
}

export function TeamTaskTableView({ cards }: { cards: TeamTaskCard[] }) {
  return (
    <div className="team-task-board__table" tabIndex={0}>
      <table>
        <caption>Visible team work</caption>
        <thead>
          <tr>
            <th scope="col">Reference</th>
            <th scope="col">Title</th>
            <th scope="col">Team</th>
            <th scope="col">Status</th>
            <th scope="col">Priority</th>
            <th scope="col">Target</th>
          </tr>
        </thead>
        <tbody>
          {cards.map((card) => (
            <tr key={`${card.ticketId}:${card.workflowLeg}`}>
              <th scope="row">{card.reference}</th>
              <td>{card.title}</td>
              <td>{card.unitName ?? "Current team"}</td>
              <td>{columns.find(([value]) => value === card.column)?.[1] ?? card.column}</td>
              <td>{card.priority}</td>
              <td>{card.targetDate ?? "Not set"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function TaskColumn({
  cards,
  label,
  planningGrantId,
  unitId,
}: {
  cards: TeamTaskCard[];
  label: string;
  planningGrantId?: string | null;
  unitId: string;
}) {
  const [planning, setPlanning] = useState<{
    card: TeamTaskCard;
    packageItem: TeamTaskCard["packages"][number];
  } | null>(null);
  const [linking, setLinking] = useState<TeamTaskCard["packages"][number] | null>(null);
  return (
    <section className="team-task-board__column" aria-label={label}>
      <header>
        <h5>{label}</h5>
        <span aria-label={`${cards.length} tasks`}>{cards.length}</span>
      </header>
      <ol>
        {cards.map((card) => (
          <li key={`${card.ticketId}:${card.workflowLeg}`}>
            <small>
              {card.reference}
              {card.unitName ? ` · ${card.unitName}` : ""}
            </small>
            <strong>{card.title}</strong>
            <dl>
              <div>
                <dt>Priority</dt>
                <dd>{card.priority}</dd>
              </div>
              {card.targetDate ? (
                <div>
                  <dt>Target</dt>
                  <dd>{card.targetDate}</dd>
                </div>
              ) : null}
            </dl>
            {card.packages.length ? (
              <ol className="team-task-board__packages" aria-label="Work packages">
                {card.packages.map((packageItem) => (
                  <li key={packageItem.packageId}>
                    <span>
                      <strong>{packageItem.title}</strong>
                      <small>{packageItem.state.replaceAll("_", " ")}</small>
                    </span>
                    {planningGrantId &&
                    packageItem.accountableUserId &&
                    ["pending", "ready", "in_progress"].includes(packageItem.state) ? (
                      <button onClick={() => setPlanning({ card, packageItem })} type="button">
                        Plan work
                      </button>
                    ) : null}
                    <button onClick={() => setLinking(packageItem)} type="button">
                      Store links
                    </button>
                  </li>
                ))}
              </ol>
            ) : null}
            {planning?.card.ticketId === card.ticketId ? (
              <WorkPackagePlanningForm
                card={planning.card}
                onClose={() => setPlanning(null)}
                packageItem={planning.packageItem}
                planningGrantId={planningGrantId!}
                unitId={unitId}
              />
            ) : null}
            {linking && card.packages.some((item) => item.packageId === linking.packageId) ? (
              <WorkspaceStoreLinksPanel
                includeDescendants={false}
                onClose={() => setLinking(null)}
                packageId={linking.packageId}
                packageTitle={linking.title}
                unitId={card.unitId ?? unitId}
              />
            ) : null}
          </li>
        ))}
      </ol>
    </section>
  );
}
