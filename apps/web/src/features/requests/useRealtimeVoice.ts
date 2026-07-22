import { useCallback, useEffect, useRef, useState } from "react";

import { createVoiceSession, releaseVoiceSession } from "../../lib/api-client/voice";
import {
  collectTranscript,
  completeTranscript,
  emptyTranscript,
  type TranscriptState,
} from "./realtime-transcript";
import { voiceStartError } from "./voice-start-error";

type VoiceStatus = "idle" | "connecting" | "connected" | "stopping";
const CONNECTION_TIMEOUT_MS = 15_000;
const TRANSCRIPT_DRAIN_IDLE_MS = 1_000;
const TRANSCRIPT_DRAIN_SETTLE_MS = 750;
const TRANSCRIPT_DRAIN_MAX_MS = 2_500;

type TranscriptDrain = ReturnType<typeof createTranscriptDrain>;

export function useRealtimeVoice(
  csrfToken: string,
  onTranscript: (transcript: string) => void,
  ticketId?: string,
) {
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
  const drainRef = useRef<TranscriptDrain | null>(null);

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
    drainRef.current?.finish();
    drainRef.current = null;
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
      const drain = createTranscriptDrain();
      drainRef.current = drain;
      channel.send(JSON.stringify({ type: "input_audio_buffer.commit" }));
      await drain.promise;
      drainRef.current = null;
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
        channel.send(JSON.stringify({ type: "response.create" }));
      };
      channel.onmessage = (event) => {
        const type = collectTranscript(event.data, transcriptRef.current);
        drainRef.current?.signal(type);
        if (type === "error") fail("The voice provider reported a session error.");
      };
      channel.onerror = () => fail("The voice connection encountered an error.");
      const offer = await peer.createOffer();
      await peer.setLocalDescription(offer);
      const started = await createVoiceSession(offer.sdp ?? "", csrfToken, ticketId);
      if (!isCurrent(operationRef, operation, mountedRef)) {
        void releaseVoiceSession(started.token, csrfToken).catch(() => undefined);
        peer.close();
        return;
      }
      tokenRef.current = started.token;
      await peer.setRemoteDescription({ type: "answer", sdp: started.answer });
    } catch (caught) {
      if (operationRef.current === operation) {
        fail(voiceStartError(caught));
      }
    }
  }, [csrfToken, fail, ticketId]);

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

function createTranscriptDrain() {
  let finished = false;
  let resolvePromise!: () => void;
  let idleTimer: ReturnType<typeof setTimeout>;
  const promise = new Promise<void>((resolve) => {
    resolvePromise = resolve;
  });
  const maximumTimer = setTimeout(finish, TRANSCRIPT_DRAIN_MAX_MS);

  function finish() {
    if (finished) return;
    finished = true;
    clearTimeout(idleTimer);
    clearTimeout(maximumTimer);
    resolvePromise();
  }

  function schedule(delay: number) {
    clearTimeout(idleTimer);
    idleTimer = setTimeout(finish, delay);
  }

  function signal(type?: string) {
    if (type === "error") {
      finish();
      return;
    }
    if (
      type?.includes("transcription") ||
      type?.startsWith("response.output_audio_transcript") ||
      type === "response.done"
    ) {
      schedule(TRANSCRIPT_DRAIN_SETTLE_MS);
    }
  }

  schedule(TRANSCRIPT_DRAIN_IDLE_MS);
  return { finish, promise, signal };
}

function isCurrent(
  operationRef: { current: number },
  operation: number,
  mountedRef: { current: boolean },
) {
  return operationRef.current === operation && mountedRef.current;
}
