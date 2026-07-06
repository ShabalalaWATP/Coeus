import { CircleCheck, CircleDashed, ListChecks } from "lucide-react";

import type { Ticket } from "../../lib/api-client/tickets";

const requiredDetails = [
  ["title", "Title"],
  ["description", "What you need"],
  ["operationalQuestion", "Operational question"],
  ["areaOrRegion", "Area or region"],
  ["priority", "Priority"],
  ["requiredOutputFormat", "Output format"],
  ["customerSuccessCriteria", "Success criteria"],
] as const;

type DetailsChecklistProps = {
  ticket: Ticket;
};

export function DetailsChecklist({ ticket }: DetailsChecklistProps) {
  const captured = requiredDetails.filter(([key]) => hasValue(ticket, key));

  return (
    <section className="surface details-checklist" aria-labelledby="checklist-title">
      <div className="section-heading access-heading">
        <ListChecks aria-hidden="true" size={20} />
        <div>
          <h2 id="checklist-title">Details the assistant needs</h2>
          <p>
            {captured.length} of {requiredDetails.length} captured from the conversation.
          </p>
        </div>
      </div>
      <ul className="details-checklist__items">
        {requiredDetails.map(([key, label]) => {
          const value = valueFor(ticket, key);
          const done = value !== null;
          return (
            <li className={done ? "details-item details-item--done" : "details-item"} key={key}>
              {done ? (
                <CircleCheck aria-hidden="true" size={17} />
              ) : (
                <CircleDashed aria-hidden="true" size={17} />
              )}
              <div>
                <strong>{label}</strong>
                <span>{value ?? "Answer in the chat to capture this."}</span>
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function hasValue(ticket: Ticket, key: (typeof requiredDetails)[number][0]) {
  return valueFor(ticket, key) !== null;
}

function valueFor(ticket: Ticket, key: (typeof requiredDetails)[number][0]) {
  const value = ticket.intake[key];
  if (value === null || value.trim() === "") {
    return null;
  }
  return value;
}
