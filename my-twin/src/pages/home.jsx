import React,{useEffect,useState} from "react";
import { Button, Dialog, DialogTitle, DialogContent, DialogActions } from "@mui/material";
import toast from "react-hot-toast";
import {Link} from "react-router-dom";
import Weather_cv from "./page_connect/Weather_cv";
import Calendar_g from "./page_connect/Calendar";
import Study from "./page_connect/Study";
import Outfit_of_day from "./page_connect/Outfit_of_day";
import {Anchor,MusicNote,
        Settings,CalendarMonth,Inventory2,Cloud,
        AttachFile,Code,ArrowUpwardTwoTone,CircleRounded,
        MicSharp,
        StopSharp,
        TurnSlightLeftTwoTone,
        AssistantDirection} from "@mui/icons-material";
import { ChatAPI, WeatherAPI } from "../Utils/Assistant";
import {useAuth} from "./AuthContext";
import SpeechRecognition, {
  useSpeechRecognition
} from "react-speech-recognition";
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
                        if (response.audio) {
                                const audio_res = new Audio("data:audio/mpeg;base64," + response.audio);
                                audio_res.play().catch((err) => console.warn("Audio playback failed:", err));
                        }
                        setAiReply(nextReply, source);
                        localStorage.setItem("AiReply", nextReply);
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
        if (transcript) {
            setQuestion(transcript);
        }
    }, [transcript]);

    useEffect(() => {
        setRecording(listening);
        if (listening) {
            setMicError("");
        }
    }, [listening]);

    useEffect(() => {
        if (isMicrophoneAvailable === false) {
            setMicError("Microphone access is blocked. Allow mic permission in your browser settings.");
        }
    }, [isMicrophoneAvailable]);

    const handleStartListening = async () => {
        setMicError("");
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

    const handleStopListening = () => {
        SpeechRecognition.stopListening();
                if (transcript) {
                        handleuserQuestionChange(transcript);
                }else{
                        toast.error("No speech detected. Please try again.");
                }
    };

    const handleResetTranscript = () => {
        resetTranscript();
        setQuestion("");
        setMicError("");
    };
    const minimize = () => {
        // Implement minimize functionality (e.g., hide the assistant, show a minimized icon, etc.)
        toast("Minimize feature coming soon!");
    };
// Keep this check after every hook call so the hook order never changes between renders
if (!browserSupportsSpeechRecognition) {
    return <p>Browser doesn't support speech recognition.</p>;
}
return (
    <main className="bg-background text-foreground backdrop-blur-md w-screen rounded-md border border-border h-screen overflow-none">
            <div className="glass h-[100px] w-full flex items-center justify-between font-bold text-xl p-5 text-left gap-4 rounded-md !overflow-auto">
                    <div className="flex items-center gap-2">
                      <Anchor
                      style={{ fontSize: '40px' }}
                       className="text-primary" />
                      <span className="text-muted-foreground text-sm items-center bg-card rounded-xl border border-border p-2 font-serif">{dateAndTime}</span>
                    </div>
                    <div className=" items-end gap-2">
                            <span className="text-primary text-lg font-bold">{userDetails}!</span>
                            {holidate && <span className="text-green-200 text-lg font-bold">{holidate}</span>}
                    </div>
            </div>
            <div className="flex flex-col md:flex-row h-[700px] w-full">
            <div className="h-auto rounded-md border border-sidebar-border m-3 bg-sidebar-background text-sidebar-foreground">
                    <ul className="block flex-col md:flex-row gap-5 text-lg font-bold ">
                             <li onClick={()=>setSection("weather")}><Cloud/></li>
                            <li className="mb-4"><Link to="/closet" className="font-bold text-sidebar-foreground"><Inventory2/></Link></li>
                            <li className="mb-4" onClick={()=>setSection("studier")}><Code/>Study</li>
                            <li><Link to="" className="font-bold text-sidebar-foreground"><MusicNote/>Music</Link></li>
                            <li onClick={()=>setSection("cal")} className="font-bold text-sidebar-foreground"><CalendarMonth/></li>
                            <li onClick={()=>setSection("oot")} className="font-bold text-sidebar-foreground" label="Outfit of the Day"><Inventory2/>Outfit of the Day</li>
                            <li>
                                {/*change to settings later on*/}
                                <Link to="/settings" className="font-bold text-sidebar-foreground"><Settings/>Settings</Link>
                            </li>
                    </ul>
                    <button onClick={minimize}>
                        <TurnSlightLeftTwoTone/>
                    </button>
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
            </div>
    </main>
);
}
export default Home;
