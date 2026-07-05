import { Clock3, Plus } from "lucide-react";
import { useState } from "react";

import type { Ticket } from "../../lib/api-client/tickets";

type TimelinePanelProps = {
  isAdding: boolean;
  onAddInformation: (body: string) => void;
  ticket?: Ticket;
};

export function TimelinePanel({ isAdding, onAddInformation, ticket }: TimelinePanelProps) {
  const [body, setBody] = useState("");

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = body.trim();
    if (trimmed.length < 3) {
      return;
    }
    onAddInformation(trimmed);
    setBody("");
  }

  return (
    <section className="surface timeline-panel" aria-labelledby="timeline-title">
      <div className="section-heading access-heading">
        <Clock3 aria-hidden="true" size={20} />
        <h2 id="timeline-title">Timeline</h2>
      </div>
      <div className="stack-list">
        {ticket?.timeline.length ? (
          ticket.timeline.map((entry) => (
            <div className="stack-row" key={entry.id}>
              <strong>{entry.eventType.replaceAll("_", " ")}</strong>
              <span>{entry.body}</span>
            </div>
          ))
        ) : (
          <p>No timeline events</p>
        )}
      </div>
      {ticket !== undefined ? (
        <form className="timeline-form" onSubmit={handleSubmit}>
          <label htmlFor="timeline-note">Additional information</label>
          <textarea
            id="timeline-note"
            onChange={(event) => setBody(event.target.value)}
            rows={3}
            value={body}
          />
          <button disabled={isAdding} type="submit">
            <Plus aria-hidden="true" size={18} />
            Add information
          </button>
        </form>
      ) : null}
    </section>
  );
}
