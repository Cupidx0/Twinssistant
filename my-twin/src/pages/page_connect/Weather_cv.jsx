import React,{use, useEffect,useState} from "react";
import {Card, CardContent, Typography,
  Button, TextField, Stack, Divider} from "@mui/material";
import toast, { Toaster } from "react-hot-toast";
import { WeatherAPI } from "../../Utils/Assistant";
import { useAuth } from "../AuthContext";
import {Link, replace} from "react-router-dom";
/* Updated upstream*/
import {Anchor,Delete,SmartToy,Inventory,MusicNote,
        Settings,CalendarMonth,Inventory2,Cloud,
        Upload,Work,Code,ArrowUpwardTwoTone} from "@mui/icons-material";
export default function Weather_cv() {
    const [weather, setWeather] = useState(null);
    const [events, setEvents] = useState([]);
    const [cvFile, setCvFile] = useState(null);
    const { isLoggedIn } = useAuth();
    useEffect(() => {
        if (isLoggedIn) {
            WeatherAPI.fetchWeather()
            .then((weatherData) => {
                if (weatherData.weather) {
                    setWeather(`${weatherData.weather.temperature}°C, ${weatherData.weather.description}`);
                    toast.success(`Weather fetched for ${weatherData.weather.city}`);
                } else {
                    toast.error("Failed to get weather");
                }
            })
            .catch((error) => {
                console.error("Error fetching weather:", error);
                toast.error("Error fetching weather");
            });
        }
    }, [isLoggedIn]);
  return (
    <div className="flex flex-col gap-4 h-full bg-transparent">
        <section className="block flex-col md:flex-row md:h-auto bg-transparent w-auto p-2 rounded-md gap-4 !overflow-auto">
            <div className="overflow-hidden rounded-2xl mb-4 border border-slate-800 bg-[radial-gradient(circle_at_top_left,_rgba(34,211,238,0.18),_transparent_28%),linear-gradient(135deg,_#0f172a_0%,_#111827_55%,_#020617_100%)] p-4 shadow-[0_24px_80px_rgba(2,6,23,0.45)] sm:p-6">
                {weather ?<span><Cloud/>{weather}</span> : <span>Loading weather...</span>}
            </div>
            <ul className="block flex-col md:flex-row gap-4 bg-slate-900 shadow-[0_24px_80px_rgba(2,6,23,0.45)] rounded-md backdrop-blur-sm border border-slate-800/10 p-4 sm:p-5">
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
                                <li className="font-bold rounded-md border border-slate-800 p-5 bg-blend-50/10 bg-gradient-to-r from-slate-950 to-gray-900 text-center">
                                    no summary
                                    <br/>summary should contain the following:
                                    <br/>coursera completed courses and left,
                                    <br/>projects done,
                                    <br/>calendar events,
                                    <br/>leetcode problems solved,
                                    <br/>github contributions
                                </li>
                            )}
            </ul>
        </section>
        <section className="h-auto max-h-[400px] rounded-md p-5 m-6 bg-slate-900 shadow-[0_24px_80px_rgba(2,6,23,0.45)] text-white text-lg gap-4">
            <Button variant="contained"
                    color="primary"
                    size="small"
                    onClick=''
                    style={{ margin: '5px',padding: '10px', backgroundColor: '#46e55622', backdropFilter:"blur(10px)",border:"1px solid #46e556", color:"#46e556" }}
                    className="bg-blue-500 text-white p-4 rounded-md m-2">
                    <input type="file" className="hidden" id="cv-upload" />
                    <label htmlFor="cv-upload" className="cursor-pointer"></label>
                    {cvFile ? <span className="text-blue-500"><Link to="/cv"><Work/>View CV</Link></span> : <span>Upload your CV <ArrowUpwardTwoTone/></span>}</Button>
        </section>
    </div>
  );
}