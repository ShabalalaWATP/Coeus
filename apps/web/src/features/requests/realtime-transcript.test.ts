import { expect, test } from "vitest";

import { collectTranscript, completeTranscript, emptyTranscript } from "./realtime-transcript";

test("orders asynchronous transcripts by their Realtime conversation items", () => {
  const state = emptyTranscript();
  collectTranscript(
    JSON.stringify({
      type: "conversation.item.added",
      item: { id: "user-1", role: "user" },
      previous_item_id: null,
    }),
    state,
  );
  collectTranscript(
    JSON.stringify({
      type: "conversation.item.added",
      item: { id: "assistant-1", role: "assistant" },
      previous_item_id: "user-1",
    }),
    state,
  );

  collectTranscript(
    JSON.stringify({
      type: "response.output_audio_transcript.done",
      item_id: "assistant-1",
      transcript: "Which region?",
    }),
    state,
  );
  collectTranscript(
    JSON.stringify({
      type: "conversation.item.input_audio_transcription.completed",
      item_id: "user-1",
      transcript: "Assess mock port activity.",
    }),
    state,
  );

  expect(completeTranscript(state)).toBe("You: Assess mock port activity.\nIstari: Which region?");
});

test("keeps legacy events without item identifiers bounded and usable", () => {
  const state = emptyTranscript();
  collectTranscript(
    JSON.stringify({
      type: "conversation.item.input_audio_transcription.delta",
      delta: "Need a synthetic briefing",
    }),
    state,
  );
  collectTranscript("not-json", state);

  expect(completeTranscript(state)).toBe("You: Need a synthetic briefing");
});

test("collects item deltas and completed response transcripts", () => {
  const state = emptyTranscript();
  collectTranscript(
    JSON.stringify({
      type: "conversation.item.input_audio_transcription.delta",
      item_id: "user-1",
      delta: "Need synthetic ",
    }),
    state,
  );
  collectTranscript(
    JSON.stringify({
      type: "conversation.item.input_audio_transcription.delta",
      item_id: "user-1",
      delta: "port activity",
    }),
    state,
  );
  collectTranscript(
    JSON.stringify({
      type: "conversation.item.input_audio_transcription.completed",
      item_id: "user-1",
    }),
    state,
  );
  collectTranscript(
    JSON.stringify({
      type: "response.done",
      response: {
        output: [
          {
            id: "assistant-1",
            role: "assistant",
            content: [{ transcript: "Which reporting window?" }],
          },
        ],
      },
    }),
    state,
  );

  expect(completeTranscript(state)).toBe(
    "You: Need synthetic port activity\nIstari: Which reporting window?",
  );
});

test("ignores unsupported payloads and retains a completed legacy assistant line", () => {
  const state = emptyTranscript();
  collectTranscript(undefined, state);
  collectTranscript(JSON.stringify({ type: "unsupported.event" }), state);
  collectTranscript(
    JSON.stringify({
      type: "response.output_audio_transcript.done",
      transcript: "How urgent is the request?",
    }),
    state,
  );

  expect(completeTranscript(state)).toBe("Istari: How urgent is the request?");
});
