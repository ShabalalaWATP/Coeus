import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, expect, test, vi } from "vitest";

import { VoiceCallControls } from "./VoiceCallControls";

let peer: TestPeer | null = null;

afterEach(() => {
  vi.unstubAllGlobals();
  peer = null;
});

test("bounds a provider session error", async () => {
  arrangeVoice();
  renderControl(vi.fn());
  await connect();

  act(() => {
    peer?.channel.onmessage?.({
      data: JSON.stringify({ type: "error", error: { message: "secret provider detail" } }),
    } as MessageEvent);
  });

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "voice provider reported a session error",
  );
  expect(screen.getByRole("alert")).not.toHaveTextContent("secret provider detail");
  expect(peer?.closed).toBe(true);
});

test("waits beyond 500 ms for delayed final events", async () => {
  const onTranscript = vi.fn();
  arrangeVoice();
  renderControl(onTranscript);
  await connect();
  await act(() => peer?.channel.onopen?.(new Event("open")));

  setTimeout(() => emitDelayedEvents(), 600);
  await userEvent.click(screen.getByRole("button", { name: "Stop voice" }));

  await waitFor(
    () =>
      expect(onTranscript).toHaveBeenCalledWith(
        "Voice drafting transcript:\nYou: Delayed detail\nIstari: Delayed acknowledgement",
      ),
    { timeout: 2_000 },
  );
});

async function connect() {
  await userEvent.click(await screen.findByRole("button", { name: "Talk with Istari" }));
  await waitFor(() => expect(peer?.remoteDescription).not.toBeNull());
}

function emitDelayedEvents() {
  act(() => {
    peer?.channel.onmessage?.(
      event("conversation.item.input_audio_transcription.completed", {
        transcript: "Delayed detail",
      }),
    );
    peer?.channel.onmessage?.(
      event("response.output_audio_transcript.done", {
        transcript: "Delayed acknowledgement",
      }),
    );
    peer?.channel.onmessage?.(event("response.done", { response: { output: [] } }));
  });
}

function event(type: string, extra: object): MessageEvent {
  return { data: JSON.stringify({ type, ...extra }) } as MessageEvent;
}

function renderControl(onTranscript: (value: string) => void) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <VoiceCallControls csrfToken="csrf" onTranscript={onTranscript} />
    </QueryClientProvider>,
  );
}

function arrangeVoice() {
  Object.defineProperty(navigator, "mediaDevices", {
    configurable: true,
    value: { getUserMedia: vi.fn().mockResolvedValue({ getTracks: () => [{ stop: vi.fn() }] }) },
  });
  vi.stubGlobal(
    "RTCPeerConnection",
    vi.fn(function PeerConstructor() {
      peer = new TestPeer();
      return peer;
    }),
  );
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(voiceState) })
      .mockResolvedValueOnce(answerResponse())
      .mockResolvedValueOnce({ ok: true }),
  );
}

const voiceState = {
  model: "gpt-realtime-2.1",
  availableModels: ["gpt-realtime-2.1", "gpt-realtime-mini"],
  enabled: true,
  apiKeyConfigured: true,
};

function answerResponse() {
  return {
    headers: { get: () => "voice-token" },
    ok: true,
    text: () => Promise.resolve("v=0\r\nm=audio answer"),
  };
}

class TestPeer {
  channel = new TestChannel();
  closed = false;
  remoteDescription: RTCSessionDescriptionInit | null = null;
  connectionState: RTCPeerConnectionState = "new";
  onconnectionstatechange: (() => void) | null = null;
  ontrack: ((event: RTCTrackEvent) => void) | null = null;
  addTrack = vi.fn();
  createDataChannel = () => this.channel as unknown as RTCDataChannel;
  createOffer = () => Promise.resolve({ type: "offer" as const, sdp: "v=0\r\nm=audio offer" });
  setLocalDescription = vi.fn().mockResolvedValue(undefined);
  setRemoteDescription = (description: RTCSessionDescriptionInit) => {
    this.remoteDescription = description;
    return Promise.resolve();
  };
  close = () => {
    this.closed = true;
  };
}

class TestChannel {
  readyState: RTCDataChannelState = "open";
  onopen: ((event: Event) => unknown) | null = null;
  onmessage: ((event: MessageEvent) => unknown) | null = null;
  onerror: ((event: Event) => unknown) | null = null;
  close = vi.fn();
  send = vi.fn();
}
