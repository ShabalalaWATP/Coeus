import { useCallback, useEffect, useRef, useState } from "react";

// Minimal typings for the browser Web Speech API, which is not part of the
// standard TypeScript DOM lib. Only the members used here are declared.
type SpeechRecognitionResultLike = {
  0: { transcript: string };
  isFinal: boolean;
};

type SpeechRecognitionEventLike = {
  resultIndex: number;
  results: ArrayLike<SpeechRecognitionResultLike>;
};

type SpeechRecognitionLike = {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onend: (() => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  start: () => void;
  stop: () => void;
};

type SpeechRecognitionConstructor = new () => SpeechRecognitionLike;

function recognitionConstructor(): SpeechRecognitionConstructor | null {
  const scope = window as typeof window & {
    SpeechRecognition?: SpeechRecognitionConstructor;
    webkitSpeechRecognition?: SpeechRecognitionConstructor;
  };
  return scope.SpeechRecognition ?? scope.webkitSpeechRecognition ?? null;
}

export function useSpeechToText(onTranscript: (transcript: string) => void) {
  const [isListening, setIsListening] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const onTranscriptRef = useRef(onTranscript);
  onTranscriptRef.current = onTranscript;

  const isSupported = recognitionConstructor() !== null;

  const stop = useCallback(() => {
    recognitionRef.current?.stop();
  }, []);

  const start = useCallback(() => {
    const RecognitionCtor = recognitionConstructor();
    if (RecognitionCtor === null || recognitionRef.current !== null) {
      return;
    }
    setError(null);
    const recognition = new RecognitionCtor();
    recognition.lang = document.documentElement.lang || "en-GB";
    recognition.continuous = true;
    // Only final results are surfaced, so dictated text lands once, cleanly.
    recognition.interimResults = false;
    recognition.onresult = (event) => {
      for (let index = event.resultIndex; index < event.results.length; index += 1) {
        const result = event.results[index];
        if (result.isFinal) {
          onTranscriptRef.current(result[0].transcript);
        }
      }
    };
    recognition.onerror = (event) => {
      setError(
        event.error === "not-allowed"
          ? "Microphone access was blocked. Allow it in the browser to dictate."
          : "Voice input stopped unexpectedly. Try again or type instead.",
      );
    };
    recognition.onend = () => {
      recognitionRef.current = null;
      setIsListening(false);
    };
    recognitionRef.current = recognition;
    recognition.start();
    setIsListening(true);
  }, []);

  useEffect(() => stop, [stop]);

  return { error, isListening, isSupported, start, stop };
}
