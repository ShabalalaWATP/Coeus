import { Bot, SendHorizonal } from "lucide-react";
import { useState } from "react";

import type { Ticket } from "../../lib/api-client/tickets";

type ChatPanelProps = {
  isSending: boolean;
  onSend: (message: string) => void;
  readOnly?: boolean;
  ticket?: Ticket;
};

export function ChatPanel({ isSending, onSend, readOnly = false, ticket }: ChatPanelProps) {
  const [message, setMessage] = useState("");

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = message.trim();
    if (trimmed.length < 3) {
      return;
    }
    onSend(trimmed);
    setMessage("");
  }

  return (
    <section className="surface chat-panel" aria-labelledby="chat-title">
      <div className="section-heading access-heading">
        <Bot aria-hidden="true" size={20} />
        <h2 id="chat-title">Intake assistant</h2>
      </div>
      <div className="chat-transcript" aria-live="polite">
        {ticket?.messages.length ? (
          ticket.messages.map((item) => (
            <article className={`chat-message chat-message--${item.author}`} key={item.id}>
              <strong>{item.author === "user" ? "You" : "Istari"}</strong>
              <p>{item.body}</p>
            </article>
          ))
        ) : (
          <p>No chat transcript</p>
        )}
        {isSending ? (
          <p className="chat-typing" role="status">
            <Bot aria-hidden="true" size={15} />
            Istari is thinking
            <span aria-hidden="true" className="chat-typing__dots">
              <i />
              <i />
              <i />
            </span>
          </p>
        ) : null}
      </div>
      {readOnly ? (
        <p className="chat-readonly">The conversation is read-only for this request.</p>
      ) : (
        <form className="chat-form" onSubmit={handleSubmit}>
          <label htmlFor="request-message">Message</label>
          <textarea
            id="request-message"
            maxLength={4000}
            onChange={(event) => setMessage(event.target.value)}
            rows={4}
            value={message}
          />
          <button disabled={isSending} type="submit">
            <SendHorizonal aria-hidden="true" size={18} />
            Send
          </button>
        </form>
      )}
    </section>
  );
}
