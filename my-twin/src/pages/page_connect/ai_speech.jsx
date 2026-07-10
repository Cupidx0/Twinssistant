import React, { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import toast from "react-hot-toast";
import SpeechRecognition, { useSpeechRecognition } from "react-speech-recognition";
import {
  Anchor,
  ArrowBack,
  ArrowUpward,
  ChatBubbleOutline,
  Close,
  GraphicEq,
  MicNone,
  MicOff,
  Stop,
} from "@mui/icons-material";
import { API_BASE_URL, ChatAPI } from "../../Utils/Assistant";
import { io } from "socket.io-client";

const WS_URL = import.meta.env.VITE_AI_SPEECH_WS_URL || "http://localhost:5000";
const AUTO_SEND_DELAY_MS = 1400;

const makeMessage = (role, text) => ({
  id: `${role}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
  role,
  text,
  ts: Date.now(),
});

function AiSpeech() {
  const {
    transcript,
    listening,
    resetTranscript,
    browserSupportsSpeechRecognition,
    isMicrophoneAvailable,
  } = useSpeechRecognition();

  const transcriptTimerRef = useRef(null);
  const transcriptEndRef = useRef(null);
  const socketRef = useRef(null);
  const [messages, setMessages] = useState([]);
  const [draftTranscript, setDraftTranscript] = useState("");
  const [reply, setReply] = useState("");
  const [connectionStatus, setConnectionStatus] = useState("Disconnected");
  const [micError, setMicError] = useState("");
  const [isPendingReply, setIsPendingReply] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [autoSpeak, setAutoSpeak] = useState(true);
  const [voices, setVoices] = useState([]);
  const [selectedVoice, setSelectedVoice] = useState("");
  const [speechRate, setSpeechRate] = useState(1);

  const vstate = listening ? "listening" : isPendingReply ? "thinking" : isSpeaking ? "speaking" : "idle";

  useEffect(() => {
    const loadVoices = () => {
      const availableVoices = window.speechSynthesis?.getVoices?.() ?? [];
      setVoices(availableVoices);
      if (!selectedVoice && availableVoices.length > 0) {
        const englishVoice =
          availableVoices.find((voice) => voice.lang?.startsWith("en-GB")) ||
          availableVoices.find((voice) => voice.lang?.startsWith("en")) ||
          availableVoices[0];
        setSelectedVoice(englishVoice.name);
      }
    };
    loadVoices();
    window.speechSynthesis?.addEventListener?.("voiceschanged", loadVoices);
    return () => {
      window.speechSynthesis?.removeEventListener?.("voiceschanged", loadVoices);
      window.speechSynthesis?.cancel?.();
    };
  }, [selectedVoice]);

  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, draftTranscript]);

  useEffect(() => {
    if (listening) setMicError("");
  }, [listening]);

  useEffect(() => {
    if (isMicrophoneAvailable === false) {
      setMicError("Microphone access is blocked. Allow microphone access in your browser.");
    }
  }, [isMicrophoneAvailable]);

  useEffect(() => {
    if (!transcript) return;
    setDraftTranscript(transcript);
    if (!listening || isPendingReply) return;

    clearTimeout(transcriptTimerRef.current);
    transcriptTimerRef.current = setTimeout(() => {
      const stabilizedText = transcript.trim();
      if (stabilizedText) void sendTurn(stabilizedText);
    }, AUTO_SEND_DELAY_MS);

    return () => clearTimeout(transcriptTimerRef.current);
  }, [transcript, listening, isPendingReply]);

  useEffect(() => {
    openSocket();
    return () => {
      clearTimeout(transcriptTimerRef.current);
      closeSocket();
    };
  }, []);

  const appendMessage = (role, text) => {
    if (!text?.trim()) return;
    setMessages((current) => [...current, makeMessage(role, text)]);
  };

  const speakReply = (text) => {
    if (!text.trim()) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    const voice = voices.find((v) => v.name === selectedVoice);
    if (voice) utterance.voice = voice;
    utterance.rate = speechRate;

    utterance.onstart = () => {
      setIsSpeaking(true);
      SpeechRecognition.stopListening();
    };
    utterance.onend = () => {
      setIsSpeaking(false);
      SpeechRecognition.startListening({ continuous: true, language: "en-GB" });
    };
    utterance.onerror = () => {
      setIsSpeaking(false);
      SpeechRecognition.startListening({ continuous: true, language: "en-GB" });
    };
    window.speechSynthesis.speak(utterance);
  };

  const stopSpeaking = () => {
    window.speechSynthesis?.cancel?.();
    setIsSpeaking(false);
  };

  const finalizeAssistantReply = (text) => {
    setReply(text);
    setIsPendingReply(false);
    appendMessage("assistant", text);
    if (autoSpeak) {
      SpeechRecognition.stopListening();
      speakReply(text);
    }
  };

  const openSocket = () => {
    closeSocket();
    setConnectionStatus("Connecting");
    socketRef.current = io(WS_URL || API_BASE_URL, {
      transports: ["websocket", "polling"],
    });
    socketRef.current.on("connect", () => setConnectionStatus("Connected"));
    socketRef.current.on("disconnect", () => setConnectionStatus("Disconnected"));
    socketRef.current.on("connect_error", () => setConnectionStatus("HTTP fallback"));
    socketRef.current.on("ai_response", (data) => {
      finalizeAssistantReply(data?.text || "No response from assistant.");
    });
  };

  const closeSocket = () => {
    socketRef.current?.disconnect();
    socketRef.current = null;
  };

  const sendViaHttp = async (text) => {
    const response = await ChatAPI.fetchAssistantResponse(text);
    finalizeAssistantReply(response.reply || "No response from assistant.");
  };

  const sendTurn = async (text) => {
    if (!text.trim() || isPendingReply) return;
    appendMessage("user", text);
    resetTranscript();
    setDraftTranscript("");
    setIsPendingReply(true);
    try {
      const socket = socketRef.current;
      if (socket?.connected) {
        socket.emit("voice_message", { text });
        return;
      }
      await sendViaHttp(text);
    } catch (error) {
      console.error("Failed to send assistant turn:", error);
      finalizeAssistantReply("Sorry, I could not get a reply right now.");
      toast.error("Assistant reply failed.");
    }
  };

  const handleStartListening = async () => {
    setMicError("");
    setDraftTranscript("");
    resetTranscript();
    stopSpeaking();
    try {
      await SpeechRecognition.startListening({ continuous: true, language: "en-GB" });
    } catch (error) {
      console.error("Failed to start speech recognition:", error);
      setMicError("Speech recognition could not start in this browser.");
    }
  };

  const handleEndTurn = async () => {
    SpeechRecognition.stopListening();
    const finalTranscript = (transcript || draftTranscript).trim();
    if (!finalTranscript) {
      toast.error("No speech detected. Try again.");
      return;
    }
    await sendTurn(finalTranscript);
  };

  const handleExitCleanup = () => {
    SpeechRecognition.stopListening();
    stopSpeaking();
    clearTimeout(transcriptTimerRef.current);
  };

  if (!browserSupportsSpeechRecognition) {
    return (
      <section className="glass m-6 rounded-3xl p-8 text-card-foreground">
        Browser speech recognition is not supported here.{" "}
        <Link to="/home" className="text-primary underline">Back to chat</Link>
      </section>
    );
  }

  const stateCaption = {
    idle: "Ready when you are",
    listening: "Listening",
    thinking: "Thinking",
    speaking: "Speaking",
  }[vstate];

  const stageText =
    vstate === "listening"
      ? draftTranscript || "Say something — I'm listening…"
      : vstate === "thinking"
        ? "Working on your reply…"
        : vstate === "speaking"
          ? reply
          : "Tap the orb or press start to begin a live conversation.";

  const stageHint = {
    idle: "Pauses end your turn automatically once we're rolling.",
    listening: "Pause to send · or press ↑ to end your turn now",
    thinking: "intent → context → compose",
    speaking: "Press stop to interrupt",
  }[vstate];

  return (
    <main className="grid h-screen w-screen grid-cols-[64px_minmax(0,1fr)] overflow-hidden bg-background text-foreground xl:grid-cols-[64px_minmax(0,1fr)_304px]">
      {/* ── Icon rail ── */}
      <aside className="flex flex-col items-center gap-1.5 border-r border-sidebar-border bg-sidebar-background py-3.5">
        <Link
          to="/home"
          onClick={handleExitCleanup}
          className="mb-3 grid h-[38px] w-[38px] place-items-center rounded-xl bg-gradient-primary text-primary-foreground shadow-glow"
          title="Twinssistant"
        >
          <Anchor sx={{ fontSize: 20 }} />
        </Link>
        <nav className="flex flex-1 flex-col gap-1.5">
          <Link
            to="/home"
            onClick={handleExitCleanup}
            title="Chat"
            className="grid h-[42px] w-[42px] place-items-center rounded-xl text-muted-foreground transition hover:bg-muted hover:text-foreground"
          >
            <ChatBubbleOutline sx={{ fontSize: 19 }} />
          </Link>
          <span
            title="Live voice"
            className="relative grid h-[42px] w-[42px] place-items-center rounded-xl bg-primary/15 text-primary-glow before:absolute before:-left-[11px] before:top-[11px] before:bottom-[11px] before:w-[3px] before:rounded before:bg-primary"
          >
            <GraphicEq sx={{ fontSize: 19 }} />
          </span>
        </nav>
      </aside>

      {/* ── Stage ── */}
      <section className="relative flex min-w-0 flex-col overflow-hidden">
        <div className="absolute left-0 right-0 top-0 z-10 flex items-center justify-between px-7 pt-6">
          <Link
            to="/home"
            onClick={handleExitCleanup}
            className="flex items-center gap-1.5 rounded-[10px] px-3 py-1.5 text-[13px] font-semibold text-muted-foreground transition hover:bg-muted hover:text-foreground"
          >
            <ArrowBack sx={{ fontSize: 14 }} /> Back to chat
          </Link>
          <span className="glass flex items-center gap-1.5 rounded-full px-3 py-1.5 font-mono text-[11.5px] text-muted-foreground">
            <span className={`pulse-dot h-[7px] w-[7px] rounded-full ${connectionStatus === "Connected" ? "bg-success" : "bg-warning"}`} />
            {connectionStatus}
          </span>
        </div>

        <div className="flex flex-1 flex-col items-center justify-center px-6 pt-10">
          <button
            onClick={vstate === "idle" ? handleStartListening : vstate === "listening" ? handleEndTurn : stopSpeaking}
            className="relative grid h-[300px] w-[300px] cursor-pointer place-items-center border-0 bg-transparent p-0"
            aria-label={vstate === "idle" ? "Start voice session" : "End turn"}
          >
            <span className={`ringwave ${vstate === "listening" ? "ripple-in" : vstate === "speaking" ? "ripple-out" : ""}`} />
            <span className={`ringwave ${vstate === "listening" ? "ripple-in ripple-d2" : vstate === "speaking" ? "ripple-out ripple-d2" : ""}`} />
            <span className={`ringwave ${vstate === "listening" ? "ripple-in ripple-d3" : vstate === "speaking" ? "ripple-out ripple-d3" : ""}`} />
            <span
              className={`orb block h-[190px] w-[190px] transition-transform duration-500 ${
                vstate === "idle" ? "orb-idle" : vstate === "listening" ? "orb-listening" : vstate === "thinking" ? "orb-thinking" : "orb-speaking"
              }`}
            />
          </button>

          <div className="mt-1.5 font-mono text-[11px] font-semibold uppercase tracking-[0.22em] text-primary-glow">
            {stateCaption}
          </div>
          <p className="mx-auto mb-0 mt-3.5 min-h-[64px] max-w-[560px] text-balance text-center text-[21px] font-medium leading-normal text-foreground/90">
            {vstate === "listening" && draftTranscript ? `"${draftTranscript}"` : stageText}
          </p>
          <p className="mt-2.5 text-[12.5px] text-muted-foreground">{stageHint}</p>

          {micError ? (
            <p className="mt-4 rounded-2xl border border-destructive/40 bg-destructive/10 px-4 py-2.5 text-sm text-destructive">
              {micError}
            </p>
          ) : null}
        </div>

        {/* Control pill */}
        <div className="flex flex-col items-center pb-6 pt-5">
          <div className="glass flex items-center gap-2 rounded-full p-2">
            <button
              onClick={listening ? () => SpeechRecognition.stopListening() : handleStartListening}
              title={listening ? "Mute microphone" : "Start microphone"}
              className={`grid h-[46px] w-[46px] place-items-center rounded-full border border-border transition hover:border-primary/40 hover:text-primary-glow ${
                listening ? "bg-secondary text-foreground" : "bg-secondary text-muted-foreground"
              }`}
            >
              {listening ? <MicNone sx={{ fontSize: 18 }} /> : <MicOff sx={{ fontSize: 18 }} />}
            </button>
            <button
              onClick={handleEndTurn}
              disabled={isPendingReply}
              title="End turn now"
              className="grid h-[58px] w-[58px] place-items-center rounded-full bg-primary text-primary-foreground transition hover:bg-primary-glow disabled:opacity-50"
            >
              <ArrowUpward sx={{ fontSize: 22 }} />
            </button>
            <button
              onClick={stopSpeaking}
              disabled={!isSpeaking}
              title="Stop voice"
              className="grid h-[46px] w-[46px] place-items-center rounded-full border border-border bg-secondary text-foreground transition hover:border-primary/40 hover:text-primary-glow disabled:opacity-40"
            >
              <Stop sx={{ fontSize: 17 }} />
            </button>
            <Link
              to="/home"
              onClick={handleExitCleanup}
              title="Exit voice mode"
              className="grid h-[46px] w-[46px] place-items-center rounded-full border border-border bg-secondary text-destructive transition hover:border-destructive/50"
            >
              <Close sx={{ fontSize: 17 }} />
            </Link>
          </div>
          <span className="mt-1.5 text-[11px] font-semibold text-muted-foreground">
            mic · end turn · stop voice · exit
          </span>
        </div>
      </section>

      {/* ── Transcript rail ── */}
      <aside className="hidden flex-col gap-3.5 overflow-hidden border-l border-border bg-background/40 p-5 pt-8 xl:flex">
        <div className="glass flex min-h-0 flex-1 flex-col rounded-2xl p-4">
          <div className="mb-2 flex items-center justify-between text-[11px] font-bold uppercase tracking-[0.14em] text-muted-foreground">
            Transcript
            <button
              onClick={() => setMessages([])}
              className="font-sans text-[11px] font-semibold normal-case tracking-normal text-primary"
            >
              Clear
            </button>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto">
            {messages.length === 0 && !draftTranscript ? (
              <p className="m-0 text-[12.5px] text-muted-foreground">Your conversation appears here as you talk.</p>
            ) : null}
            {messages.map((m) => (
              <div key={m.id} className="flex flex-col gap-1 border-t border-border py-2 first:border-t-0">
                <span className={`font-mono text-[9.5px] font-bold uppercase tracking-[0.16em] ${m.role === "user" ? "text-primary-glow" : "text-muted-foreground"}`}>
                  {m.role === "user" ? "You" : "Ashen"} · {new Date(m.ts).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" })}
                </span>
                <span className="text-[12.5px] leading-normal text-foreground/85">{m.text}</span>
              </div>
            ))}
            {draftTranscript ? (
              <div className="flex flex-col gap-1 border-t border-border py-2">
                <span className="font-mono text-[9.5px] font-bold uppercase tracking-[0.16em] text-primary-glow">You · now</span>
                <span className="blink-caret text-[12.5px] leading-normal text-foreground">{draftTranscript}</span>
              </div>
            ) : null}
            <div ref={transcriptEndRef} />
          </div>
        </div>

        <div className="glass rounded-2xl p-4">
          <div className="mb-2.5 text-[11px] font-bold uppercase tracking-[0.14em] text-muted-foreground">
            Voice settings
          </div>
          <div className="flex flex-col gap-2.5">
            <label className="flex items-center justify-between gap-2 text-[12.5px] text-foreground/85">
              Voice
              <select
                value={selectedVoice}
                onChange={(e) => setSelectedVoice(e.target.value)}
                className="max-w-[150px] rounded-lg border border-border bg-secondary px-2 py-1 text-[12px] text-foreground outline-none focus:border-primary"
              >
                {voices.length > 0 ? (
                  voices.map((voice) => (
                    <option key={`${voice.name}-${voice.lang}`} value={voice.name}>
                      {voice.name}
                    </option>
                  ))
                ) : (
                  <option value="">System default</option>
                )}
              </select>
            </label>
            <label className="flex items-center justify-between gap-2 text-[12.5px] text-foreground/85">
              Speed · {speechRate.toFixed(1)}×
              <input
                type="range"
                min="0.7"
                max="1.3"
                step="0.1"
                value={speechRate}
                onChange={(e) => setSpeechRate(Number(e.target.value))}
                className="w-[120px] accent-[hsl(24,88%,60%)]"
              />
            </label>
            <label className="flex items-center justify-between text-[12.5px] text-foreground/85">
              Auto-speak replies
              <input
                type="checkbox"
                checked={autoSpeak}
                onChange={(e) => setAutoSpeak(e.target.checked)}
                className="h-4 w-4 accent-[hsl(24,88%,60%)]"
              />
            </label>
          </div>
        </div>
      </aside>
    </main>
  );
}

export default AiSpeech;
