import React,{useEffect,useState} from "react";
import {Button} from "@mui/material";
import toast, { Toaster } from "react-hot-toast";
import {Link} from "react-router-dom";
import {Dashboard, Delete,SmartToy,
        Upload,Work,Code} from "@mui/icons-material";  
function Home () {
    const [dateAndTime, setDateAndTime] = useState(new Date().toLocaleString("en-GB",{fullDate:'long', hour:'2-digit', minute:'2-digit', second:'2-digit'}));
    const [tasks, setTasks] = useState([]);
    const[todoTaskInput, setTodoTaskInput] = useState("");
    const [pastDue, setPastDue] = useState([]);
    const[dueDateInput, setDueDateInput] = useState("");
    const [AiTasks, setAiTasks] = useState([]);
    const [question, setQuestion] = useState("");
    const [cvFile, setCvFile] = useState(null);
    //const [dueDate, setDueDate] = useState("");
    //const [CalendarEvents, setCalendarEvents] = useState([]);
    useEffect(() => {
        const refreshTasks=()=>{
                try{
                    const storedTasks = JSON.parse(localStorage.getItem("todoTasks"));
                    const storedQuestions = localStorage.getItem("userQuestion");
                    if(storedTasks){
                        setTasks(storedTasks);
                    }
                    if(storedQuestions){
                        setQuestion(storedQuestions);
                    }
                }catch(error){
                        setTasks([]);
                        setQuestion([]);
                        console.error("Error parsing tasks from localStorage:", error);
                 }
        };
        refreshTasks();
    }, []);
    const handleAddTask = () => {
        const currentDate = new Date().toISOString().slice(0,16);
        if(!dueDateInput.trim()||!todoTaskInput.trim()){
                toast.error("Please enter a due date and a task.");
                return;
        }

        if(new Date(dueDateInput) < new Date(currentDate)){
                toast.error("Due date cannot be in the past.");
                return;
        }
        const newTasks = {task:todoTaskInput.trim(),dueDate:dueDateInput.trim()};
        const updateTasks = [...tasks, newTasks];
        setTasks(updateTasks);
        localStorage.setItem("todoTasks",JSON.stringify(updateTasks));
        toast.success(`Task "${todoTaskInput}" added successfully!`);
        setTodoTaskInput("");
        setDueDateInput("");
    }
    useEffect(() => {
        const pastDued = tasks.filter(t => new Date(t.dueDate) < new Date());
        setPastDue(pastDued);
        localStorage.setItem("pastDueTasks", JSON.stringify(pastDued));
    }, [tasks]);
    const handleRemoveTask = (index)=>{
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
    }
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
    const handleuserQuestionChange = () => {
        if(!question.trim()){
            toast.error("Please enter a question.");
        }else{
            localStorage.setItem("userQuestion", question.trim());
            toast.success("Question submitted successfully!");
        }
        setQuestion("");
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

   useEffect(() => {
        const interval = setInterval(() => {
            setDateAndTime(new Date().toLocaleString());
        }, 1000);
        return () => clearInterval(interval);
    }, []);
return (
    <main className=" w-screen rounded-md border border-white bg-black text-white h-screen overflow-none">
            <div className="h-[100px] w-full flex items-center justify-between font-bold text-xl p-5 text-left bg-black gap-4 rounded-md border border-white !overflow-auto">
                    <div className="flex items-center gap-2">
                      <Dashboard 
                      fontColor="primary"
                      style={{ fontSize: '40px' }}
                       className="text-blue-200" />
                      <h2 className="m-0">Dashboard</h2>
                    </div>
                    <div className="flex flex-col items-end">
                            <span className="text-blue-200 text-lg font-bold">{dateAndTime}</span>
                            <span className="text-blue-200 text-lg font-bold">Welcome, User!</span>
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
            <div className="flex flex-col md:flex-row h-[700px] w-auto p-5 m-6 gap-4 rounded-md border border-white !overflow-auto">
                    <section className="block flex-col md:flex-row md:h-[300px] w-[700px] p-6 m-6  gap-4 rounded-md border border-white !overflow-auto">
                            <ul className="block flex-col md:flex-row gap-4  ">
                                <li className="font-bold rounded-md border border-white p-5 mb-4 bg-blue-500">Today's summary</li>
                                <li className="font-bold rounded-md border border-white p-5 bg-sky-500">Start my day</li>
                            </ul>
                    </section>
                    <div className=" h-auto p-5 m-6 gap-6 rounded-md border border-white !overflow-auto">
                            <h3 className="text-blue-300 text-lg font-bold m-3"><SmartToy/>AI Chat Assistant</h3>
                            <div className="rounded-md border border-white p-2 mb-4 bg-white text-black text-lg">
                                    <h4 className="text-blue-400 text-left font-bold"><SmartToy/>AI response</h4>
                                    <h4 className="text-gray-500 text-right font-bold">
                                        <div className="text-blue-300 text-left font-bold m-3">You asked:</div>
                                        <p>{localStorage.getItem("userQuestion")}</p>
                                        {question ? question : "ask me anything!"}
                                    </h4>
                            </div>
                            <input className="rounded-sm border border-white p-2 mb-4 w-auto"
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
                                    className="bg-blue-500 text-white p-2 rounded-md m-2">Ask</Button>
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
                                    className="bg-blue-500 text-white p-2 rounded-md m-2">Suggest an outfit</Button>
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
                    </div>
                    <section className="h-auto max-h-[100vh] rounded-md border border-white p-5 m-6 bg-gray-500 text-black text-lg gap-4 overflow-auto">
                            <h3 className="text-xl font-bold">To - Do List</h3>
                            <ul className="list-disc list-none p-4 text-green-500 font-bold">
                                    {tasks.length >0 ? tasks.map((t, index) => (
                                        <li key={index} className="text-underlined">{t.task} - Due: {new Date(t.dueDate).toLocaleString([],{
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
                                    </li>
                                    )) : <li>No tasks added yet.</li>}
                            </ul>
                            <h3 className="text-xl font-bold">Past Due</h3>
                            <ul className="list-disc list-none p-4 text-red-500 font-bold mb-4 gap-2 justify-between">
                                <ul className="list-disc list-none p-4 text-red-500 font-bold mb-4 gap-2 justify-between">
                                    {pastDue.length > 0 ? pastDue.map((p,index)=>(
                                        <li key={index} className="text-underlined">{p.task} - Due: {new Date(p.dueDate).toLocaleString([],{
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
                                    <input
                                        type="text"
                                        id="todo-tasks"
                                        value={todoTaskInput}
                                        onChange={(e) => setTodoTaskInput(e.target.value)}
                                     className="rounded-md border border-white bg-white p-1 mb-4 w-full" />
                                     <input
                                        type="datetime-local"
                                        id="todo-due-date"
                                        style={{marginRight:'30px'}}
                                        value={dueDateInput}
                                        onChange={(e) => setDueDateInput(e.target.value)}
                                        className="rounded-md border border-white bg-white p-1 mb-2 w-[220px]"
                                        placeholder="Due date"
                                    />
                                <Button variant="contained"
                                onClick={handleAddTask} 
                                 className="bg-blue-500 text-white p-2 rounded-md">Add Task</Button>
                                <Button 
                                    variant="contained"
                                    component="span"
                                    color="neutral"
                                    size="small"
                                    style={{ margin: '5px' }}
                                    onClick={handleClearAllTasks}
                                    className="bg-red-500 text-white p-2 mt-2 border border-transparent font-bold">
                                    <Delete /> Remove Task
                                </Button>
                            </ul>
                    </section>
                    <section className="h-auto rounded-md border border-white p-5 m-6 bg-slate-700 text-black text-lg gap-4">
                            <h3>Calendar</h3>
                            <p className="text-slate-300">Upcoming events and deadlines.</p>
                            <ul className="list-disc list-none p-4 text-white font-bold">
                                    <li>Project deadline: 2023-10-30</li>
                                    <li>Team meeting: 2023-10-31</li>
                            </ul>
                            <Button variant="contained" size="small" style={{ margin: '5px' }} className="bg-blue-500 text-white rounded-sm">Add Event</Button>
                            <Button variant="contained" color="success" size='small' className="bg-green-500 text-white rounded-sm">View Calendar</Button>
                    </section>
                    <section className="h-auto max-h-[400px] rounded-md border border-white p-5 m-6 bg-slate-600 text-black text-lg gap-4">
                            <h3>Outfit of the Day</h3>
                            <p className="text-slate-300">Today's outfit suggestion based on weather and schedule.</p>
                    </section>
                    <section className="h-auto max-h-[400px] rounded-md border border-white p-5 m-6 bg-slate-600 text-black text-lg gap-4">
                            <h3>Study Progress</h3>
                            <progress value="70" max="100"></progress>
                    </section>
            </div>
            </div>
    </main>
);
}
export default Home;
