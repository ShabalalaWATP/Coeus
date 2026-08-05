import { useQuery } from "@tanstack/react-query";
import { BriefcaseBusiness, LayoutGrid, List } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { ErrorState, LoadingState } from "../../components/ui/PageState";
import { listMyWork, type MyWorkCard, type MyWorkColumn } from "../../lib/api-client/my-work";

const labels: Record<MyWorkColumn, string> = {
  ready: "Ready",
  in_progress: "In progress",
  blocked: "Blocked",
  review: "In review",
  rework: "Rework",
  on_hold: "On hold",
  completed: "Completed",
};

export default function MyWorkPage() {
  const [column, setColumn] = useState<MyWorkColumn | "">("");
  const [includeCompleted, setIncludeCompleted] = useState(false);
  const [view, setView] = useState<"cards" | "table">("cards");
  const [cursorStack, setCursorStack] = useState<(string | null)[]>([null]);
  const pageIndex = cursorStack.length - 1;
  const cursor = cursorStack[pageIndex];
  const pageHeading = useRef<HTMLHeadingElement>(null);
  const query = useQuery({
    queryKey: ["my-work", "page", column, includeCompleted, cursor],
    queryFn: () => listMyWork({ column, includeCompleted, cursor, limit: 25 }),
    retry: false,
  });

  useEffect(() => {
    if (!query.isFetching && pageIndex > 0) pageHeading.current?.focus();
  }, [pageIndex, query.isFetching]);

  function resetFilters(nextColumn: MyWorkColumn | "", completed: boolean) {
    setColumn(nextColumn);
    setIncludeCompleted(completed);
    setCursorStack([null]);
  }

  return (
    <div className="my-work-page">
      <header className="overview-hero">
        <div>
          <h1 ref={pageHeading} tabIndex={-1}>
            <BriefcaseBusiness aria-hidden="true" /> My work
          </h1>
          <p>Your canonical work packages, derived from current workflow ownership.</p>
        </div>
      </header>
      <section className="surface my-work-page__controls" aria-label="Work filters and view">
        <label>
          Status
          <select
            value={column}
            onChange={(event) => {
              const next = event.target.value as MyWorkColumn | "";
              resetFilters(next, next === "completed" || includeCompleted);
            }}
          >
            <option value="">All active statuses</option>
            {Object.entries(labels).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label className="my-work-page__check">
          <input
            checked={includeCompleted}
            onChange={(event) =>
              resetFilters(
                !event.target.checked && column === "completed" ? "" : column,
                event.target.checked,
              )
            }
            type="checkbox"
          />
          Include work completed in the last 30 days
        </label>
        <div aria-label="Result view" className="my-work-page__view" role="group">
          <button aria-pressed={view === "cards"} onClick={() => setView("cards")} type="button">
            <LayoutGrid aria-hidden="true" size={16} /> Cards
          </button>
          <button aria-pressed={view === "table"} onClick={() => setView("table")} type="button">
            <List aria-hidden="true" size={16} /> Table
          </button>
        </div>
      </section>
      {query.isLoading ? <LoadingState label="Loading your work" /> : null}
      {query.isError ? (
        <ErrorState
          message="Your work is temporarily unavailable."
          onRetry={() => void query.refetch()}
        />
      ) : null}
      {query.data && query.data.cards.length === 0 ? (
        <p className="surface my-work-page__empty">No work matches these filters.</p>
      ) : null}
      {query.data?.cards.length ? (
        view === "cards" ? (
          <WorkCards cards={query.data.cards} />
        ) : (
          <WorkTable cards={query.data.cards} />
        )
      ) : null}
      {query.data ? (
        <nav aria-label="My work pages" className="my-work-page__paging">
          <button
            disabled={pageIndex === 0 || query.isFetching}
            onClick={() => setCursorStack((current) => current.slice(0, -1))}
            type="button"
          >
            Previous page
          </button>
          <span aria-live="polite">Page {pageIndex + 1}</span>
          <button
            disabled={!query.data.nextCursor || query.isFetching}
            onClick={() => setCursorStack((current) => [...current, query.data.nextCursor])}
            type="button"
          >
            Next page
          </button>
        </nav>
      ) : null}
    </div>
  );
}

function WorkCards({ cards }: { cards: MyWorkCard[] }) {
  return (
    <ol className="my-work-page__cards" aria-label="My work results">
      {cards.map((card) => (
        <li className="surface" key={card.packageId}>
          <small>{card.reference}</small>
          <h2>{card.packageTitle}</h2>
          <p>{card.ticketTitle}</p>
          <dl>
            <div>
              <dt>Status</dt>
              <dd>{labels[card.column]}</dd>
            </div>
            <div>
              <dt>Due</dt>
              <dd>{formatDate(card.dueAt ?? card.targetDate)}</dd>
            </div>
          </dl>
          <Link to={`/analyst/tasks/${encodeURIComponent(card.ticketId)}`}>Open task</Link>
        </li>
      ))}
    </ol>
  );
}

function WorkTable({ cards }: { cards: MyWorkCard[] }) {
  return (
    <div className="surface my-work-page__table" tabIndex={0}>
      <table>
        <caption>My work results</caption>
        <thead>
          <tr>
            <th scope="col">Reference</th>
            <th scope="col">Package</th>
            <th scope="col">Status</th>
            <th scope="col">Due</th>
            <th scope="col">Action</th>
          </tr>
        </thead>
        <tbody>
          {cards.map((card) => (
            <tr key={card.packageId}>
              <th scope="row">{card.reference}</th>
              <td>{card.packageTitle}</td>
              <td>{labels[card.column]}</td>
              <td>{formatDate(card.dueAt ?? card.targetDate)}</td>
              <td>
                <Link to={`/analyst/tasks/${encodeURIComponent(card.ticketId)}`}>Open task</Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function formatDate(value: string | null) {
  if (!value) return "Not set";
  const parsed = new Date(value.length === 10 ? `${value}T12:00:00Z` : value);
  return Number.isNaN(parsed.valueOf())
    ? "Unavailable"
    : new Intl.DateTimeFormat("en-GB", { dateStyle: "medium" }).format(parsed);
}
