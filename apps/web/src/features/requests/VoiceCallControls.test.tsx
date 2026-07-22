import { StrictMode } from "react";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, expect, test, vi } from "vitest";

import { VoiceCallControls } from "./VoiceCallControls";

let latestPeer: FakePeer | null = null;

afterEach(() => {
  vi.unstubAllGlobals();
  latestPeer = null;
});

test("hides the control while voice is disabled", async () => {
  stubBrowser();
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(jsonResponse({ ...voiceState, enabled: false })),
  );
  renderControl(vi.fn());
  await waitFor(() => expect(fetch).toHaveBeenCalled());
  expect(screen.queryByRole("button", { name: "Talk with Istari" })).not.toBeInTheDocument();
});

test("starts a WebRTC call, captures both transcripts and cleans up on stop", async () => {
  const onTranscript = vi.fn();
  const stopTrack = vi.fn();
  stubBrowser(stopTrack);
  stubVoiceSessionFetch();
  renderControl(onTranscript, false, "ticket-123");

  await userEvent.click(await screen.findByRole("button", { name: "Talk with Istari" }));
  await waitFor(() =>
    expect(latestPeer?.remoteDescription).toEqual({ type: "answer", sdp: "v=0\r\nm=audio answer" }),
  );
  expect(fetch).toHaveBeenNthCalledWith(
    2,
    "http://127.0.0.1:8001/api/v1/voice/session?ticketId=ticket-123",
    expect.objectContaining({ method: "POST" }),
  );
  act(() => {
    latestPeer?.channel.onmessage?.({
      data: JSON.stringify({
        type: "conversation.item.input_audio_transcription.completed",
        transcript: "Need an EW assessment",
      }),
    } as MessageEvent);
    latestPeer?.channel.onmessage?.({
      data: JSON.stringify({
        type: "response.output_audio_transcript.done",
        transcript: "Which region?",
      }),
    } as MessageEvent);
    latestPeer?.channel.onopen?.(new Event("open"));
  });
  expect(latestPeer?.channel.send).toHaveBeenNthCalledWith(
    1,
    JSON.stringify({ type: "response.create" }),
  );
  await userEvent.click(screen.getByRole("button", { name: "Stop voice" }));

  await waitFor(
    () =>
      expect(onTranscript).toHaveBeenCalledWith(
        "Voice drafting transcript:\nYou: Need an EW assessment\nIstari: Which region?",
      ),
    { timeout: 2_000 },
  );
  expect(stopTrack).toHaveBeenCalled();
  expect(latestPeer?.closed).toBe(true);
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(3));
});

test("cancels safely while microphone permission is pending", async () => {
  const pendingMedia = deferred<MediaStream>();
  const stopTrack = vi.fn();
  stubBrowser(stopTrack);
  vi.spyOn(navigator.mediaDevices, "getUserMedia").mockReturnValueOnce(pendingMedia.promise);
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(voiceState)));
  renderControl(vi.fn());

  await userEvent.click(await screen.findByRole("button", { name: "Talk with Istari" }));
  const cancel = screen.getByRole("button", { name: "Cancel voice" });
  expect(cancel).toBeEnabled();
  await userEvent.click(cancel);
  pendingMedia.resolve({ getTracks: () => [{ stop: stopTrack }] } as unknown as MediaStream);

  await waitFor(() => expect(stopTrack).toHaveBeenCalled());
  expect(screen.getByRole("button", { name: "Talk with Istari" })).toBeEnabled();
});

test("releases a late server session after the user cancels", async () => {
  const pendingSession = deferred<ReturnType<typeof textResponse>>();
  stubBrowser();
  const fetchMock = vi
    .fn()
    .mockResolvedValueOnce(jsonResponse(voiceState))
    .mockReturnValueOnce(pendingSession.promise)
    .mockResolvedValueOnce(emptyResponse());
  vi.stubGlobal("fetch", fetchMock);
  renderControl(vi.fn());

  await userEvent.click(await screen.findByRole("button", { name: "Talk with Istari" }));
  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
  await userEvent.click(screen.getByRole("button", { name: "Cancel voice" }));
  pendingSession.resolve(textResponse("v=0\r\nm=audio answer"));

  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
  expect(latestPeer?.closed).toBe(true);
  expect(fetchMock).toHaveBeenLastCalledWith(
    "http://127.0.0.1:8001/api/v1/voice/session/voice-token",
    expect.objectContaining({ method: "DELETE" }),
  );
});

test("stops a late microphone stream after unmount", async () => {
  const pendingMedia = deferred<MediaStream>();
  const stopTrack = vi.fn();
  stubBrowser(stopTrack);
  vi.spyOn(navigator.mediaDevices, "getUserMedia").mockReturnValueOnce(pendingMedia.promise);
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(voiceState)));
  const rendered = renderControl(vi.fn());

  await userEvent.click(await screen.findByRole("button", { name: "Talk with Istari" }));
  rendered.unmount();
  pendingMedia.resolve({ getTracks: () => [{ stop: stopTrack }] } as unknown as MediaStream);

  await waitFor(() => expect(stopTrack).toHaveBeenCalled());
});

test("starts correctly when React StrictMode replays effects", async () => {
  stubBrowser();
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(voiceState))
      .mockResolvedValueOnce(textResponse("v=0\r\nm=audio answer")),
  );
  renderControl(vi.fn(), true);

  await userEvent.click(await screen.findByRole("button", { name: "Talk with Istari" }));
  await waitFor(() => expect(latestPeer?.remoteDescription).not.toBeNull());
});

test("reports denied microphone permission and returns to the idle control", async () => {
  stubBrowser();
  vi.spyOn(navigator.mediaDevices, "getUserMedia").mockRejectedValueOnce(
    new DOMException("device detail that must not be shown", "NotAllowedError"),
  );
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(voiceState)));
  renderControl(vi.fn());

  await userEvent.click(await screen.findByRole("button", { name: "Talk with Istari" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Microphone permission was denied");
  expect(screen.getByRole("button", { name: "Talk with Istari" })).toBeEnabled();
});

test("closes a failed peer connection and reports a bounded error", async () => {
  stubBrowser();
  stubVoiceSessionFetch();
  renderControl(vi.fn());

  await userEvent.click(await screen.findByRole("button", { name: "Talk with Istari" }));
  await waitFor(() => expect(latestPeer?.remoteDescription).not.toBeNull());
  act(() => {
    if (latestPeer) latestPeer.connectionState = "failed";
    latestPeer?.onconnectionstatechange?.();
  });

  expect(await screen.findByRole("alert")).toHaveTextContent("voice connection was lost");
  expect(latestPeer?.closed).toBe(true);
});

test("ignores malformed events and stops an empty errored call without a transcript", async () => {
  const onTranscript = vi.fn();
  stubBrowser();
  stubVoiceSessionFetch();
  renderControl(onTranscript);
  await userEvent.click(await screen.findByRole("button", { name: "Talk with Istari" }));
  await waitFor(() => expect(latestPeer?.remoteDescription).not.toBeNull());
  act(() => {
    latestPeer?.ontrack?.({ streams: [] } as unknown as RTCTrackEvent);
    latestPeer?.channel.onmessage?.({ data: 42 } as MessageEvent);
    latestPeer?.channel.onmessage?.({ data: "not-json" } as MessageEvent);
    latestPeer?.channel.onmessage?.({ data: JSON.stringify({ type: "other" }) } as MessageEvent);
    latestPeer?.channel.onerror?.(new Event("error"));
    latestPeer?.channel.onopen?.(new Event("open"));
  });
  expect(screen.getByRole("alert")).toHaveTextContent("voice connection encountered an error");
  await userEvent.click(screen.getByRole("button", { name: "Stop voice" }));
  expect(onTranscript).not.toHaveBeenCalled();
});

test("preserves in-flight transcript deltas when the user stops", async () => {
  const onTranscript = vi.fn();
  stubBrowser();
  stubVoiceSessionFetch();
  renderControl(onTranscript);
  await userEvent.click(await screen.findByRole("button", { name: "Talk with Istari" }));
  await waitFor(() => expect(latestPeer?.remoteDescription).not.toBeNull());
  act(() => {
    latestPeer?.channel.onopen?.(new Event("open"));
    latestPeer?.channel.onmessage?.({
      data: JSON.stringify({
        type: "conversation.item.input_audio_transcription.delta",
        delta: "Need a China cyber update",
      }),
    } as MessageEvent);
    latestPeer?.channel.onmessage?.({
      data: JSON.stringify({
        type: "response.output_audio_transcript.delta",
        delta: "Which timeframe?",
      }),
    } as MessageEvent);
  });

  await userEvent.click(screen.getByRole("button", { name: "Stop voice" }));
  await waitFor(
    () =>
      expect(onTranscript).toHaveBeenCalledWith(
        "Voice drafting transcript:\nYou: Need a China cyber update\nIstari: Which timeframe?",
      ),
    { timeout: 2_000 },
  );
  expect(latestPeer?.channel.send).toHaveBeenCalled();
});

test("captures a completed assistant response transcript", async () => {
  const onTranscript = vi.fn();
  stubBrowser();
  stubVoiceSessionFetch();
  renderControl(onTranscript);
  await userEvent.click(await screen.findByRole("button", { name: "Talk with Istari" }));
  await waitFor(() => expect(latestPeer?.remoteDescription).not.toBeNull());
  act(() => {
    latestPeer?.channel.onopen?.(new Event("open"));
    latestPeer?.channel.onmessage?.({
      data: JSON.stringify({
        type: "response.done",
        response: { output: [{ content: [{ transcript: "Tell me the required timeframe." }] }] },
      }),
    } as MessageEvent);
  });

  await userEvent.click(screen.getByRole("button", { name: "Stop voice" }));
  await waitFor(
    () =>
      expect(onTranscript).toHaveBeenCalledWith(
        "Voice drafting transcript:\nIstari: Tell me the required timeframe.",
      ),
    { timeout: 2_000 },
  );
});

const voiceState = {
  model: "gpt-realtime-mini",
  availableModels: ["gpt-realtime-mini"],
  enabled: true,
  apiKeyConfigured: true,
};

function renderControl(onTranscript: (value: string) => void, strict = false, ticketId?: string) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const control = (
    <QueryClientProvider client={queryClient}>
      <VoiceCallControls csrfToken="csrf" onTranscript={onTranscript} ticketId={ticketId} />
    </QueryClientProvider>
  );
  return render(strict ? <StrictMode>{control}</StrictMode> : control);
}

function stubBrowser(stopTrack = vi.fn()) {
  Object.defineProperty(navigator, "mediaDevices", {
    configurable: true,
    value: { getUserMedia: vi.fn().mockResolvedValue({ getTracks: () => [{ stop: stopTrack }] }) },
  });
  vi.stubGlobal(
    "RTCPeerConnection",
    vi.fn(function PeerConstructor() {
      latestPeer = new FakePeer();
      return latestPeer;
    }),
  );
}

function stubVoiceSessionFetch() {
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(voiceState))
      .mockResolvedValueOnce(textResponse("v=0\r\nm=audio answer"))
      .mockResolvedValueOnce(emptyResponse()),
  );
}

class FakePeer {
  channel = new FakeChannel();
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

class FakeChannel {
  readyState: RTCDataChannelState = "open";
  onopen: ((event: Event) => unknown) | null = null;
  onmessage: ((event: MessageEvent) => unknown) | null = null;
  onerror: ((event: Event) => unknown) | null = null;
  close = vi.fn();
  send = vi.fn();
}

function jsonResponse(payload: object) {
  return { ok: true, json: () => Promise.resolve(payload) };
}

function textResponse(payload: string) {
  return {
    headers: { get: (name: string) => (name === "X-Voice-Session-Token" ? "voice-token" : null) },
    ok: true,
    text: () => Promise.resolve(payload),
  };
}

const emptyResponse = () => ({ ok: true });

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise;
  });
  return { promise, resolve };
}
