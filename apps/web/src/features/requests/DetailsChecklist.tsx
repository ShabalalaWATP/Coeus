import { CircleCheck, CircleDashed, ListChecks } from "lucide-react";

import type { Ticket } from "../../lib/api-client/tickets";

type DetailsChecklistProps = {
  ticket: Ticket;
};

export function DetailsChecklist({ ticket }: DetailsChecklistProps) {
  const items = ticket.intakeChecklist;
  const captured = items.filter((item) => item.satisfied);

  return (
    <section className="surface details-checklist" aria-labelledby="checklist-title">
      <div className="section-heading access-heading">
        <ListChecks aria-hidden="true" size={20} />
        <div>
          <h2 id="checklist-title">Request details</h2>
          <p>
            {captured.length} of {items.length} captured from the conversation.
          </p>
        </div>
      </div>
      <ul className="details-checklist__items">
        {items.map((item) => (
          <li
            className={item.satisfied ? "details-item details-item--done" : "details-item"}
            key={item.key}
          >
            {item.satisfied ? (
              <CircleCheck aria-hidden="true" size={17} />
            ) : (
              <CircleDashed aria-hidden="true" size={17} />
            )}
            <div>
              <strong>{item.label}</strong>
              <span>{item.value ?? "Answer in the chat to capture this."}</span>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
