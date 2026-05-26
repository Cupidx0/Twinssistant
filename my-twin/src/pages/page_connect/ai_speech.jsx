import React, { useEffect, useRef, useState } from "react";
import toast from "react-hot-toast";
import SpeechRecognition, {
  useSpeechRecognition,
} from "react-speech-recognition";
import {
  GraphicEq,
  Link,
  LinkOff,
  Mic,
  PauseCircle,
  Radio,
  Refresh,
  SettingsVoice,
  Stop,
  VolumeUp,
  WifiTethering,
} from "@mui/icons-material";
import { API_BASE_URL, ChatAPI } from "../../Utils/Assistant";
import { io } from "socket.io-client"
const WS_URL = import.meta.env.VITE_AI_SPEECH_WS_URL || "";
const AUTO_SEND_DELAY_MS = 1400;

const quickPrompts = [
  "Start a mock interview with me",
  "Coach me through a coding problem",
  "Review my CV for an internship role",
];

const makeMessage = (role, text, status = "final") => ({
  id: `${role}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
  role,
  text,
  status,
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
  const conversationEndRef = useRef(null);
  const socketRef = useRef(null)
  const [messages, setMessages] = useState([
    makeMessage(
      "assistant",
      "Live voice mode is ready. Start the microphone and I will treat pauses like turn endings.",
    ),
  ]);
  const [draftTranscript, setDraftTranscript] = useState("");
  const [reply, setReply] = useState("");
  const [status, setStatus] = useState("Idle");
  const [connectionStatus, setConnectionStatus] = useState(WS_URL ? "Disconnected" : "HTTP Fallback");
  const [micError, setMicError] = useState("");
  const [isPendingReply, setIsPendingReply] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [autoSpeak, setAutoSpeak] = useState(true);
  const [voices, setVoices] = useState([]);
  const [selectedVoice, setSelectedVoice] = useState("");
  const [speechRate, setSpeechRate] = useState(1);

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
    if (conversationEndRef.current) {
      conversationEndRef.current.scrollIntoView({ behavior: "smooth", block: "end" });
    }
  }, [messages, draftTranscript]);

  useEffect(() => {
    setStatus(listening ? "Listening" : isPendingReply ? "Thinking" : isSpeaking ? "Speaking" : "Idle");
    if (listening) {
      setMicError("");
    }
  }, [listening, isPendingReply, isSpeaking]);

  useEffect(() => {
    if (isMicrophoneAvailable === false) {
      setMicError("Microphone access is blocked. Allow microphone access in your browser.");
    }
  }, [isMicrophoneAvailable]);

  useEffect(() => {
    if (!transcript) {
      return;
    }

    setDraftTranscript(transcript);

    if (!listening || isPendingReply) {
      return;
    }

    clearTimeout(transcriptTimerRef.current);
    transcriptTimerRef.current = setTimeout(() => {
      const stabilizedText = transcript.trim();
      if (stabilizedText) {
        void sendTurn(stabilizedText);
      }
    }, AUTO_SEND_DELAY_MS);

    return () => clearTimeout(transcriptTimerRef.current);
  }, [transcript, listening, isPendingReply]);

  useEffect(() => () => {
    clearTimeout(transcriptTimerRef.current);
    socketRef.current?.close?.();
  }, []);

  const appendMessage = (role, text, messageStatus = "final") => {
    if (!text?.trim()) {
      return;
    }
    setMessages((current) => [...current, makeMessage(role, text, messageStatus)]);
  };

  const replacePendingAssistantMessage = (text, messageStatus = "streaming") => {
    setMessages((current) => {
      const next = [...current];
      const lastMessage = next[next.length - 1];

      if (lastMessage?.role === "assistant" && lastMessage.status === "streaming") {
        next[next.length - 1] = {
          ...lastMessage,
          text,
          status: messageStatus,
        };
        return next;
      }

      next.push(makeMessage("assistant", text, messageStatus));
      return next;
    });
  };

  const speakReply = (text) => {
      if (!text.trim()) return

      window.speechSynthesis.cancel()
      const utterance = new SpeechSynthesisUtterance(text)
      
      utterance.onstart = () => {
          setIsSpeaking(true)
          SpeechRecognition.stopListening() // make sure mic is off
      }
      utterance.onend = () => {
          setIsSpeaking(false)
          // resume listening after AI finishes
          SpeechRecognition.startListening({ continuous: true, language: "en-GB" })
      }
      utterance.onerror = () => {
          setIsSpeaking(false)
          SpeechRecognition.startListening({ continuous: true, language: "en-GB" })
      }

      window.speechSynthesis.speak(utterance)
  }

  const stopSpeaking = () => {
    window.speechSynthesis?.cancel?.();
    setIsSpeaking(false);
  };

  const finalizeAssistantReply = (text) => {
    setReply(text);
    setIsPendingReply(false);
    setStatus("Replied");
    replacePendingAssistantMessage(text, "final");

    if (autoSpeak) {
        // stop listening before speaking
        SpeechRecognition.stopListening()
        speakReply(text)
    }
  };
  useEffect(() => {
    if (!WS_URL) {
      return undefined;
    }

    openSocket();
    return () => closeSocket();
  }, []);

  const openSocket = () => {
    const socketUrl = WS_URL || API_BASE_URL;
    closeSocket();
    setConnectionStatus("Connecting");

    socketRef.current = io(socketUrl, {
      transports: ["websocket", "polling"],
    });

    socketRef.current.on("connect", () => setConnectionStatus("Connected"));
    socketRef.current.on("disconnect", () =>
      setConnectionStatus(WS_URL ? "Disconnected" : "HTTP Fallback"),
    );
    socketRef.current.on("connect_error", () =>
      setConnectionStatus(WS_URL ? "Error" : "HTTP Fallback"),
    );

    socketRef.current.on("ai_response", (data) => {
      finalizeAssistantReply(data?.text || "No response from assistant.");
    });
  };

  const closeSocket = () => {
    socketRef.current?.disconnect();
    socketRef.current = null;
    setConnectionStatus(WS_URL ? "Disconnected" : "HTTP Fallback");
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
    try {
      await SpeechRecognition.startListening({
        continuous: true,
        language: "en-GB",
      });
    } catch (error) {
      console.error("Failed to start speech recognition:", error);
      setMicError("Speech recognition could not start in this browser.");
    }
  };

  const handleStopListening = async () => {
    SpeechRecognition.stopListening();
    const finalTranscript = (transcript || draftTranscript).trim();
    if (!finalTranscript) {
      toast.error("No speech detected. Try again.");
      return;
    }
    await sendTurn(finalTranscript);
  };

  const handleReset = () => {
    SpeechRecognition.stopListening();
    stopSpeaking();
    clearTimeout(transcriptTimerRef.current);
    resetTranscript();
    setDraftTranscript("");
    setReply("");
    setIsPendingReply(false);
    setStatus("Idle");
    setMicError("");
    setMessages([
      makeMessage(
        "assistant",
        "Live voice mode is ready. Start the microphone and I will treat pauses like turn endings.",
      ),
    ]);
  };

  const handleQuickPrompt = async (prompt) => {
    await sendTurn(prompt);
  };

  if (!browserSupportsSpeechRecognition) {
    return (
      <section className="m-6 rounded-3xl border border-border bg-card p-8 text-card-foreground shadow-soft">
        Browser speech recognition is not supported here.
      </section>
    );
  }

  const hasSocket = Boolean(WS_URL);

  return (
    <div className="min-h-screen bg-background px-4 py-6 text-foreground sm:px-6 lg:px-8">
      <section className="mx-auto flex w-full max-w-7xl flex-col gap-6">
        <div className="glass-strong overflow-hidden rounded-[32px] border border-border bg-gradient-aurora p-6 sm:p-8">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl">
              <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-border bg-card/70 px-4 py-2 text-sm font-semibold text-card-foreground">
                <GraphicEq className="text-primary" fontSize="small" />
                Realtime Conversation Interface
              </div>
              <h1 className="text-3xl font-semibold tracking-tight sm:text-5xl">
                Continuous voice turns, connection state, and streamed replies.
              </h1>
              <p className="mt-3 max-w-2xl text-sm text-muted-foreground sm:text-base">
                This interface behaves like a websocket conversation client. It auto-sends on a pause in speech,
                keeps a running thread, and can switch to a real socket session when a backend endpoint is available.
              </p>
            </div>

            <div className="grid grid-cols-2 gap-3 text-center text-sm md:grid-cols-4">
              <div className="rounded-2xl border border-border bg-card/70 px-4 py-3">
                <p className="text-muted-foreground">Connection</p>
                <p className="mt-1 font-semibold text-card-foreground">{connectionStatus}</p>
              </div>
              <div className="rounded-2xl border border-border bg-card/70 px-4 py-3">
                <p className="text-muted-foreground">Mic</p>
                <p className="mt-1 font-semibold text-card-foreground">{listening ? "Hot" : "Standby"}</p>
              </div>
              <div className="rounded-2xl border border-border bg-card/70 px-4 py-3">
                <p className="text-muted-foreground">Assistant</p>
                <p className="mt-1 font-semibold text-card-foreground">{isPendingReply ? "Thinking" : "Ready"}</p>
              </div>
              <div className="rounded-2xl border border-border bg-card/70 px-4 py-3">
                <p className="text-muted-foreground">Voice</p>
                <p className="mt-1 font-semibold text-card-foreground">{isSpeaking ? "Playing" : "Ready"}</p>
              </div>
            </div>
          </div>
        </div>

        <div className="grid gap-6 xl:grid-cols-[1.45fr_0.85fr]">
          <div className="flex flex-col gap-6">
            <section className="glass rounded-[28px] border border-border p-5 sm:p-6">
              <div className="flex flex-col gap-5">
                <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                  <div>
                    <h2 className="text-xl font-semibold text-card-foreground">Voice Session</h2>
                    <p className="text-sm text-muted-foreground">
                      The interface listens continuously and treats a pause as the end of a user turn.
                    </p>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <button
                      onClick={openSocket}
                      disabled={!hasSocket || connectionStatus === "Connected" || connectionStatus === "Connecting"}
                      className="flex h-11 items-center gap-2 rounded-2xl bg-primary px-4 text-sm font-semibold text-primary-foreground disabled:opacity-50"
                    >
                      <Link fontSize="small" />
                      Connect
                    </button>
                    <button
                      onClick={closeSocket}
                      disabled={!hasSocket || connectionStatus !== "Connected"}
                      className="flex h-11 items-center gap-2 rounded-2xl border border-border bg-card px-4 text-sm font-semibold text-card-foreground disabled:opacity-50"
                    >
                      <LinkOff fontSize="small" />
                      Disconnect
                    </button>
                  </div>
                </div>

                <div className="rounded-[24px] border border-border bg-card p-5">
                  <div className="mb-5 flex items-end justify-center gap-2">
                    {Array.from({ length: 20 }).map((_, index) => (
                      <span
                        key={index}
                        className={`w-2 rounded-full transition-all duration-300 ${
                          listening
                            ? index % 4 === 0
                              ? "h-16 bg-primary"
                              : index % 2 === 0
                                ? "h-11 bg-accent"
                                : "h-6 bg-secondary"
                            : isPendingReply
                              ? index % 3 === 0
                                ? "h-12 bg-accent"
                                : "h-7 bg-primary"
                              : isSpeaking
                                ? "h-9 bg-primary"
                                : "h-4 bg-border"
                        }`}
                      />
                    ))}
                  </div>

                  <div className="flex flex-wrap items-center justify-center gap-3">
                    {!listening ? (
                      <button
                        onClick={handleStartListening}
                        className="flex h-14 min-w-[170px] items-center justify-center gap-2 rounded-2xl bg-primary px-5 text-sm font-semibold text-primary-foreground shadow-soft transition hover:opacity-95"
                      >
                        <Mic />
                        Start Session Mic
                      </button>
                    ) : (
                      <button
                        onClick={handleStopListening}
                        className="flex h-14 min-w-[170px] items-center justify-center gap-2 rounded-2xl bg-destructive px-5 text-sm font-semibold text-white shadow-soft transition hover:opacity-95"
                      >
                        <Stop />
                        End Turn Now
                      </button>
                    )}

                    <button
                      onClick={handleReset}
                      className="flex h-14 min-w-[130px] items-center justify-center gap-2 rounded-2xl border border-border bg-card px-5 text-sm font-semibold text-card-foreground transition hover:bg-secondary"
                    >
                      <Refresh />
                      Reset
                    </button>

                    <button
                      onClick={() => speakReply(reply)}
                      disabled={!reply}
                      className="flex h-14 min-w-[130px] items-center justify-center gap-2 rounded-2xl border border-border bg-card px-5 text-sm font-semibold text-card-foreground transition hover:bg-secondary disabled:opacity-50"
                    >
                      <VolumeUp />
                      Replay
                    </button>

                    <button
                      onClick={stopSpeaking}
                      disabled={!isSpeaking}
                      className="flex h-14 min-w-[130px] items-center justify-center gap-2 rounded-2xl border border-border bg-card px-5 text-sm font-semibold text-card-foreground transition hover:bg-secondary disabled:opacity-50"
                    >
                      <PauseCircle />
                      Stop Voice
                    </button>
                  </div>

                  {micError ? (
                    <p className="mt-4 rounded-2xl border border-red-400/40 bg-red-500/10 px-4 py-3 text-sm text-red-300">
                      {micError}
                    </p>
                  ) : null}
                </div>

                <div className="grid gap-4 lg:grid-cols-[0.9fr_1.1fr]">
                  <div className="rounded-[24px] border border-border bg-card p-5">
                    <p className="mb-2 text-xs font-semibold uppercase tracking-[0.18em] text-primary">
                      Live Transcript
                    </p>
                    <p className="min-h-[180px] whitespace-pre-wrap text-sm text-card-foreground">
                      {draftTranscript || "Your current turn appears here while you are speaking."}
                    </p>
                    <p className="mt-4 text-xs text-muted-foreground">
                      Auto-send delay: {(AUTO_SEND_DELAY_MS / 1000).toFixed(1)}s after speech pauses.
                    </p>
                  </div>

                  <div className="rounded-[24px] border border-border bg-card p-5">
                    <p className="mb-2 text-xs font-semibold uppercase tracking-[0.18em] text-primary">
                      Conversation Thread
                    </p>
                    <div className="flex max-h-[360px] flex-col gap-3 overflow-auto pr-2">
                      {messages.map((message) => (
                        <div
                          key={message.id}
                          className={`rounded-2xl px-4 py-3 text-sm ${
                            message.role === "user"
                              ? "ml-auto max-w-[85%] bg-primary text-primary-foreground"
                              : "mr-auto max-w-[90%] border border-border bg-background text-card-foreground"
                          }`}
                        >
                          <p className="mb-1 text-[11px] uppercase tracking-[0.18em] opacity-70">
                            {message.role === "user" ? "You" : "Assistant"}
                          </p>
                          <p className="whitespace-pre-wrap">{message.text}</p>
                        </div>
                      ))}
                      <div ref={conversationEndRef} />
                    </div>
                  </div>
                </div>
              </div>
            </section>

            <section className="glass rounded-[28px] border border-border p-5 sm:p-6">
              <h2 className="text-xl font-semibold text-card-foreground">Quick Starts</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                These drop directly into the conversation thread without a manual send step.
              </p>
              <div className="mt-4 grid gap-3 md:grid-cols-3">
                {quickPrompts.map((prompt) => (
                  <button
                    key={prompt}
                    onClick={() => void handleQuickPrompt(prompt)}
                    className="rounded-2xl border border-border bg-card px-4 py-4 text-left text-sm font-medium text-card-foreground transition hover:-translate-y-0.5 hover:bg-secondary"
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            </section>
          </div>

          <aside className="flex flex-col gap-6">
            <section className="glass rounded-[28px] border border-border p-5 sm:p-6">
              <div className="mb-4 flex items-center gap-2">
                <SettingsVoice className="text-primary" />
                <h2 className="text-xl font-semibold text-card-foreground">Realtime Settings</h2>
              </div>

              <div className="space-y-4">
                <div className="rounded-2xl border border-border bg-card px-4 py-4">
                  <p className="text-sm font-medium text-card-foreground">Transport</p>
                  <p className="mt-1 text-sm text-muted-foreground">
                    {hasSocket
                      ? `WebSocket enabled via ${WS_URL}`
                      : "No websocket URL is configured, so turns fall back to the existing HTTP chat endpoint."}
                  </p>
                </div>

                <label className="block">
                  <span className="mb-2 block text-sm font-medium text-card-foreground">Playback voice</span>
                  <select
                    value={selectedVoice}
                    onChange={(event) => setSelectedVoice(event.target.value)}
                    className="w-full rounded-2xl border border-border bg-card px-4 py-3 text-sm text-card-foreground outline-none transition focus:border-primary"
                  >
                    {voices.length > 0 ? (
                      voices.map((voice) => (
                        <option key={`${voice.name}-${voice.lang}`} value={voice.name}>
                          {voice.name} ({voice.lang})
                        </option>
                      ))
                    ) : (
                      <option value="">System default voice</option>
                    )}
                  </select>
                </label>

                <label className="block">
                  <span className="mb-2 block text-sm font-medium text-card-foreground">
                    Speech rate: {speechRate.toFixed(1)}x
                  </span>
                  <input
                    type="range"
                    min="0.7"
                    max="1.3"
                    step="0.1"
                    value={speechRate}
                    onChange={(event) => setSpeechRate(Number(event.target.value))}
                    className="w-full accent-[var(--color-primary)]"
                  />
                </label>

                <label className="flex items-center justify-between rounded-2xl border border-border bg-card px-4 py-3">
                  <span className="text-sm font-medium text-card-foreground">Auto speak assistant replies</span>
                  <input
                    type="checkbox"
                    checked={autoSpeak}
                    onChange={(event) => setAutoSpeak(event.target.checked)}
                    className="h-4 w-4 accent-[var(--color-primary)]"
                  />
                </label>
              </div>
            </section>

            <section className="glass rounded-[28px] border border-border p-5 sm:p-6">
              <h2 className="text-xl font-semibold text-card-foreground">Session States</h2>
              <div className="mt-4 space-y-3">
                <div className="flex items-start gap-3 rounded-2xl border border-border bg-card px-4 py-4 text-sm text-card-foreground">
                  <WifiTethering className="mt-0.5 text-primary" fontSize="small" />
                  <span>Connect the page to a future websocket endpoint with `VITE_AI_SPEECH_WS_URL`.</span>
                </div>
                <div className="flex items-start gap-3 rounded-2xl border border-border bg-card px-4 py-4 text-sm text-card-foreground">
                  <Radio className="mt-0.5 text-primary" fontSize="small" />
                  <span>Speech pauses trigger automatic turn submission, so the user does not need to press send.</span>
                </div>
                <div className="flex items-start gap-3 rounded-2xl border border-border bg-card px-4 py-4 text-sm text-card-foreground">
                  <Mic className="mt-0.5 text-primary" fontSize="small" />
                  <span>Manual `End Turn Now` is still available for faster interruptions and tighter control.</span>
                </div>
              </div>
            </section>
          </aside>
        </div>
      </section>
    </div>
  );
}

export default AiSpeech;
