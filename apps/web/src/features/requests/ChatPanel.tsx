import { Bot, Mic, MicOff, SendHorizonal } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import type { Ticket } from "../../lib/api-client/tickets";
import { useSpeechToText } from "./useSpeechToText";
import { VoiceCallControls } from "./VoiceCallControls";

const GREETING =
  "Hi, I am Istari. Please tell me about the query you would like to " +
  "submit and we will take it from there.";

type ChatPanelProps = {
  csrfToken?: string;
  isSending: boolean;
  onSend: (message: string, onSuccess?: () => void) => void;
  readOnly?: boolean;
  ticket?: Ticket;
};

export function ChatPanel({
  csrfToken = "",
  isSending,
  onSend,
  readOnly = false,
  ticket,
}: ChatPanelProps) {
  const [message, setMessage] = useState("");
  const transcriptRef = useRef<HTMLDivElement>(null);
  const speech = useSpeechToText((transcript) => {
    setMessage((current) =>
      current.trim() ? `${current.trimEnd()} ${transcript.trim()}` : transcript.trim(),
    );
  });
  const clarificationRequests =
    ticket?.state === "INFO_REQUIRED" ? (ticket.clarificationRequests ?? []) : [];
  const trimmedMessage = message.trim();
  const messageTooShort = trimmedMessage.length > 0 && trimmedMessage.length < 3;

  useEffect(() => {
    const transcript = transcriptRef.current;
    if (transcript) transcript.scrollTop = transcript.scrollHeight;
  }, [isSending, ticket?.messages.length]);

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (trimmedMessage.length < 3) {
      return;
    }
    speech.stop();
    onSend(trimmedMessage, () => setMessage(""));
  }

  return (
    <section className="surface chat-panel" aria-labelledby="chat-title">
      <div className="chat-panel__heading">
        <span className="chat-panel__icon">
          <Bot aria-hidden="true" size={20} />
        </span>
        <div>
          <h2 id="chat-title">Conversation with Istari</h2>
          <p>Describe the decision you need to make. Istari will shape it into a clear request.</p>
        </div>
      </div>
      <div
        aria-label="Conversation history"
        aria-live="polite"
        className="chat-transcript"
        ref={transcriptRef}
      >
        {ticket?.messages.length ? (
          ticket.messages.map((item) => (
            <article className={`chat-message chat-message--${item.author}`} key={item.id}>
              <header>
                <strong>{item.author === "user" ? "You" : "Istari"}</strong>
                <time dateTime={item.createdAt}>{formatMessageTime(item.createdAt)}</time>
              </header>
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
            <strong>More information needed</strong>
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
          <label className="sr-only" htmlFor="request-message">
            Message
          </label>
          <textarea
            id="request-message"
            maxLength={4000}
            onChange={(event) => setMessage(event.target.value)}
            rows={4}
            placeholder="Add the next detail or answer Istari's question…"
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
          {speech.isSupported ? (
            <small className="field-hint" id="dictation-privacy-notice">
              Dictation is provided by your browser and may process audio remotely. Use synthetic
              data only.
            </small>
          ) : null}
          {csrfToken ? (
            <VoiceCallControls
              csrfToken={csrfToken}
              onTranscript={(transcript) =>
                setMessage((current) => {
                  const combined = current.trim()
                    ? `${current.trimEnd()}\n\n${transcript}`
                    : transcript;
                  return combined.slice(0, 4000);
                })
              }
            />
          ) : null}
          <div className="chat-form__actions">
            {speech.isSupported ? (
              <button
                aria-pressed={speech.isListening}
                aria-describedby="dictation-privacy-notice"
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

function formatMessageTime(value: string) {
  return new Intl.DateTimeFormat("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}
