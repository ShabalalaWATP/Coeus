import { Clock3, Plus } from "lucide-react";
import { useState } from "react";

import type { Ticket } from "../../lib/api-client/tickets";

type TimelinePanelProps = {
  isAdding: boolean;
  onAddInformation: (body: string) => void;
  readOnly?: boolean;
  ticket?: Ticket;
};

export function TimelinePanel({
  isAdding,
  onAddInformation,
  readOnly = false,
  ticket,
}: TimelinePanelProps) {
  const [body, setBody] = useState("");
  const trimmedBody = body.trim();
  const bodyTooShort = trimmedBody.length > 0 && trimmedBody.length < 3;

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (trimmedBody.length < 3) {
      return;
    }
    onAddInformation(trimmedBody);
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
      {ticket !== undefined && readOnly ? (
        <p className="chat-readonly">The timeline is read-only for this request.</p>
      ) : null}
      {ticket !== undefined && !readOnly ? (
        <form className="timeline-form" onSubmit={handleSubmit}>
          <label htmlFor="timeline-note">Additional information</label>
          <textarea
            id="timeline-note"
            onChange={(event) => setBody(event.target.value)}
            rows={3}
            value={body}
          />
          {bodyTooShort ? (
            <small className="field-hint">Entries need at least 3 characters.</small>
          ) : null}
          <button disabled={isAdding || trimmedBody.length < 3} type="submit">
            <Plus aria-hidden="true" size={18} />
            Add information
          </button>
        </form>
      ) : null}
    </section>
  );
}
