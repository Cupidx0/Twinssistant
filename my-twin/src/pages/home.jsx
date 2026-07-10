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

function Home () {
    const [dateAndTime, setDateAndTime] = useState(new Date().toLocaleString("en-GB",{fullDate:'long', hour:'2-digit', minute:'2-digit', second:'2-digit'}));
    const {user} = useAuth();
    const[usertime, setUsertime] = useState("");
    const[recording, setRecording] = useState(false);
    const[holidate, setHolidate] = useState(null);
    const [AiTasks, setAiTasks] = useState(() => readStoredValue("AiTasks", ""));
    const[AiReply, setAiReply] = useState(() => readStoredValue("AiReply", ""));
    const[AiSource, setAiSource] = useState(() => readStoredValue("AiSource", ""));
    const [question, setQuestion] = useState(() => readStoredValue("userQuestion", ""));
    const [openConfirm, setOpenConfirm] = useState(false);
    const[online, setOnline] = useState(navigator.onLine);
    const [section, setSection] = useState(() => readStoredValue("home:section", "weather"));
    const [micError, setMicError] = useState("");

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
        localStorage.setItem("home:section", section);
    }, [section]);

    const handleAiTasksChange = (e) => {
        setAiTasks(e.target.value);
        localStorage.setItem("AiTasks", e.target.value);
    };

    const handleuserQuestionChange = async (overrideQuestion) => {
        const nextQuestion = (overrideQuestion ?? question).trim();
        if(nextQuestion === ""){
                toast.error("Please enter a question.");
                return;
        }
        else{
                toast.success("Question sent to assistant!");
                try{
                        setQuestion(nextQuestion);
                        localStorage.setItem("userQuestion", nextQuestion);
                        const response = await ChatAPI.fetchAssistantResponse(nextQuestion);
                        const nextReply = response.reply || "No response from assistant.";
                        const source = response.source || "no source provided.";
                        console.log("source:", source);
                        if (response.audio) {
                                const audio_res = new Audio("data:audio/mpeg;base64," + response.audio);
                                audio_res.play().catch((err) => console.warn("Audio playback failed:", err));
                        }
                        setAiReply(nextReply);
                        setAiSource(source);
                        localStorage.setItem("AiReply", nextReply);
                        localStorage.setItem("AiSource", source);
                        if (nextReply.toLowerCase().includes("chat history is too long")) {
                                setOpenConfirm(true);
                        }
                }catch(error){
                        console.error("Error fetching assistant response:", error);
                        toast.error("Failed to get response from assistant.");
                }
        }
    };

    const handleConfirmClear = async () => {
                try{
                        const data = await ChatAPI.clearHistory("yes");
                        toast.success(data.reply || "Chat history cleared!");
                        localStorage.removeItem("AiReply");
                        localStorage.removeItem("userQuestion");
                } catch(error) {
                        toast.error("Failed to clear history");
                        console.error(error);
                }
                setOpenConfirm(false); // close dialog
        };
       const handleCancelClear = () => {
                toast("Chat history kept.");
                setOpenConfirm(false);
        };
const {
    transcript,
    listening,
    resetTranscript,
    browserSupportsSpeechRecognition,
    isMicrophoneAvailable
} = useSpeechRecognition();
const mail = user ? user.email.replace("@gmail.com","") : "";
const userDetails = user ? `${mail}` : "Not logged in";
const onlineStatus = user ? "Online" : "Offline";
   useEffect(() => {
        const interval = setInterval(() => {
            setDateAndTime(new Date().toLocaleString());
        }, 1000);
        return () => clearInterval(interval);
    }, []);
    useEffect(() => {
        const checkTime = ()=>{
                const hours = new Date().getHours();
                if (hours < 12){
                        setUsertime("Good morning");
                }else if (hours >= 12 && hours < 18){
                        setUsertime("Good afternoon");
                }else{
                        setUsertime("Good evening");
                }
        };
        checkTime();}, []);
        const fetchSeason = async ()=>{
                try{
                        const season = "a single word representing the current season/holiday (e.g., Christmas, Halloween, Summer, etc.) not a sentence, just the season name and if there isn't one,make sure to check the date to verify if the day is actually a holiday; use none if not a holiday or season.";
                        WeatherAPI.fetchSeason(season).then((season) => {
                                if (season.dreply === "none") {
                                        setHolidate("");
                                } else {
                                        setHolidate(`Happy ${season.dreply}!`);
                                }
                        });
                }catch(error){
                        console.error("Error fetching season:", error);
                        toast.error("Failed to fetch season");
                }
        };
        const happyNewMonthandYear =()=>{
                const date = new Date();
                if(date.getDate() <= 7){
                        toast("Happy new month!");
                        setHolidate("Happy new month!");
                        if(date.getMonth() === 0){
                                toast("Happy new year!");
                        }
                }
        };
    useEffect(() => {
        if (new Date().getDate() <= 2) {
                happyNewMonthandYear();
        }else{
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
            <div className="bg-card flex flex-col md:flex-row h-full w-full rounded-md !overflow-auto">
                 <section className=" h-auto w-[80%] p-2 rounded-md text-foreground border border-border !overflow-auto">
                        <section className="glass h-auto rounded-md p-2 bg-transparent content-start font-serif text-left text-card-foreground text-lg">
                                <span className="text-success"><CircleRounded style={
                                        {
                                                height:"10px",
                                                color: online ? "linear-gradient(135deg, #46e556 0%, #7d7d7da9 100%)" : "#ff0000",
                                                backgroundBlendMode:"difference",
                                                backdropFilter:"blur(10px)"
                                        }
                                }/> {onlineStatus}</span>
                            <h3 className="text-card-foreground text-lg font-bold m-0">{usertime},{userDetails}</h3>
                            <p>How can i help you today?</p>
                            <Link to="/speech">
                                <AssistantDirection className="text-primary text-lg font-bold"/>
                            </Link>
                        </section>
                            <div className="glass rounded-md p-2 mb-4 h-[300px] text-card-foreground text-lg overflow-auto border border-border">
                                <span className=" text-left font-bold m-3 overflow-auto">
                                    {AiReply ? AiReply :"no reply"}
                                    {AiSource && AiSource !== "no source provided." ? (
                                        <div className="text-muted-foreground text-left font-bold m-3">
                                            <p>Source:</p>
                                            <p className="flex flex-col rounded-md bg-secondary p-2 mb-4 max-h-[200px] text-card-foreground border border-border overflow-auto">{AiSource}</p>
                                        </div>
                                    ) : null}
                                </span>
                                    <h4 className="text-muted-foreground text-right font-bold">
                                        <div className="text-primary text-left font-bold m-3">You asked:</div>
                                        <p className="flex flex-col rounded-md bg-secondary p-2 mb-4 max-h-[200px] text-card-foreground border border-border overflow-auto">{question ? question : "ask me anything!"}</p>
                                    </h4>
                            </div>
                            <Dialog open={openConfirm} onClose={handleCancelClear}>
                                <DialogTitle>⚠️ Clear Chat History?</DialogTitle>
                                <DialogContent>
                                        Your chat history is very long. Do you want to clear it now?
                                </DialogContent>
                                <DialogActions>
                                        <Button onClick={handleCancelClear} color="secondary">No</Button>
                                        <Button onClick={handleConfirmClear} color="error" variant="contained">Yes, Clear</Button>
                                </DialogActions>
                            </Dialog>
                            <div className="glass mb-4 flex w-full max-w-full items-center gap-2 rounded-2xl p-2">
                                        <div className="rounded-xl bg-card text-primary shadow-soft transition hover:bg-secondary">
                                                <input type="file" className="hidden" id="file-upload" />
                                                <label
                                                  className="flex cursor-pointer items-center gap-2 px-3 py-2 text-sm font-semibold"
                                                  htmlFor="file-upload"
                                                >
                                                  <AttachFile fontSize="small" />
                                                  <span className="hidden sm:inline"></span>
                                                </label>
                                        </div>
                                <input className="min-w-0 flex-1 border-0 bg-transparent px-3 py-2 text-foreground outline-none focus:outline-none focus:ring-0"
                                        id="user-question"
                                        value={question}
                                        onChange={(e) => setQuestion(e.target.value)}
                                        onKeyDown={(e)=>{if(e.key === "Enter"){
                                                handleuserQuestionChange(question);
                                        }}}
                                        type="text" placeholder="Ask me anything..."
                                        />
                                        <div className="flex shrink-0 items-center content-between gap-2">
                                        <Button variant="contained"
                                                color="primary"
                                                size="small"
                                                onClick={() => handleuserQuestionChange(question)}
                                                style={{ minHeight:"36px", margin: 0 }}
                                                component="span"
                                                className="flex min-w-10 items-center justify-center rounded-xl border border-border/40 bg-primary px-3 text-primary-foreground shadow-soft"><ArrowUpwardTwoTone /></Button>
                                        </div>
                                </div>
                            <section className=" gap-4 mb-4">
                                <p>{recording ? "Listening..." : "Mic Off"}</p>
                                {micError ? <p className="text-red-500">{micError}</p> : null}

                                       { !recording? (<button
                                                onClick={handleStartListening}
                                        >
                                                <MicSharp/>
                                        </button> ): (<button
                                                onClick={handleStopListening}
                                        >
                                                <StopSharp/>
                                        </button>)}
                                        <button onClick={handleResetTranscript}>
                                                Clear
                                        </button>
                                    <Button variant="contained"
                                    color="primary"
                                    size="small"
                                    onClick={() => handleuserQuestionChange("Tailor my CV")}
                                    style={{ margin: '2px',padding: '2px' }}
                                    component="span"
                                    className="bg-success text-primary-foreground p-2 rounded-md m-2 border border-border/50">Tailor my CV</Button>
                                    <Button variant="contained"
                                    component="span"
                                    color="primary"
                                    size="small"
                                    onClick={()=> handleuserQuestionChange("Suggest an outfit")}
                                    style={{ margin: '2px',padding: '2px' }}
                                    className="bg-accent text-primary-foreground p-2 rounded-md m-2 border border-border/50">Suggest an outfit</Button>
                                    <Button variant="contained"
                                    component="span"
                                    color="primary"
                                    size="small"
                                    onClick={() => handleuserQuestionChange("Plan my day")}
                                    style={{ margin: '2px',padding: '2px' }}
                                    className="bg-primary text-primary-foreground p-2 rounded-md m-2 border border-border/50">Plan my day</Button>
                                    <Button
                                        size="small"
                                        variant="contained"
                                        color="primary"
                                        placeholder="Add a task..."
                                        onClick={() => handleuserQuestionChange(AiTasks || null)}
                                        style={{ margin: '2px',padding: '2px' }}
                                        className="w-[200px] bg-surface text-primary rounded-2xl shadow-soft border border-border/50 hover:bg-accent-indigo-light transition"
                                        >
                                        {AiTasks || "No tasks added yet"}
                                </Button>
                                <input
                                        className="w-[150px] rounded-md border border-border/50 bg-background text-primary placeholder-secondary p-2 mb-0 focus:outline-none focus:ring-2 focus:ring-accent-indigo"
                                        id="task-input"
                                        value={AiTasks}
                                        onChange={handleAiTasksChange}
                                        style={{ margin: '2px',padding: '2px' }}
                                        type="text"
                                        placeholder="New task..."
                                        />
                            </section>
                    </section>
                    <div className="bg-card md:flex-col md: h-full max-h-full w-[400px] text-card-foreground rounded-md m-2 !overflow-auto">
                {section === "weather" && <Weather_cv />}
                {section === "cal" && <Calendar_g />}
                {section === "oot" && <Outfit_of_day />}
                {section === "studier" && <Study />}
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
