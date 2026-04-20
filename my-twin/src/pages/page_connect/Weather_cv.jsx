import React,{use, useEffect,useState} from "react";
import {Card, CardContent, Typography,
  Button, TextField, Stack, Divider} from "@mui/material";
import toast, { Toaster } from "react-hot-toast";
import { WeatherAPI,ConvertTextAPI} from "../../Utils/Assistant";
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
            //cv file upload listener
        }
    }, [isLoggedIn]); 
    const handleFileChange = (e) => {
        const file = e.target.files[0];

        if (!file) return;

        setCvFile(file);

        ConvertTextAPI.convertFileToText(file)
            .then((response) => {
                if (response.text) {
                    toast.success("CV text extracted successfully!");
                    console.log("Extracted CV Text:", response.text);
                } else {
                    toast.error("Failed to extract text from CV");
                }
            })
            .catch((error) => {
                console.error("Error converting file to text:", error);
                toast.error("Error converting file to text");
            });
    };
  return (
    <div className="flex h-full flex-col gap-4 bg-transparent">
        <section className="block flex-col md:flex-row md:h-auto bg-transparent w-auto p-2 rounded-md gap-4 !overflow-auto">
            <div className="glass-strong mb-4 overflow-hidden rounded-2xl border border-border bg-gradient-aurora p-4 sm:p-6">
                {weather ?<span className="flex items-center gap-2 text-card-foreground"><Cloud className="text-primary"/>{weather}</span> : <span className="text-muted-foreground">Loading weather...</span>}
            </div>
            <ul className="glass block flex-col gap-4 rounded-md border border-border p-4 sm:p-5 md:flex-row">
                {
                    events.length > 0 ? (
                        events.map((event) => (
                        <li key={event.id} className="text-card-foreground">
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
                                <li className="rounded-md border border-border bg-card p-5 text-center font-bold text-card-foreground">
                                    no summary
                                    <br/><span className="font-normal text-muted-foreground">summary should contain the following:</span>
                                    <br/>coursera completed courses and left,
                                    <br/>projects done,
                                    <br/>calendar events,
                                    <br/>leetcode problems solved,
                                    <br/>github contributions
                                </li>
                            )}
            </ul>
        </section>
        <section className="glass h-auto max-h-[400px] rounded-md p-5 m-6 text-lg text-card-foreground gap-4">
            <Button
                    variant="contained"
                    color="primary"
                    size="small"
                    style={{ margin: '5px', padding: '10px' }}
                    className="m-2 rounded-md border border-border bg-primary p-4 text-primary-foreground shadow-soft"
                    >
                    <label htmlFor="cv-upload" className="cursor-pointer flex items-center gap-2">
                        <Upload className="text-primary"/>
                        {cvFile ? cvFile.name : "Upload CV"}
                    </label>

                    <input 
                        type="file" 
                        className="hidden" 
                        id="cv-upload"
                        onChange={handleFileChange}
                    />
                </Button>
            </section>
        </div>
  );
}
