import { Bot, SendHorizonal } from "lucide-react";
import { useState } from "react";

import type { Ticket } from "../../lib/api-client/tickets";

type RfiFollowUpChatProps = {
  feedbackPending: boolean;
  isSending: boolean;
  onSend: (feedback: string, onSuccess?: () => void) => void;
  ticket: Ticket;
};

export function RfiFollowUpChat({
  feedbackPending,
  isSending,
  onSend,
  ticket,
}: RfiFollowUpChatProps) {
  const [feedback, setFeedback] = useState("");
  const value = feedback.trim();

  function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (value.length < 3) return;
    onSend(value, () => setFeedback(""));
  }

  return (
    <section className="surface chat-panel" aria-labelledby="rfi-follow-up-title">
      <div className="chat-panel__heading">
        <span className="chat-panel__icon">
          <Bot aria-hidden="true" size={20} />
        </span>
        <div>
          <h2 id="rfi-follow-up-title">Conversation with Istari</h2>
          <p>Tell Istari what the offered products did not answer.</p>
        </div>
      </div>
      <div aria-label="Conversation history" aria-live="polite" className="chat-transcript">
        {ticket.messages.map((item) => (
          <article className={`chat-message chat-message--${item.author}`} key={item.id}>
            <header>
              <strong>{item.author === "user" ? "You" : "Istari"}</strong>
              <time dateTime={item.createdAt}>{formatMessageTime(item.createdAt)}</time>
            </header>
            <p>{item.body}</p>
          </article>
        ))}
      </div>
      {feedbackPending ? (
        <form className="chat-form" onSubmit={submit}>
          <label htmlFor="rfi-search-feedback">What was missing?</label>
          <textarea
            id="rfi-search-feedback"
            maxLength={1000}
            onChange={(event) => setFeedback(event.target.value)}
            placeholder="For example, the reports were too old and did not cover Donetsk."
            rows={3}
            value={feedback}
          />
          <div className="chat-form__actions">
            <button disabled={isSending || value.length < 3} type="submit">
              <SendHorizonal aria-hidden="true" size={18} />
              {isSending ? "Sending…" : "Send feedback"}
            </button>
          </div>
        </form>
      ) : (
        <p className="chat-readonly">
          Feedback recorded. Choose whether to search again, continue to new tasking or close the
          request.
        </p>
      )}
    </section>
  );
}

function formatMessageTime(value: string) {
  return new Intl.DateTimeFormat("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}
