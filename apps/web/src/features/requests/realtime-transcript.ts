const MAX_TRANSCRIPT_CHARS = 3500;

type Speaker = "assistant" | "user";
type TranscriptItem = { delta: string; role?: Speaker; text: string };

export type TranscriptState = {
  fallbackAssistantDelta: string;
  fallbackLines: string[];
  fallbackUserDelta: string;
  items: Map<string, TranscriptItem>;
  order: string[];
};

type RealtimeEvent = {
  delta?: string;
  item?: { id?: string; role?: string };
  item_id?: string;
  previous_item_id?: string | null;
  response?: {
    output?: { content?: { transcript?: string }[]; id?: string; role?: string }[];
  };
  transcript?: string;
  type?: string;
};

export function collectTranscript(raw: unknown, state: TranscriptState): string | undefined {
  if (typeof raw !== "string") return;
  try {
    const event = JSON.parse(raw) as RealtimeEvent;
    if (event.type === "conversation.item.added") {
      registerItem(state, event.item?.id, roleOf(event.item?.role), event.previous_item_id);
    } else if (event.type === "conversation.item.input_audio_transcription.delta") {
      appendDelta(state, event.item_id, "user", event.delta);
    } else if (event.type === "response.output_audio_transcript.delta") {
      appendDelta(state, event.item_id, "assistant", event.delta);
    } else if (event.type === "conversation.item.input_audio_transcription.completed") {
      finaliseItem(state, event.item_id, "user", event.transcript);
    } else if (event.type === "response.output_audio_transcript.done") {
      finaliseItem(state, event.item_id, "assistant", event.transcript);
    } else if (event.type === "response.done") {
      collectCompletedResponse(state, event.response?.output ?? []);
    }
    return event.type;
  } catch {
    // Ignore non-JSON WebRTC control messages.
    return undefined;
  }
}

export function completeTranscript(state: TranscriptState): string {
  finaliseFallback(state, "fallbackUserDelta", "You");
  finaliseFallback(state, "fallbackAssistantDelta", "Istari");
  const lines: string[] = [];
  for (const id of state.order) {
    const item = state.items.get(id);
    const value = item?.text.trim() || item?.delta.trim();
    if (item?.role && value) appendLine(lines, `${labelFor(item.role)}: ${value}`);
  }
  for (const line of state.fallbackLines) appendLine(lines, line);
  return lines.join("\n").trim();
}

export function emptyTranscript(): TranscriptState {
  return {
    fallbackAssistantDelta: "",
    fallbackLines: [],
    fallbackUserDelta: "",
    items: new Map(),
    order: [],
  };
}

function collectCompletedResponse(
  state: TranscriptState,
  output: NonNullable<RealtimeEvent["response"]>["output"],
) {
  for (const item of output ?? []) {
    const transcript = item.content
      ?.map((content) => content.transcript ?? "")
      .join(" ")
      .trim();
    if (transcript) finaliseItem(state, item.id, roleOf(item.role) ?? "assistant", transcript);
  }
}

function appendDelta(
  state: TranscriptState,
  itemId: string | undefined,
  role: Speaker,
  delta = "",
) {
  if (!itemId) {
    const key = role === "user" ? "fallbackUserDelta" : "fallbackAssistantDelta";
    state[key] = `${state[key]}${delta}`.slice(0, MAX_TRANSCRIPT_CHARS);
    return;
  }
  const item = registerItem(state, itemId, role);
  item.delta = `${item.delta}${delta}`.slice(0, MAX_TRANSCRIPT_CHARS);
}

function finaliseItem(
  state: TranscriptState,
  itemId: string | undefined,
  role: Speaker,
  finalValue?: string,
) {
  if (!itemId) {
    const key = role === "user" ? "fallbackUserDelta" : "fallbackAssistantDelta";
    const value = finalValue?.trim() || state[key].trim();
    state[key] = "";
    if (value) appendLine(state.fallbackLines, `${labelFor(role)}: ${value}`);
    return;
  }
  const item = registerItem(state, itemId, role);
  item.text = (finalValue?.trim() || item.delta.trim()).slice(0, MAX_TRANSCRIPT_CHARS);
  item.delta = "";
}

function finaliseFallback(
  state: TranscriptState,
  pending: "fallbackAssistantDelta" | "fallbackUserDelta",
  speaker: string,
) {
  const value = state[pending].trim();
  state[pending] = "";
  if (value) appendLine(state.fallbackLines, `${speaker}: ${value}`);
}

function registerItem(
  state: TranscriptState,
  id: string | undefined,
  role?: Speaker,
  previous?: string | null,
): TranscriptItem {
  if (!id) return { delta: "", role, text: "" };
  const item = state.items.get(id) ?? { delta: "", text: "" };
  if (role) item.role = role;
  state.items.set(id, item);
  if (!state.order.includes(id)) state.order.push(id);
  if (previous !== undefined) {
    state.order = state.order.filter((itemId) => itemId !== id);
    const index = previous === null ? -1 : state.order.indexOf(previous);
    state.order.splice(index + 1, 0, id);
  }
  return item;
}

function appendLine(lines: string[], line: string) {
  const remaining = MAX_TRANSCRIPT_CHARS - lines.join("\n").length;
  if (remaining > 0 && !lines.includes(line)) lines.push(line.slice(0, remaining));
}

function roleOf(role?: string): Speaker | undefined {
  return role === "user" || role === "assistant" ? role : undefined;
}

function labelFor(role: Speaker) {
  return role === "user" ? "You" : "Istari";
}
