import { useQuery } from "@tanstack/react-query";
import { AudioLines, Square } from "lucide-react";

import { getVoiceConfig } from "../../lib/api-client/voice";
import { useRealtimeVoice } from "./useRealtimeVoice";

export function VoiceCallControls({
  csrfToken,
  onTranscript,
}: {
  csrfToken: string;
  onTranscript: (transcript: string) => void;
}) {
  const config = useQuery({ queryKey: ["voice-config"], queryFn: getVoiceConfig, retry: false });
  const voice = useRealtimeVoice(csrfToken, onTranscript);
  const supported = typeof RTCPeerConnection !== "undefined" && Boolean(navigator.mediaDevices);
  if (!supported || !config.data?.enabled || !config.data.apiKeyConfigured) return null;

  return (
    <div className="voice-call">
      <button
        aria-describedby="voice-privacy-notice"
        aria-pressed={voice.isActive}
        className={
          voice.isActive ? "voice-call__button voice-call__button--active" : "voice-call__button"
        }
        disabled={voice.status === "stopping"}
        onClick={voice.isActive ? () => void voice.stop() : () => void voice.start()}
        type="button"
      >
        {voice.isActive ? (
          <Square aria-hidden="true" size={16} />
        ) : (
          <AudioLines aria-hidden="true" size={18} />
        )}
        {voice.status === "connecting"
          ? "Cancel voice"
          : voice.status === "stopping"
            ? "Stopping…"
            : voice.isActive
              ? "Stop voice"
              : "Talk with Istari"}
      </button>
      <small className="field-hint" id="voice-privacy-notice">
        Live audio is processed by OpenAI. Review the transcript before sending. Synthetic data
        only.
      </small>
      {voice.error ? (
        <small className="field-hint" role="alert">
          {voice.error}
        </small>
      ) : null}
    </div>
  );
}
