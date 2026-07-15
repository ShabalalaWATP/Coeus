import { useQuery } from "@tanstack/react-query";
import { History, RotateCcw } from "lucide-react";
import { useState } from "react";

import { getAnalystTaskConversation } from "../../lib/api-client/analyst";

export function AnalystConversation({ ticketId }: { ticketId: string }) {
  const [open, setOpen] = useState(false);
  const conversationQuery = useQuery({
    enabled: open,
    queryFn: () => getAnalystTaskConversation(ticketId),
    queryKey: ["analyst", "conversation", ticketId],
    retry: false,
  });

  return (
    <details
      className="analyst-conversation"
      onToggle={(event) => setOpen(event.currentTarget.open)}
    >
      <summary>
        <span>
          <History aria-hidden="true" size={17} />
          Request conversation
        </span>
        <small>Full customer and Istari history</small>
      </summary>
      <div className="analyst-conversation__body">
        {conversationQuery.isLoading ? <p role="status">Loading conversation…</p> : null}
        {conversationQuery.isError ? (
          <div className="analyst-conversation__error" role="alert">
            <span>The request conversation could not be loaded.</span>
            <button onClick={() => void conversationQuery.refetch()} type="button">
              <RotateCcw aria-hidden="true" size={15} />
              Retry
            </button>
          </div>
        ) : null}
        {conversationQuery.data?.messages.length === 0 ? (
          <p>No customer conversation was recorded for this request.</p>
        ) : null}
        {conversationQuery.data?.messages.length ? (
          <ol className="analyst-conversation__messages">
            {conversationQuery.data.messages.map((message) => (
              <li
                className={`analyst-conversation__message analyst-conversation__message--${message.author}`}
                key={message.id}
              >
                <header>
                  <strong>{message.author === "user" ? "Requester" : "Istari"}</strong>
                  <time dateTime={message.createdAt}>{formatTime(message.createdAt)}</time>
                </header>
                <p>{message.body}</p>
              </li>
            ))}
          </ol>
        ) : null}
      </div>
    </details>
  );
}

function formatTime(value: string) {
  return new Intl.DateTimeFormat("en-GB", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}
