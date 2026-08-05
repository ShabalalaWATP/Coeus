import { useQuery } from "@tanstack/react-query";
import { BriefcaseBusiness } from "lucide-react";
import { Link } from "react-router-dom";

import { listMyWork, type MyWorkCard } from "../../lib/api-client/my-work";

const columnLabels: Record<MyWorkCard["column"], string> = {
  ready: "Ready",
  in_progress: "In progress",
  blocked: "Blocked",
  review: "In review",
  rework: "Rework",
  on_hold: "On hold",
  completed: "Completed",
};

function timing(card: MyWorkCard) {
  const value = card.reviewAt ?? card.dueAt ?? card.targetDate;
  if (!value) return "No target date";
  const parsed = new Date(value.length === 10 ? `${value}T12:00:00Z` : value);
  if (Number.isNaN(parsed.valueOf())) return "Target date unavailable";
  return new Intl.DateTimeFormat("en-GB", { dateStyle: "medium" }).format(parsed);
}

export function MyWorkSnapshot() {
  const work = useQuery({
    queryKey: ["my-work", "profile-snapshot"],
    queryFn: () => listMyWork(5),
    retry: false,
  });
  const cards = work.data?.cards ?? [];

  return (
    <section className="profile-panel my-work" aria-labelledby="my-work-title">
      <div className="profile-panel__heading">
        <h3 id="my-work-title">
          <BriefcaseBusiness aria-hidden="true" size={15} /> My work
        </h3>
        <Link className="profile-panel__link" to="/analyst/my-work">
          View all my work
        </Link>
      </div>
      {work.isLoading ? <p className="profile-muted">Loading your current work…</p> : null}
      {work.isError ? (
        <div className="my-work__failure" role="alert">
          <p className="profile-muted">Your current work is temporarily unavailable.</p>
          <button
            type="button"
            className="button button--secondary"
            onClick={() => void work.refetch()}
          >
            Try again
          </button>
        </div>
      ) : null}
      {!work.isLoading && !work.isError && cards.length === 0 ? (
        <p className="profile-muted">You have no active work packages.</p>
      ) : null}
      {cards.length > 0 ? (
        <ol className="my-work__cards">
          {cards.map((card) => (
            <li key={card.packageId}>
              <Link to={`/analyst/tasks/${encodeURIComponent(card.ticketId)}`}>
                <span>
                  <strong>{card.packageTitle}</strong>
                  <small>
                    {card.reference} · {card.ticketTitle}
                  </small>
                </span>
                <span className="my-work__status">
                  {columnLabels[card.column]}
                  <small>{timing(card)}</small>
                </span>
              </Link>
            </li>
          ))}
        </ol>
      ) : null}
    </section>
  );
}
