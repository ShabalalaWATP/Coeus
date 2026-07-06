import { SendHorizonal } from "lucide-react";
import { useState } from "react";

import type { Ticket } from "../../lib/api-client/tickets";

type ChatPanelProps = {
  isSending: boolean;
  onSend: (message: string) => void;
  ticket?: Ticket;
};

export function ChatPanel({ isSending, onSend, ticket }: ChatPanelProps) {
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
        <SendHorizonal aria-hidden="true" size={20} />
        <h2 id="chat-title">Chat Intake</h2>
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
      </div>
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
    </section>
  );
}
