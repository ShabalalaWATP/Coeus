import { useCallback, useEffect, useRef, useState } from "react";

import { createVoiceSession, releaseVoiceSession } from "../../lib/api-client/voice";

type VoiceStatus = "idle" | "connecting" | "connected" | "stopping";
type TranscriptState = { assistantDelta: string; lines: string[]; userDelta: string };

const CONNECTION_TIMEOUT_MS = 15_000;
const TRANSCRIPT_DRAIN_MS = 500;
const MAX_TRANSCRIPT_CHARS = 3500;

export function useRealtimeVoice(csrfToken: string, onTranscript: (transcript: string) => void) {
  const [status, setStatus] = useState<VoiceStatus>("idle");
  const [error, setError] = useState<string | null>(null);
  const mountedRef = useRef(true);
  const operationRef = useRef(0);
  const peerRef = useRef<RTCPeerConnection | null>(null);
  const channelRef = useRef<RTCDataChannel | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const tokenRef = useRef<string | null>(null);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const transcriptRef = useRef<TranscriptState>(emptyTranscript());

  const releaseToken = useCallback(() => {
    const token = tokenRef.current;
    tokenRef.current = null;
    if (token) void releaseVoiceSession(token, csrfToken).catch(() => undefined);
  }, [csrfToken]);

  const closeResources = useCallback(() => {
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    timeoutRef.current = null;
    channelRef.current?.close();
    peerRef.current?.close();
    streamRef.current?.getTracks().forEach((track) => track.stop());
    if (audioRef.current) audioRef.current.srcObject = null;
    channelRef.current = null;
    peerRef.current = null;
    streamRef.current = null;
    audioRef.current = null;
    releaseToken();
  }, [releaseToken]);

  const fail = useCallback(
    (message: string) => {
      operationRef.current += 1;
      closeResources();
      if (mountedRef.current) {
        setStatus("idle");
        setError(message);
      }
    },
    [closeResources],
  );

  const stop = useCallback(async () => {
    operationRef.current += 1;
    streamRef.current?.getTracks().forEach((track) => track.stop());
    if (mountedRef.current) setStatus("stopping");
    const channel = channelRef.current;
    if (channel?.readyState === "open") {
      channel.send(JSON.stringify({ type: "input_audio_buffer.commit" }));
      await new Promise((resolve) => setTimeout(resolve, TRANSCRIPT_DRAIN_MS));
    }
    const transcript = completeTranscript(transcriptRef.current);
    closeResources();
    transcriptRef.current = emptyTranscript();
    if (mountedRef.current) {
      setStatus("idle");
      if (transcript) onTranscript(`Voice drafting transcript:\n${transcript}`);
    }
  }, [closeResources, onTranscript]);

  const start = useCallback(async () => {
    const operation = operationRef.current + 1;
    operationRef.current = operation;
    setError(null);
    setStatus("connecting");
    transcriptRef.current = emptyTranscript();
    const peer = new RTCPeerConnection();
    peerRef.current = peer;
    timeoutRef.current = setTimeout(
      () => fail("Voice could not connect in time. Please try again."),
      CONNECTION_TIMEOUT_MS,
    );
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (!isCurrent(operationRef, operation, mountedRef)) {
        stream.getTracks().forEach((track) => track.stop());
        peer.close();
        return;
      }
      streamRef.current = stream;
      const audio = new Audio();
      audio.autoplay = true;
      audioRef.current = audio;
      peer.ontrack = (event) => {
        audio.srcObject = event.streams[0] ?? null;
      };
      peer.onconnectionstatechange = () => {
        if (["failed", "disconnected"].includes(peer.connectionState)) {
          fail("The voice connection was lost. Please try again.");
        }
      };
      stream.getTracks().forEach((track) => peer.addTrack(track, stream));
      const channel = peer.createDataChannel("oai-events");
      channelRef.current = channel;
      channel.onopen = () => {
        if (timeoutRef.current) clearTimeout(timeoutRef.current);
        timeoutRef.current = null;
        if (mountedRef.current) setStatus("connected");
      };
      channel.onmessage = (event) => collectTranscript(event.data, transcriptRef.current);
      channel.onerror = () => fail("The voice connection encountered an error.");
      const offer = await peer.createOffer();
      await peer.setLocalDescription(offer);
      const started = await createVoiceSession(offer.sdp ?? "", csrfToken);
      if (!isCurrent(operationRef, operation, mountedRef)) {
        void releaseVoiceSession(started.token, csrfToken).catch(() => undefined);
        peer.close();
        return;
      }
      tokenRef.current = started.token;
      await peer.setRemoteDescription({ type: "answer", sdp: started.answer });
    } catch {
      if (operationRef.current === operation) {
        fail("Voice could not start. Check microphone permission and try again.");
      }
    }
  }, [csrfToken, fail]);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      operationRef.current += 1;
      closeResources();
    };
  }, [closeResources]);
  return { error, isActive: status !== "idle", start, status, stop };
}

function collectTranscript(raw: unknown, state: TranscriptState) {
  if (typeof raw !== "string") return;
  try {
    const event = JSON.parse(raw) as RealtimeEvent;
    if (event.type === "conversation.item.input_audio_transcription.delta") {
      state.userDelta += event.delta ?? "";
    } else if (event.type === "response.output_audio_transcript.delta") {
      state.assistantDelta += event.delta ?? "";
    } else if (event.type === "conversation.item.input_audio_transcription.completed") {
      appendFinal(state, "userDelta", "You", event.transcript);
    } else if (event.type === "response.output_audio_transcript.done") {
      appendFinal(state, "assistantDelta", "Istari", event.transcript);
    } else if (event.type === "response.done") {
      const transcript = event.response?.output
        ?.flatMap((item) => item.content ?? [])
        .map((content) => content.transcript ?? "")
        .join(" ")
        .trim();
      if (transcript) appendFinal(state, "assistantDelta", "Istari", transcript);
    }
  } catch {
    // Ignore non-JSON WebRTC control messages.
  }
}

type RealtimeEvent = {
  delta?: string;
  response?: { output?: { content?: { transcript?: string }[] }[] };
  transcript?: string;
  type?: string;
};

function appendFinal(
  state: TranscriptState,
  pending: "assistantDelta" | "userDelta",
  speaker: string,
  finalValue?: string,
) {
  const value = finalValue?.trim() || state[pending].trim();
  state[pending] = "";
  if (value) appendLine(state.lines, `${speaker}: ${value}`);
}

function completeTranscript(state: TranscriptState): string {
  appendFinal(state, "userDelta", "You");
  appendFinal(state, "assistantDelta", "Istari");
  return state.lines.join("\n").trim();
}

function appendLine(lines: string[], line: string) {
  const remaining = MAX_TRANSCRIPT_CHARS - lines.join("\n").length;
  if (remaining > 0 && !lines.includes(line)) lines.push(line.slice(0, remaining));
}

function emptyTranscript(): TranscriptState {
  return { assistantDelta: "", lines: [], userDelta: "" };
}

function isCurrent(
  operationRef: { current: number },
  operation: number,
  mountedRef: { current: boolean },
) {
  return operationRef.current === operation && mountedRef.current;
}
