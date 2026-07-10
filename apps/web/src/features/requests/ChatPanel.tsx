import { Bot, Mic, MicOff, SendHorizonal } from "lucide-react";
import { useState } from "react";

import type { Ticket } from "../../lib/api-client/tickets";
import { useSpeechToText } from "./useSpeechToText";

const GREETING =
  "Hi, I am Istari. Please tell me about the query you would like to " +
  "submit and we will take it from there.";

type ChatPanelProps = {
  isSending: boolean;
  onSend: (message: string) => void;
  readOnly?: boolean;
  ticket?: Ticket;
};

export function ChatPanel({ isSending, onSend, readOnly = false, ticket }: ChatPanelProps) {
  const [message, setMessage] = useState("");
  const speech = useSpeechToText((transcript) => {
    setMessage((current) =>
      current.trim() ? `${current.trimEnd()} ${transcript.trim()}` : transcript.trim(),
    );
  });
  const clarificationRequests =
    ticket?.state === "INFO_REQUIRED" ? (ticket.clarificationRequests ?? []) : [];
  const trimmedMessage = message.trim();
  const messageTooShort = trimmedMessage.length > 0 && trimmedMessage.length < 3;

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (trimmedMessage.length < 3) {
      return;
    }
    speech.stop();
    onSend(trimmedMessage);
    setMessage("");
  }

  return (
    <section className="surface chat-panel" aria-labelledby="chat-title">
      <div className="section-heading access-heading">
        <Bot aria-hidden="true" size={20} />
        <h2 id="chat-title">Customer chatbot</h2>
      </div>
      <div className="chat-transcript" aria-live="polite">
        {ticket?.messages.length ? (
          ticket.messages.map((item) => (
            <article className={`chat-message chat-message--${item.author}`} key={item.id}>
              <strong>{item.author === "user" ? "You" : "Istari"}</strong>
              <p>{item.body}</p>
            </article>
          ))
        ) : readOnly ? (
          <p>No chat transcript</p>
        ) : (
          <article className="chat-message chat-message--assistant">
            <strong>Istari</strong>
            <p>{GREETING}</p>
          </article>
        )}
        {clarificationRequests.map((request) => (
          <article
            className="chat-message chat-message--assistant chat-message--clarification"
            key={request.id}
          >
            <strong>Istari</strong>
            <p>Manager clarification requested: {request.reason}</p>
            <ul>
              {request.questions.map((question) => (
                <li key={question}>{question}</li>
              ))}
            </ul>
          </article>
        ))}
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
      ) : ticket?.conversationStatus === "closed" ? (
        <p className="chat-readonly">
          The conversation is complete. Review the details and press Submit.
        </p>
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
          {messageTooShort ? (
            <small className="field-hint">Messages need at least 3 characters.</small>
          ) : null}
          {speech.isListening ? (
            <p className="chat-dictation" role="status">
              Listening. Speak your message, then press Stop dictation.
            </p>
          ) : null}
          {speech.error ? <small className="field-hint">{speech.error}</small> : null}
          <div className="chat-form__actions">
            {speech.isSupported ? (
              <button
                aria-pressed={speech.isListening}
                className={speech.isListening ? "chat-mic chat-mic--listening" : "chat-mic"}
                onClick={speech.isListening ? speech.stop : speech.start}
                type="button"
              >
                {speech.isListening ? (
                  <MicOff aria-hidden="true" size={18} />
                ) : (
                  <Mic aria-hidden="true" size={18} />
                )}
                {speech.isListening ? "Stop dictation" : "Dictate"}
              </button>
            ) : null}
            <button disabled={isSending || trimmedMessage.length < 3} type="submit">
              <SendHorizonal aria-hidden="true" size={18} />
              Send
            </button>
          </div>
        </form>
      )}
    </section>
  );
}
