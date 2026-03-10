import React,{use, useEffect,useState} from "react";
import {Card, CardContent, Typography,
  Button, TextField, Stack, Divider} from "@mui/material";
import toast, { Toaster } from "react-hot-toast";
import {Link} from "react-router-dom";
/* Updated upstream*/
import {Anchor,Delete,SmartToy,
        Upload,Work,Code} from "@mui/icons-material";  
import { fetchAssistantResponse } from "../Utils/Assistant";
import {useAuth} from "./AuthContext";
import { Calendar, dateFnsLocalizer } from "react-big-calendar";
import { format, parse, startOfWeek, getDay, set } from "date-fns";
import "react-big-calendar/lib/css/react-big-calendar.css";
import Linkify from 'react-linkify';
//import {store,db} from "../Utils/Firebase";
//import { collection, getDoc, query, where, doc, deleteDoc } from "firebase/firestore";
import enGB from "date-fns/locale/en-GB";
import { Dialog, DialogTitle, DialogContent, DialogActions} from "@mui/material";
/* Stashed changes*/
function Home () {
    const [dateAndTime, setDateAndTime] = useState(new Date().toLocaleString("en-GB",{fullDate:'long', hour:'2-digit', minute:'2-digit', second:'2-digit'}));
    const [tasks, setTasks] = useState([]);
    const {user} = useAuth();
    const[usertime, setUsertime] = useState("");
    const[holidate, setHolidate] = useState("");
    const[todoTaskInput, setTodoTaskInput] = useState("");
    const [pastDue, setPastDue] = useState([]);
    const[dueDateInput, setDueDateInput] = useState("");
    const [AiTasks, setAiTasks] = useState([]);
    const[AiReply, setAiReply] = useState("");
    const [question, setQuestion] = useState("");
    const [openConfirm, setOpenConfirm] = useState(false);
    const [cvFile, setCvFile] = useState(null);
    const [events, setEvents] = useState([]);
    const [weather, setWeather] = useState("");
    const [summary, setSummary] = useState("");
    const [outstart, setOutstart] = useState("");
    const [end, setEnd] = useState("");
    //const [dueDate, setDueDate] = useState("");
    //const [CalendarEvents, setCalendarEvents] = useState([]);

        const locales = {
        "en-GB": enGB,
        };

        const localizer = dateFnsLocalizer({
                format,
                parse,
                startOfWeek: () => startOfWeek(new Date(), { weekStartsOn: 1 }),
                getDay,
                locales,
        });
    useEffect(() => {
        const refreshTasks= async()=>{
                try{
                    // 1. Load local tasks

                // 2. Fetch calendar events
                const res = await fetch("http://127.0.0.1:5000/calendar", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ userId: user?.uid || user?.email }),
                });
                const data = await res.json();
                setTasks(data.events || []);
                setEvents(data.events || []);
                const storedQuestions = localStorage.getItem("userQuestion");
                const storedReplies = localStorage.getItem("Aireply");
                if(storedQuestions){
                        setQuestion(storedQuestions);
                }
                if(storedReplies){
                        setAiReply(storedReplies);
                }
                }catch(error){
                        setTasks([]);
                        setQuestion([]);
                        console.error("Error parsing tasks from localStorage:", error);
                 }
        };
        refreshTasks();
    },[user?.uid],[]);
    useEffect(()=>{
        const fetchWeather = async ()=>{
                try{
                        const res = await fetch ("http://127.0.0.1:5000/weather",{
                                method:"POST",
                                headers:{"Content-Type":"application/json"},
                                body:JSON.stringify({location:"London"}),
                        });
                        const data = await res.json();
                        if (data.weather) {
                                setWeather(`${data.weather.temperature}°C, ${data.weather.description}`);
                                //toast.success(`Weather fetched for ${data.weather.city}`);
                        } else {
                               toast.error(data.error || "Failed to get weather");
                        }
                        return data.weather;
                }catch(error){
                        //console.error("Error fetching weather:", error);
                        //toast.error("Error fetching weather");
                }
        }
        fetchWeather();
    },[weather]);
    const deleteDocField = async (eventId) => {
        try {
        const res = await fetch("http://127.0.0.1:5000/calendar/delete", {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ eventId, userId: user?.uid || user?.email }),
        });

        const data = await res.json();

        if (data.success) {
        toast.success(data.reply || "Task deleted successfully.");
        setTasks((prev) => prev.filter((event) => event.googleEventId !== eventId));
        } else {
        toast.error(data.error || "Failed to delete task.");
        }

        // 🔹 Refresh events from backend (POST with userId)
        const refreshed = await fetch("http://127.0.0.1:5000/calendar/get", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ userId: user?.uid || user?.email }),
        }).then((r) => r.json());

        setEvents(refreshed.events || []);
        } catch (error) {
        console.error("Error deleting:", error);
        toast.error("Failed to delete task.");
        }
  };
  useEffect(()=>{
        const fetchFit = async ()=> {
                try{
                        const res =  await fetch("http://127.0.0.1:5000/outfit",{
                                method:"POST",
                                headers:{"Content-Type":"application/json"},
                                body:JSON.stringify({fit:"generate a random outfit for me to wear based on the weather."}),
                        });
                        const data = await res.json();
                        if (data.outgen) {
                                setOutstart(`${data.outgen}`);
                                //toast.success(`Weather fetched for ${data.weather.city}`);
                        } else {
                               toast.error(data.error || "Failed to get weather");
                        }
                        return data.outgen;
                }catch(error){
                        //console.error("Error fetching weather:", error);
                        //toast.error("Error fetching weather");
                }
        }
        fetchFit();
        //set interval for 30 mins
        const interval = setInterval(fetchFit, 1800000);
        return ()=> clearInterval(interval);
  },[]);
  // Add new event
  const handleAddTask = async () => {
    const currentDate = new Date().toISOString().slice(0, 16);
    if (!dueDateInput.trim() || !todoTaskInput.trim()) {
      toast.error("Please enter a due date and a task.");
      return;
        }

    if (new Date(dueDateInput) < new Date(currentDate)) {
      toast.error("Due date cannot be in the past.");
      return;
        }
        /*const updatedTasks = [...tasks, { task: todoTaskInput, dueDate: dueDateInput }];
        setTasks(updatedTasks);
        localStorage.setItem("todoTasks", JSON.stringify(updatedTasks));*/
    const redueDate = new Date(dueDateInput).toISOString().replace("Z", "+00:00");
    try {
        const res = await fetch("http://127.0.0.1:5000/calendar/add", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ summary: todoTaskInput, end: redueDate ,UserId:user.uid || user.email||"default_user"}),
    });
    const data = await res.json();
    alert(data.reply || data.error);
    if(data.error){
        toast.error(data.error);
    }else{
        toast.success(`Task "${todoTaskInput}" added successfully!`);
        setTodoTaskInput("");
        setDueDateInput("");
    }
    // refresh events after adding
    const refreshed = await fetch("http://127.0.0.1:5000/calendar/get", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ userId: user?.uid || user?.email }),
        }).then(r => r.json());
    setEvents(refreshed.events || []);
    setTasks(refreshed.events ||[]);
    } catch (error) {
        console.error("Error adding event:", error);
        toast.error("Failed to add task",error);
    }
    try{
        const events = await fetch("http://127.0.0.1:5000/calendar/get");
        if(!events.ok){
            const errorData = await events.json().catch(() => ({}));
            throw new Error(`HTTP error! status: ${events.status}, message: ${errorData.error||'Unknown error'}`);
        }
        const data = await events.json();
        toast.success("Events fetched successfully!");
        setTasks(data.events||[]);
        return data.events;
    }catch(error){
        console.error("Error fetching assistant response:", error);
        throw error;
    }
    }
    useEffect(() => {
        const pastDued = tasks.filter(t => new Date(t.end) < new Date());
        setPastDue(pastDued);
        localStorage.setItem("pastDueTasks", JSON.stringify(pastDued));
    }, [tasks]);
    /*const handleRemoveTask = (index)=>{
        const updatedTasks = tasks.filter((_,i) => i !== index);
        if(updatedTasks.length === 0){
                toast.error("No tasks to remove.");
                return;
        }else{
                setTasks(updatedTasks);
                localStorage.setItem("todoTasks",JSON.stringify(updatedTasks));
                toast.success("Task removed successfully!");
                return;
        }
        setTodoTaskInput("");
        setDueDateInput("");
    }*/
    useEffect(()=>{
        const taskInput = document.getElementById("task-input");
        const handleAiTasks = (e)=>{
                setAiTasks(e.target.value);
                if(e.target.value.trim() === ""){
                    toast.error("Please enter a task.");
                }else{
                    localStorage.setItem("AiTasks",e.target.value);
                    toast.success(`Task "${e.target.value}" added successfully!`);
                }
        };
        taskInput.addEventListener("change", handleAiTasks);
        return () => {
            taskInput.removeEventListener("change", handleAiTasks);
        };
    }, [AiTasks]);
    useEffect(() => {
        const cvinput = document.getElementById("cv-upload");
        const handleFileChange = (e) => {
            const file = e.target.files[0];
            if(file){
                setCvFile(file);
                alert(`CV file ${file.name} uploaded successfully!`);
                toast.success(`CV file ${file.name} uploaded successfully!`);
            }else{
                toast.error("No file selected.");
            }
        };
        cvinput.addEventListener("change",handleFileChange);
        return ()=>{
            cvinput.removeEventListener("change",handleFileChange);
        }
    }, []);
    const handleuserQuestionChange = async () => {
        if(!question.trim()){
            toast.error("Please enter a question.");
        }else{
            localStorage.setItem("userQuestion", question.trim());
            toast.success("Question submitted successfully!");
        }
        try{
                const reply = await fetchAssistantResponse(question);
                if(reply){
                        toast.success("message sent.")
                        setAiReply(reply);
                        toast.success(`Assistant reply: ${reply}`);
                        localStorage.setItem("AiReply",reply);
                }
                if (reply.includes("Do you want to clear it")) {
                        setOpenConfirm(true);  // open confirmation dialog
                }
        }catch(error){
                console.error("message error",error);
                toast.error("an error occurred with the sending process .");
        }
        if (reply.includes("event:")) {
                const redueDate = new Date(dueDateInput).toISOString().replace("Z", "+00:00");
                try {
                        const res = await fetch("http://127.0.0.1:5000/calendar/add", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ summary: todoTaskInput, end: redueDate ,UserId:user.uid || user.email||"default_user"}),
                });
                const data = await res.json();
                alert(data.reply || data.error);
                if(data.error){
                        toast.error(data.error);
                }else{
                        toast.success(`Task "${todoTaskInput}" added successfully!`);
                        setTodoTaskInput("");
                        setDueDateInput("");
                }
        }catch(error){
                console.error("Error adding event:", error);
                toast.error("Failed to add task",error);
        }
        if (reply.includes("task:")) {
                try{
                        const events = await fetch("http://127.0.0.1:5000/calendar/get");
                        if(!events.ok){
                        const errorData = await events.json().catch(() => ({}));
                        throw new Error(`HTTP error! status: ${events.status}, message: ${errorData.error||'Unknown error'}`);
                        }
                        const data = await events.json();
                        toast.success("Events fetched successfully!");
                        setTasks(data.events || []);
                        return data.events;
                }catch(error){
                        console.error("Error fetching assistant response:", error);
                        throw error;
                }
        }
        setQuestion("");
    }};
    const handleConfirmClear = async () => {
                try{
                        const res = await fetch("http://127.0.0.1:5000/clear", {
                                method: "POST",
                                headers: {"Content-Type":"application/json"},
                                body: JSON.stringify({confirmation: "yes" }),
                        });
                        const data = await res.json();
                        toast.success(data.reply || "Chat history cleared!");
                        localStorage.removeItem("AiReply");
                        localStorage.removeItem("userQuestion");
                } catch(error) {
                        toast.error("Failed to clear history");
                        console.error(error);
                }
                setOpenConfirm(false); // close dialog
        };
       const handleCancelClear = async () => {
                await fetch("http://127.0.0.1:5000/clear", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ confirmation: "no" })
                });
                toast.error("Chat history not cleared");
                setOpenConfirm(false);
        };
    const handleClearAllTasks = () => {
        if(tasks.length === 0){
                toast.error("No tasks to remove.");
                return;
        }
        setTasks([]);
        localStorage.removeItem("todoTasks");
        toast.success("All tasks removed!");

};
const userDetails = user ? `Logged in as: ${user.email}` : "Not logged in";
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
        const checkMonth =()=>{
                const month = new Date().getMonth();
                if(month >=2 && month <=4){
                        toast("It's spring!");
                        setHolidate("Happy spring!");
                }else if(month >=5 && month <=7){
                        toast("It's summer!");
                        setHolidate("Happy summer!");
                }else if(month >=8 && month <=10){
                        toast("It's autumn!");
                        setHolidate("Happy autumn!");
                }else{
                        toast("It's winter!");
                        setHolidate("Happy winter!");
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
        setHolidate("");
        checkTime();
        checkMonth();
        happyNewMonthandYear();
   }, [usertime,holidate]);
return (
    <main className=" w-screen rounded-md border border-white bg-slate-950 text-white h-screen overflow-none">
            <div className="h-[100px] w-full flex items-center justify-between font-bold text-xl p-5 text-left bg-black gap-4 rounded-md border border-black !overflow-auto">
                    <div className="flex items-center gap-2">
                      <Anchor
                      fontColor="primary"
                      style={{ fontSize: '40px' }}
                       className="text-blue-200" />
                      <h2 className="m-0">Dashboard</h2>
                    </div>
                    <div className="flex flex-col items-end">
                            <span className="text-blue-200 text-lg font-bold">{dateAndTime}</span>
                            <span className="text-blue-200 text-lg font-bold">{usertime},{userDetails}!</span>
                            {holidate && <span className="text-green-200 text-lg font-bold">{holidate}</span>}
                    </div>
            </div>
            <div className="flex flex-col md:flex-row h-[700px] w-full">
            <div className="h-auto p-5 m-6 gap-6 rounded-md border border-white">
                    <ul className="block flex-col md:flex-row gap-5 text-lg font-bold ">
                            <li className="mb-4"><Link to="/closet" className="text-white font-bold">Closet</Link></li>
                         <li className="mb-4"><Link to="/study" className="text-white font-bold"><Code/>Study</Link></li>
                            <input type="file" className="hidden" id="cv-upload" />
                            <label htmlFor="cv-upload" className="cursor-pointer">
                                    {cvFile ? <span className="text-blue-500"><Link to="/cv"><Work/>View CV</Link></span> : <span className="text-red-500"><Upload/>Upload CV</span>}
                            </label>
                            <li><Link to="/planner" className="text-white font-bold">Planner</Link></li>
                            <li>
                                {/*change to settings later on*/}
                                <Link to="/login" className="text-white font-bold">Settings/login</Link>
                            </li>
                    </ul>
            </div>
            <div className="flex flex-col md:flex-row h-[700px] w-auto p-5 m-6 gap-4 rounded-md border border-slate-800 !overflow-auto">
                <div className=" h-auto max-w-[400px] p-5 m-6 gap-6 rounded-md border border-slate-800 !overflow-auto">
                    <section className="block flex-col md:flex-row md:h-[300px] w-auto p-6 m-6 gap-4 rounded-md border border-slate-800 !overflow-auto">
                        <ul className="block flex-col md:flex-row gap-4">
                                {weather ? <li className="font-bold rounded-md border border-slate-800 p-5 text-orange-500">weather:{weather}</li> : <li>Loading weather...</li>}
                                {
                                events.length > 0 ? (
                                        events.map((event) => (
                                                <li key={event.id} className="text-underlined">
                                                {event.summary ? event.summary : "No Title"} - Due:{" "}
                                                {event.end
                                                ? new Date(event.end).toLocaleString([], {
                                                        year: "numeric",
                                                        month: "2-digit",
                                                        day: "2-digit",
                                                        hour: "2-digit",
                                                        minute: "2-digit",
                                                })
                                                : "N/A"}
                                                </li>
                                        ))
                                        ) : (
                                        <li className="font-bold rounded-md border border-slate-800 p-5 bg-slate-900">
                                        no summary
                                        <br/>summary should contain the following:
                                        <br/>coursera completed courses and left,
                                        <br/>projects done,
                                        <br/>calendar events,
                                        <br/>leetcode problems solved,
                                        <br/>github contributions
                                        </li>
                                        )}
                                        <li className="font-bold rounded-md border border-white p-5 bg-sky-500">
                                        Start my day
                                        </li>
                        </ul>
                 </section>
                 <section className=" h-auto max-w-[400px] p-5 m-6 gap-6 rounded-md border border-slate-800 !overflow-auto">
                            <h3 className="text-blue-300 text-lg font-bold m-3"><SmartToy/>AI Chat Assistant</h3>
                            <div className="rounded-md border border-slate-800 p-2 mb-4 bg-slate-800 text-white text-lg">
                                    <h4 className="text-blue-400 text-left font-bold"><SmartToy/>AI response</h4>
                                    {/*{AiReply ? AiReply :"no reply"}*/}
                                    <h4 className="text-gray-500 text-right font-bold">
                                        <div className="text-blue-300 text-left font-bold m-3">You asked:</div>
                                        <p>{localStorage.getItem("userQuestion")}</p>
                                        <Linkify><p className="text-left">{localStorage.getItem("AiReply")}</p></Linkify>
                                        <p className="text-white">{question ? question : "ask me anything!"}</p>
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
                            <li className="font-bold rounded-sm border border-blue-500  mb-4 cursor-pointer list-none">
                                <input type="file" className="hidden" id="file-upload" />
                                <label className="cursor-pointer" htmlFor="file-upload">
                                    <Upload />
                                </label>
                                </li>
                            <input className="rounded-sm border border-white p-2 mb-4 w-[180px] max-h-[200px]"
                            id="user-question"
                            value={question}
                            onChange={(e) => setQuestion(e.target.value)}
                            type="text" placeholder="Ask me anything..." />
                            <section className=" gap-4 mb-4">
                                    <Button variant="contained"
                                    color="primary"
                                    size="small"
                                    onClick={handleuserQuestionChange}
                                    style={{ margin: '5px' }}
                                    component="span"
                                    className="bg-blue-600 text-white p-2 rounded-md m-2">Ask</Button>
                                    <Button variant="contained"
                                    color="primary"
                                    size="small"
                                    style={{ margin: '5px' }}
                                    component="span"
                                    className="bg-blue-500 text-white p-2 rounded-md m-2">Tailor my CV</Button>
                                    <Button variant="contained"
                                    component="span"
                                    color="primary"
                                    size="small"
                                    style={{ margin: '5px' }}
                                    className="bg-blue-600 text-white p-2 rounded-md m-2">Suggest an outfit</Button>
                                    <Button variant="contained"
                                    component="span"
                                    color="primary"
                                    size="small"
                                    style={{ margin: '5px' }}
                                    className="bg-blue-500 text-white p-2 rounded-md m-2">Plan my day</Button>
                                    <Button
                                        size="small"
                                        variant="contained"
                                        color="primary"
                                        onClick={() => setAiTasks('')}
                                        style={{ margin: '5px' }}
                                        className="w-[200px] bg-surface text-primary rounded-2xl shadow-soft border border-border hover:bg-accent-indigo-light transition"
                                        >
                                        {localStorage.getItem("AiTasks") ? localStorage.getItem("AiTasks") : "No tasks added yet"}
                                </Button>
                                <input
                                        className="w-[150px] rounded-md border border-border bg-background text-primary placeholder-secondary p-2 mb-0 focus:outline-none focus:ring-2 focus:ring-accent-indigo"
                                        id="task-input"
                                        value={AiTasks}
                                        onChange={(e) => setAiTasks(e.target.value)}
                                        type="text"
                                        placeholder="New task..."
                                        />
                            </section>
                    </section>
                    </div>
                    <div className=" md:flex-col md: h-[600px] w-[600px] p-2 m-2 gap-2 text-white rounded-md border border-black !overflow-auto">
                    <section className="md:flex-col md:h-[400px] w-[300px] p-2 m-2 gap-2 rounded-md border border-slate-900 !overflow-auto">
                                <h3 className="text-xl font-bold">To - Do List</h3>
                                <ul className="list-disc list-none p-4 text-green-500 font-bold">
                                        {events.length >0 ? events.map((event) => (
                                                <li key={event.id} className="text-underlined">
                                                        {event.summary ? event.summary : "No Title"}- Due:{""}
                                                        {event.end ? new Date(event.end).toLocaleString([],{
                                                        year: 'numeric',
                                                        month: '2-digit',
                                                        day: '2-digit',
                                                        hour: '2-digit',
                                                        minute: '2-digit'
                                                }) : "No due date"}
                                                <Button 
                                                variant="contained" 
                                                color="error" 
                                                size="small" 
                                                onClick={() => deleteDocField(event.googleEventId)}
                                                style={{ marginLeft: "10px" }}
                                                >
                                                {/*onClick={() => handleRemoveTask(index)}*/}
                                                <Delete
                                                        fontSize="small"
                                                        style={{ color: 'white' }}
                                                />
                                                </Button>
                                        </li>
                                        )) : <li>No tasks added yet.</li>}
                                </ul>
                                <h3 className="text-xl font-bold">Past Due</h3>
                                <ul className="list-disc list-none p-4 text-red-500 font-bold mb-4 gap-2 justify-between">
                                        <ul className="list-disc list-none p-4 text-red-500 font-bold mb-4 gap-2 justify-between">
                                        {pastDue.length > 0 ? pastDue.map((p,index)=>(
                                                <li key={p.id} className="text-underlined">{p.task} - Due: {new Date(p.dueDate).toLocaleString([],{
                                                        year: 'numeric',
                                                        month: '2-digit',
                                                        day: '2-digit',
                                                        hour: '2-digit',
                                                        minute: '2-digit'
                                                })}
                                                <Button 
                                                variant="contained" 
                                                color="error" 
                                                size="small" 
                                                onClick={() => handleRemoveTask(index)}
                                                style={{ marginLeft: "10px" }}
                                                >
                                                <Delete
                                                        fontSize="small"
                                                        style={{ color: 'white' }}
                                                />
                                                </Button>
                                        </li>)):<li>No past dues</li>}
                                        </ul>
                                        <Stack spacing={2}>
                                                <TextField
                                                label="Event Summary"
                                                type="text"
                                                id="todo-tasks"
                                                value={todoTaskInput}
                                                onChange={(e) => setTodoTaskInput(e.target.value)}
                                                />
                                                <TextField
                                                type="datetime-local"
                                                id="todo-due-date"
                                                style={{backgroundColor:"#e6e2e2e4", color:"white"}}
                                                sx={{ width: 200 }}
                                                value={dueDateInput}
                                                onChange={(e) => setDueDateInput(e.target.value)}
                                                fullWidth
                                                />
                                                <Button variant="contained" onClick={handleAddTask}>
                                                Add Event
                                                </Button>
                                                <Button 
                                                        variant="contained"
                                                        component="span"
                                                        
                                                        color="error"
                                                        size="small"
                                                        style={{ margin: '5px'}}
                                                        onClick={handleClearAllTasks}
                                                        className="bg-red-500 text-white p-2 mt-2 border border-transparent font-bold">
                                                        <Delete /> Clear All Tasks
                                                </Button>
                                        </Stack>
                                </ul>
                        </section>
                                <Card sx={{ p: 4, borderRadius: "16px", boxShadow: 3,height:"auto", maxHeight:450, width: 300, maxWidth: "600px", overflow: "hidden" }}>
                                        <CardContent >
                                        <Typography variant="h6" gutterBottom>
                                                📅 My Calendar
                                        </Typography>

                                        {/* Interactive Calendar */}
                                        <Calendar 
                                                localizer={localizer}
                                                events={events.map(ev => ({
                                                title: ev.summary || "No title",
                                                start: new Date(ev.start),
                                                end: new Date(ev.end)
                                                }))}
                                                startAccessor="start"
                                                endAccessor="end"
                                                style={{ height: 350,width: 200, margin: "10px 0" }}
                                                selectable
                                                onSelectSlot={(slot) => {
                                                console.log("Selected slot:", slot);
                                                setDueDateInput(slot.end.toISOString());
                                                toast.success("Slot selected! Fill in the summary to add event.");
                                                }}
                                                onSelectEvent={(event) => {
                                                alert(`Selected event: ${event.title}`);
                                                }}
                                        />

                                        <Divider sx={{ my: 2 }} />
                                        </CardContent>
                                </Card>
                                </div>
                    <section className="h-auto max-h-[400px] max-w-[200px] rounded-md border border-slate-900 p-5 m-6 bg-slate-850  text-lg gap-4 !overflow-auto">
                            <h3 className="font-bold text-blue-200">Outfit of the Day</h3>
                            {outstart ? <p className="text-white">{outstart}</p>:<p className="text-white">Today's outfit suggestion based on weather and schedule.</p>}
                    </section>
                    <section className="h-auto max-h-[400px] rounded-md border border-slate-800 p-5 m-6 bg-slate-850 text-white text-lg gap-4">
                            <h3>Study Progress</h3>
                            <progress value="70" max="100" className="w-full h-6 rounded-md border border-white bg-slate-700">
                                    70% completed
                            </progress>
                    </section>
            </div>
            </div>
    </main>
);
}
export default Home;
