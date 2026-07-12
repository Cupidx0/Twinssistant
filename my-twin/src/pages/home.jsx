import React, { useEffect, useRef, useState } from "react";
import { Dialog, DialogTitle, DialogContent, DialogActions, Button } from "@mui/material";
import toast from "react-hot-toast";
import { Link } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import Weather_cv from "./page_connect/Weather_cv";
import Calendar_g from "./page_connect/Calendar";
import Study from "./page_connect/Study";
import Outfit_of_day from "./page_connect/Outfit_of_day";
import {
  Anchor,
  ChatBubbleOutline,
  Cloud,
  Checkroom,
  CalendarMonth,
  MenuBook,
  MusicNote,
  Settings as SettingsIcon,
  AttachFile,
  MicNone,
  StopCircleOutlined,
  GraphicEq,
  ArrowUpward,
  ContentCopy,
  VolumeUp,
  Replay,
  ArrowForward,
  Search,
  Description,
  Public,
  CheckCircleOutline,
  AutorenewOutlined,
} from "@mui/icons-material";
import { ChatAPI, WeatherAPI, CalendarAPI } from "../Utils/Assistant";
import { useAuth } from "./AuthContext";
import SpeechRecognition, { useSpeechRecognition } from "react-speech-recognition";
import "react-big-calendar/lib/css/react-big-calendar.css";

const readStoredValue = (key, fallback = "") => {
  try {
    const value = localStorage.getItem(key);
    return value ?? fallback;
  } catch (error) {
    console.warn(`Failed to read ${key} from localStorage`, error);
    return fallback;
  }
};

const readStoredThread = () => {
  try {
    const raw = localStorage.getItem("chatThread");
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
};

const makeMessage = (role, text, sources = []) => ({
  id: `${role}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
  role,
  text,
  sources,
  ts: Date.now(),
});

const quickActions = [
  { label: "Search the web", icon: <Search fontSize="inherit" />, prompt: "What's the latest tech news today?" },
  { label: "Tailor my CV", icon: <Description fontSize="inherit" />, prompt: "Tailor my CV" },
  { label: "Suggest an outfit", icon: <Checkroom fontSize="inherit" />, prompt: "Suggest an outfit" },
  { label: "Plan my day", icon: <CalendarMonth fontSize="inherit" />, prompt: "Plan my day" },
];

function SourceChips({ sources }) {
  if (!sources?.length) return null;
  return (
    <div className="mt-3">
      <div className="mb-2 flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-[0.14em] text-muted-foreground">
        <Public sx={{ fontSize: 13 }} /> Sources · {sources.length}
      </div>
      <div className="flex flex-wrap gap-2">
        {sources.map((s, i) => {
          let domain = "";
          try { domain = new URL(s.url).hostname.replace("www.", ""); } catch { domain = s.url; }
          return (
            <a
              key={`${s.url}-${i}`}
              href={s.url}
              target="_blank"
              rel="noreferrer"
              className="flex max-w-[230px] items-center gap-2 rounded-[10px] border border-border bg-card px-3 py-1.5 transition hover:border-primary/40 hover:bg-secondary"
            >
              <span className="grid h-[17px] w-[17px] shrink-0 place-items-center rounded-[5px] bg-primary/15 font-mono text-[10px] font-bold text-primary-glow">
                {i + 1}
              </span>
              <span className="flex min-w-0 flex-col">
                <span className="truncate text-xs font-semibold text-card-foreground">{s.title}</span>
                <span className="truncate font-mono text-[10.5px] text-muted-foreground">{domain}</span>
              </span>
            </a>
          );
        })}
      </div>
    </div>
  );
}

function ThinkingSteps() {
  return (
    <div className="mb-6">
      <div className="mb-2 flex items-center gap-2 font-mono text-[11px] uppercase tracking-[0.1em] text-muted-foreground">
        <span className="grid h-[18px] w-[18px] place-items-center rounded-md bg-gradient-primary text-primary-foreground">
          <GraphicEq sx={{ fontSize: 11 }} />
        </span>
        Working on it
      </div>
      <div className="flex flex-col">
        <div className="flex items-center gap-3 py-1.5 text-[13.5px] text-foreground/80">
          <CheckCircleOutline className="text-primary-glow" sx={{ fontSize: 18 }} />
          Understanding your request
        </div>
        <div className="flex items-center gap-3 py-1.5 text-[13.5px] font-semibold text-foreground">
          <AutorenewOutlined className="animate-spin text-primary" sx={{ fontSize: 18 }} />
          Gathering context &amp; composing…
        </div>
      </div>
      <div className="mt-4 space-y-2">
        <div className="h-3 w-full animate-pulse rounded-lg bg-muted" />
        <div className="h-3 w-4/5 animate-pulse rounded-lg bg-muted" />
        <div className="h-3 w-3/5 animate-pulse rounded-lg bg-muted" />
      </div>
    </div>
  );
}

function Home() {
  const { user } = useAuth();
  const [messages, setMessages] = useState(readStoredThread);
  const [pending, setPending] = useState(false);
  const [question, setQuestion] = useState(() => readStoredValue("userQuestion", ""));
  const [task, setTask] = useState(() => readStoredValue("AiTasks", ""));
  const [holidate, setHolidate] = useState(null);
  const [online, setOnline] = useState(navigator.onLine);
  const [section, setSection] = useState("chat");
  const [micError, setMicError] = useState("");
  const [openConfirm, setOpenConfirm] = useState(false);
  const [weather, setWeather] = useState(null);
  const [events, setEvents] = useState([]);
  const [now, setNow] = useState(new Date());
  const bottomRef = useRef(null);

  const {
    transcript,
    listening,
    resetTranscript,
    browserSupportsSpeechRecognition,
    isMicrophoneAvailable,
  } = useSpeechRecognition();

  const name = user?.displayName || (user?.email ? user.email.split("@")[0] : "there");
  const hours = now.getHours();
  const greeting = hours < 12 ? "Good morning" : hours < 18 ? "Good afternoon" : "Good evening";

  useEffect(() => {
    const goOnline = () => setOnline(true);
    const goOffline = () => setOnline(false);
    window.addEventListener("online", goOnline);
    window.addEventListener("offline", goOffline);
    return () => {
      window.removeEventListener("online", goOnline);
      window.removeEventListener("offline", goOffline);
    };
  }, []);

  useEffect(() => {
    const interval = setInterval(() => setNow(new Date()), 30000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem("chatThread", JSON.stringify(messages.slice(-40)));
    } catch (error) {
      console.warn("Failed to persist chat thread", error);
    }
  }, [messages]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, pending]);

  useEffect(() => {
    const fetchSeason = async () => {
      try {
        const season = "a single word representing the current season/holiday (e.g., Christmas, Halloween, Summer, etc.) not a sentence, just the season name and if there isn't one,make sure to check the date to verify if the day is actually a holiday; use none if not a holiday or season.";
        const res = await WeatherAPI.fetchSeason(season);
        setHolidate(res.dreply && res.dreply !== "none" ? `Happy ${res.dreply}!` : "");
      } catch (error) {
        console.error("Error fetching season:", error);
      }
    };
    if (new Date().getDate() <= 2) {
      setHolidate(new Date().getMonth() === 0 ? "Happy new year!" : "Happy new month!");
    } else {
      fetchSeason();
    }
  }, []);

  useEffect(() => {
    if (!user) return;
    WeatherAPI.fetchWeather()
      .then((d) => d.weather && setWeather(d.weather))
      .catch(() => setWeather(null));
    CalendarAPI.fetchEvents()
      .then((evs) => setEvents(Array.isArray(evs) ? evs.slice(0, 4) : []))
      .catch(() => setEvents([]));
  }, [user]);

  useEffect(() => {
    if (transcript) setQuestion(transcript);
  }, [transcript]);

  useEffect(() => {
    if (listening) setMicError("");
  }, [listening]);

  useEffect(() => {
    if (isMicrophoneAvailable === false) {
      setMicError("Microphone access is blocked. Allow mic permission in your browser settings.");
    }
  }, [isMicrophoneAvailable]);

  const handleSend = async (overrideQuestion) => {
    const text = (overrideQuestion ?? question).trim();
    if (!text) {
      toast.error("Please enter a question.");
      return;
    }
    if (pending) return;

    setMessages((current) => [...current, makeMessage("user", text)]);
    setQuestion("");
    localStorage.setItem("userQuestion", text);
    resetTranscript();
    setPending(true);
    try {
      const response = await ChatAPI.fetchAssistantResponse(text);
      const reply = response.reply || "No response from assistant.";
      const sources = Array.isArray(response.sources) ? response.sources : [];
      setMessages((current) => [...current, makeMessage("assistant", reply, sources)]);
      if (response.audio) {
        const audio = new Audio("data:audio/mpeg;base64," + response.audio);
        audio.play().catch((err) => console.warn("Audio playback failed:", err));
      }
      if (reply.toLowerCase().includes("chat history is too long")) {
        setOpenConfirm(true);
      }
    } catch (error) {
      console.error("Error fetching assistant response:", error);
      setMessages((current) => [
        ...current,
        makeMessage("assistant", "Sorry — I couldn't get a reply. Check that the backend is running and you're logged in."),
      ]);
      toast.error("Failed to get response from assistant.");
    } finally {
      setPending(false);
    }
  };

  const handleRetry = () => {
    const lastUser = [...messages].reverse().find((m) => m.role === "user");
    if (lastUser) handleSend(lastUser.text);
  };

  const handleSpeak = (text) => {
    try {
      window.speechSynthesis.cancel();
      window.speechSynthesis.speak(new SpeechSynthesisUtterance(text));
    } catch (error) {
      console.warn("Speech synthesis failed:", error);
    }
  };

  const handleCopy = (text) => {
    navigator.clipboard.writeText(text).then(
      () => toast.success("Copied"),
      () => toast.error("Copy failed"),
    );
  };

  const handleTaskChange = (e) => {
    const value = e.target.value;
    setTask(value);
    localStorage.setItem("AiTasks", value);
  };

  const handleAskAboutTask = () => {
    if (!task.trim()) return;
    handleSend(task);
  };

  const handleConfirmClear = async () => {
    try {
      const data = await ChatAPI.clearHistory("yes");
      toast.success(data.reply || "Chat history cleared!");
      setMessages([]);
      localStorage.removeItem("chatThread");
      localStorage.removeItem("userQuestion");
    } catch (error) {
      toast.error("Failed to clear history");
      console.error(error);
    }
    setOpenConfirm(false);
  };

  const handleMicToggle = async () => {
    if (listening) {
      SpeechRecognition.stopListening();
      const finalText = transcript.trim();
      if (finalText) handleSend(finalText);
      return;
    }
    setMicError("");
    try {
      await SpeechRecognition.startListening({ continuous: true, language: "en-GB" });
    } catch (error) {
      console.error("Failed to start speech recognition:", error);
      setMicError("Speech recognition could not start in this browser.");
    }
  };

  const railItems = [
    { key: "chat", label: "Chat", icon: <ChatBubbleOutline sx={{ fontSize: 19 }} /> },
    { key: "weather", label: "Weather & CV", icon: <Cloud sx={{ fontSize: 19 }} /> },
    { key: "oot", label: "Outfit of the day", icon: <Checkroom sx={{ fontSize: 19 }} /> },
    { key: "cal", label: "Calendar", icon: <CalendarMonth sx={{ fontSize: 19 }} /> },
    { key: "studier", label: "Study", icon: <MenuBook sx={{ fontSize: 19 }} /> },
    { key: "music", label: "Music — coming soon", icon: <MusicNote sx={{ fontSize: 19 }} />, disabled: true },
  ];

  const timeLabel = now.toLocaleString("en-GB", {
    weekday: "short", day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit",
  });

  return (
    <main className="grid h-screen w-screen grid-cols-[64px_minmax(0,1fr)] overflow-hidden bg-background text-foreground xl:grid-cols-[64px_minmax(0,1fr)_304px]">
      {/* ── Icon rail ── */}
      <aside className="flex flex-col items-center gap-1.5 border-r border-sidebar-border bg-sidebar-background py-3.5">
        <Link
          to="/home"
          onClick={() => setSection("chat")}
          className="mb-3 grid h-[38px] w-[38px] place-items-center rounded-xl bg-gradient-primary text-primary-foreground shadow-glow"
          title="Twinssistant"
        >
          <Anchor sx={{ fontSize: 20 }} />
        </Link>
        <nav className="flex flex-1 flex-col gap-1.5">
          {railItems.map((item) => (
            <button
              key={item.key}
              onClick={() => !item.disabled && setSection(item.key)}
              title={item.label}
              className={`relative grid h-[42px] w-[42px] place-items-center rounded-xl transition ${
                section === item.key
                  ? "bg-primary/15 text-primary-glow before:absolute before:-left-[11px] before:top-[11px] before:bottom-[11px] before:w-[3px] before:rounded before:bg-primary"
                  : item.disabled
                    ? "cursor-default text-muted-foreground/40"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground"
              }`}
            >
              {item.icon}
            </button>
          ))}
          <Link
            to="/speech"
            title="Live voice mode"
            className="grid h-[42px] w-[42px] place-items-center rounded-xl text-muted-foreground transition hover:bg-muted hover:text-foreground"
          >
            <GraphicEq sx={{ fontSize: 19 }} />
          </Link>
        </nav>
        <Link
          to="/settings"
          title="Settings"
          className="mb-2 grid h-[42px] w-[42px] place-items-center rounded-xl text-muted-foreground transition hover:bg-muted hover:text-foreground"
        >
          <SettingsIcon sx={{ fontSize: 19 }} />
        </Link>
        <div className="relative" title={user ? `${name} — online` : "Not logged in"}>
          <div className="grid h-9 w-9 place-items-center rounded-full border border-border bg-secondary text-[13px] font-bold text-primary-glow">
            {name.charAt(0).toUpperCase()}
          </div>
          <span
            className={`absolute -bottom-px -right-px h-[11px] w-[11px] rounded-full border-[2.5px] border-sidebar-background ${
              user && online ? "bg-success" : "bg-muted-foreground"
            }`}
          />
        </div>
      </aside>

      {/* ── Center ── */}
      {section === "chat" ? (
        <section className="flex min-w-0 flex-col overflow-hidden">
          <div className="flex flex-1 justify-center overflow-y-auto">
            <div className="flex w-full max-w-[720px] flex-col px-6 pb-6 pt-8">
              {/* Day header */}
              <div className="mb-6 flex items-center justify-between">
                <div className="flex flex-wrap items-baseline gap-2.5">
                  <h1 className="m-0 text-[15px] font-semibold text-muted-foreground">
                    {greeting}, <b className="text-foreground">{name}</b>
                  </h1>
                  {holidate ? (
                    <span className="rounded-full border border-warning/25 bg-warning/10 px-2.5 py-0.5 text-[11.5px] font-bold text-warning">
                      {holidate}
                    </span>
                  ) : null}
                </div>
                <time className="font-mono text-xs text-muted-foreground">{timeLabel}</time>
              </div>

              {micError ? (
                <p className="mb-3 rounded-xl border border-destructive/40 bg-destructive/10 px-4 py-2 text-sm text-destructive">
                  {micError}
                </p>
              ) : null}

              {/* Empty state */}
              {messages.length === 0 && !pending ? (
                <div className="mt-[10vh] text-center">
                  <h2 className="text-gradient m-0 mb-2.5 text-4xl font-semibold tracking-tight">
                    What can I do for you?
                  </h2>
                  <p className="m-0 mb-7 text-[15px] text-muted-foreground">
                    Ask anything — I can search the web, manage your calendar, and work on your CV.
                  </p>
                  <div className="flex flex-wrap justify-center gap-2.5">
                    {quickActions.map((qa) => (
                      <button
                        key={qa.label}
                        onClick={() => handleSend(qa.prompt)}
                        className="glass flex items-center gap-2 rounded-[14px] px-4 py-2.5 text-[13.5px] font-semibold text-foreground transition hover:-translate-y-px hover:border-primary/45"
                      >
                        <span className="text-[15px] text-primary">{qa.icon}</span>
                        {qa.label}
                      </button>
                    ))}
                  </div>
                </div>
              ) : null}

              {/* Thread */}
              {messages.map((m) =>
                m.role === "user" ? (
                  <div key={m.id} className="mb-4 mt-1.5 max-w-[78%] self-end">
                    <div className="rounded-2xl rounded-br-[4px] border border-primary/30 bg-primary/15 px-4 py-2.5 text-[14.5px] text-foreground">
                      {m.text}
                    </div>
                  </div>
                ) : (
                  <div key={m.id} className="mb-6">
                    <div className="mb-2 flex items-center gap-2 font-mono text-[11px] uppercase tracking-[0.1em] text-muted-foreground">
                      <span className="grid h-[18px] w-[18px] place-items-center rounded-md bg-gradient-primary text-primary-foreground">
                        <GraphicEq sx={{ fontSize: 11 }} />
                      </span>
                      Ashen{m.sources?.length ? " · web search" : ""}
                    </div>
                    <div className="markdown-body max-w-[65ch] text-[15px] leading-[1.7] text-foreground/90 [&_a]:text-primary-glow [&_a]:underline [&_code]:rounded [&_code]:bg-muted [&_code]:px-1 [&_code]:font-mono [&_code]:text-[13px] [&_pre]:overflow-x-auto [&_pre]:rounded-xl [&_pre]:border [&_pre]:border-border [&_pre]:bg-card [&_pre]:p-3 [&_p]:mb-3 [&_p]:mt-0 [&_ul]:my-2 [&_ul]:pl-5 [&_ol]:my-2 [&_ol]:pl-5">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.text || ""}</ReactMarkdown>
                    </div>
                    <SourceChips sources={m.sources} />
                    <div className="mt-2 flex gap-1">
                      <button onClick={() => handleCopy(m.text)} className="flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-semibold text-muted-foreground transition hover:bg-muted hover:text-foreground">
                        <ContentCopy sx={{ fontSize: 13 }} /> Copy
                      </button>
                      <button onClick={() => handleSpeak(m.text)} className="flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-semibold text-muted-foreground transition hover:bg-muted hover:text-foreground">
                        <VolumeUp sx={{ fontSize: 13 }} /> Speak
                      </button>
                      <button onClick={handleRetry} className="flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-semibold text-muted-foreground transition hover:bg-muted hover:text-foreground">
                        <Replay sx={{ fontSize: 13 }} /> Retry
                      </button>
                    </div>
                  </div>
                ),
              )}

              {pending ? <ThinkingSteps /> : null}
              <div ref={bottomRef} />
            </div>
          </div>

          {/* Input dock */}
          <div className="flex justify-center px-6 pb-4 pt-2">
            <div className="w-full max-w-[720px]">
              <div className="glass flex items-end gap-1.5 rounded-[18px] p-2 transition focus-within:border-primary/50 focus-within:shadow-glow">
                <button
                  onClick={() => setSection("weather")}
                  title="Upload a CV"
                  className="grid h-[38px] w-[38px] shrink-0 place-items-center rounded-xl text-muted-foreground transition hover:bg-muted hover:text-foreground"
                >
                  <AttachFile sx={{ fontSize: 17 }} />
                </button>
                <textarea
                  rows={1}
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      handleSend();
                    }
                  }}
                  placeholder={listening ? "Listening…" : "Ask anything…"}
                  aria-label="Message"
                  className="max-h-[130px] min-h-[24px] flex-1 resize-none border-0 bg-transparent px-1.5 py-2 text-[15px] text-foreground outline-none placeholder:text-muted-foreground"
                />
                {browserSupportsSpeechRecognition ? (
                  <button
                    onClick={handleMicToggle}
                    title={listening ? "Stop and send" : "Dictate"}
                    className={`grid h-[38px] w-[38px] shrink-0 place-items-center rounded-xl transition ${
                      listening ? "bg-destructive/20 text-destructive" : "text-muted-foreground hover:bg-muted hover:text-foreground"
                    }`}
                  >
                    {listening ? <StopCircleOutlined sx={{ fontSize: 17 }} /> : <MicNone sx={{ fontSize: 17 }} />}
                  </button>
                ) : null}
                <Link
                  to="/speech"
                  title="Live voice mode"
                  className="grid h-[38px] w-[38px] shrink-0 place-items-center rounded-xl border border-border text-muted-foreground transition hover:border-primary/40 hover:text-primary-glow"
                >
                  <GraphicEq sx={{ fontSize: 17 }} />
                </Link>
                <button
                  onClick={() => handleSend()}
                  disabled={pending}
                  title="Send"
                  className="grid h-[38px] w-[38px] shrink-0 place-items-center rounded-xl bg-primary text-primary-foreground transition hover:bg-primary-glow disabled:opacity-50"
                >
                  <ArrowUpward sx={{ fontSize: 16 }} />
                </button>
              </div>
              <div className="flex items-center justify-between px-2 pt-2 font-mono text-[11px] text-muted-foreground">
                <span className="flex items-center gap-1.5">
                  <span className={`pulse-dot h-1.5 w-1.5 rounded-full ${online ? "bg-success" : "bg-destructive"}`} />
                  {online ? "Connected" : "Offline"} · auto-routing Gemini / GPT / Claude
                </span>
                <span>⏎ send · ⇧⏎ newline</span>
              </div>
            </div>
          </div>
        </section>
      ) : (
        <section className="min-w-0 overflow-y-auto p-4 pt-6">
          {section === "weather" && <Weather_cv />}
          {section === "cal" && <Calendar_g />}
          {section === "oot" && <Outfit_of_day />}
          {section === "studier" && <Study />}
        </section>
      )}

      {/* ── Context rail ── */}
      <aside className="hidden flex-col gap-3.5 overflow-y-auto border-l border-border bg-background/40 p-5 pt-8 xl:flex">
        <div className="glass rounded-2xl p-4">
          <div className="mb-3 flex items-center justify-between text-[11px] font-bold uppercase tracking-[0.14em] text-muted-foreground">
            Weather
            <button onClick={() => setSection("weather")} className="font-sans text-[11px] font-semibold normal-case tracking-normal text-primary">
              Open
            </button>
          </div>
          {weather ? (
            <div className="flex items-center gap-3.5">
              <Cloud className="text-warning" sx={{ fontSize: 38 }} />
              <span className="text-[32px] font-semibold tracking-tight">{Math.round(weather.temperature)}°</span>
              <span className="text-[12.5px] leading-snug text-muted-foreground">
                <b className="block text-[13px] text-foreground">{weather.description}</b>
                {weather.city}
              </span>
            </div>
          ) : (
            <p className="m-0 text-[12.5px] text-muted-foreground">
              {user ? "Loading weather…" : "Log in to see your weather."}
            </p>
          )}
          <button
            onClick={() => handleSend("Suggest an outfit")}
            className="mt-3 flex w-full items-start gap-2 rounded-[10px] border border-primary/20 bg-primary/15 px-3 py-2 text-left text-[12.5px] leading-snug text-foreground/85 transition hover:border-primary/40"
          >
            <Checkroom className="mt-px shrink-0 text-primary" sx={{ fontSize: 14 }} />
            Ask me for today's outfit.
          </button>
        </div>

        <div className="glass rounded-2xl p-4">
          <div className="mb-2 flex items-center justify-between text-[11px] font-bold uppercase tracking-[0.14em] text-muted-foreground">
            Today
            <button onClick={() => setSection("cal")} className="font-sans text-[11px] font-semibold normal-case tracking-normal text-primary">
              Calendar
            </button>
          </div>
          {events.length > 0 ? (
            events.map((ev) => (
              <div key={ev.googleEventId || ev.id} className="flex items-start gap-2.5 border-t border-border py-2 first:border-t-0">
                <time className="whitespace-nowrap rounded-[7px] bg-primary/15 px-1.5 py-1 font-mono text-[11px] font-semibold text-primary-glow">
                  {ev.start && !Number.isNaN(new Date(ev.start).valueOf())
                    ? new Date(ev.start).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" })
                    : "—"}
                </time>
                <div>
                  <div className="text-[13px] font-semibold leading-snug">{ev.summary || "No title"}</div>
                  <div className="mt-0.5 text-[11px] text-muted-foreground">{ev.duration || ""}</div>
                </div>
              </div>
            ))
          ) : (
            <p className="m-0 text-[12.5px] text-muted-foreground">
              {user ? "Nothing scheduled — ask me to add an event." : "Log in to see your calendar."}
            </p>
          )}
        </div>

        <div className="glass rounded-2xl p-4">
          <div className="mb-2 flex items-center justify-between text-[11px] font-bold uppercase tracking-[0.14em] text-muted-foreground">
            Quick task
          </div>
          <input
            value={task}
            onChange={handleTaskChange}
            placeholder="Jot a task…"
            className="w-full rounded-[10px] border border-border bg-secondary px-3 py-2 text-[12.5px] text-foreground outline-none placeholder:text-muted-foreground focus:border-primary/40"
          />
          <button
            onClick={handleAskAboutTask}
            disabled={!task.trim()}
            className="mt-2 w-full rounded-[10px] bg-primary py-2 text-xs font-semibold text-primary-foreground transition hover:bg-primary-glow disabled:opacity-50"
          >
            Ask Ashen about this
          </button>
        </div>

        <div className="glass rounded-2xl p-4">
          <div className="mb-2 flex items-center justify-between text-[11px] font-bold uppercase tracking-[0.14em] text-muted-foreground">
            CV toolkit
            <button onClick={() => setSection("weather")} className="font-sans text-[11px] font-semibold normal-case tracking-normal text-primary">
              Open
            </button>
          </div>
          <p className="m-0 text-[12.5px] leading-snug text-muted-foreground">
            Upload a CV, get a scored review, and download a rewrite tailored to a role.
          </p>
          <div className="mt-3 flex gap-2">
            <button
              onClick={() => handleSend("Review my CV")}
              className="flex-1 rounded-[10px] border border-border bg-secondary py-2 text-xs font-semibold text-foreground transition hover:brightness-110"
            >
              Review
            </button>
            <button
              onClick={() => setSection("weather")}
              className="flex-1 rounded-[10px] bg-primary py-2 text-xs font-semibold text-primary-foreground transition hover:bg-primary-glow"
            >
              Rewrite
            </button>
          </div>
        </div>
      </aside>

      <Dialog open={openConfirm} onClose={() => setOpenConfirm(false)}>
        <DialogTitle>Clear chat history?</DialogTitle>
        <DialogContent>Your chat history is getting long. Clearing it keeps replies fast.</DialogContent>
        <DialogActions>
          <Button onClick={() => setOpenConfirm(false)} color="secondary">Keep it</Button>
          <Button onClick={handleConfirmClear} color="error" variant="contained">Clear history</Button>
        </DialogActions>
      </Dialog>
    </main>
  );
}

export default Home;
