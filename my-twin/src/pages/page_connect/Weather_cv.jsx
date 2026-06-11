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
import { serverTimestamp } from "firebase/firestore";
export default function Weather_cv() {
    const [weather, setWeather] = useState(null);
    const [events, setEvents] = useState([]);
    const [cvFile, setCvFile] = useState(null);
    const [role, setRole] = useState("")
    const [preview, setPreview] = useState("")
    const [review, setReview] = useState(null)
    const [rewrite, setRewrite] = useState("")
    const [loading, setLoading] = useState("")

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
        setReview(null);
        setRewrite("");
        setPreview("");

        ConvertTextAPI.convertFileToText(file)
            .then((response) => {
                if (response.text) {
                    toast.success("CV text extracted successfully!");
                    console.log("Extracted CV Text:", response.text);
                    setPreview(response.text);
                } else {
                    toast.error("Failed to extract text from CV");
                }
                if (response.cv) {
                    toast.success("CV file saved successfully!");
                    console.log("Saved CV Path:", response.cv);
                } else {
                    toast.error("Failed to save CV file");
                }
            })
            .catch((error) => {
                console.error("Error converting file to text:", error);
                toast.error("Error converting file to text");
            });
    };

    const getReview = async () => {
        const role = "Software Engineer";
        if (!cvFile) {
            toast.error("Please upload a CV first.");
            return;
        }
        
        setLoading("reviewing");
        
        ConvertTextAPI.ReviewCV(role || "Software Engineer")
            .then((response) => {
                if (response.review) {
                    toast.success("CV review fetched successfully!");
                    console.log("CV Review:", response.review);
                    setReview(response.review);
                } else {
                    toast.error("Failed to fetch CV review");
                }
            } )
            .catch ((error)=> {
                console.error("Error fetching CV review:", error);
                toast.error("Error fetching CV review");
            })
            . finally (() => {
                setLoading("");
            });
    };

    const getRewrite = async () => {
        if (!cvFile) {
            toast.error("Please upload a CV first.");
            return;
        }
        setLoading("rewriting");
        try {
            const response = await ConvertTextAPI.RewriteCV(role || "Software Engineer");
            const blob = new Blob([response], { type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document" });
            const url = window.URL.createObjectURL(blob);
            const link = document.createElement("a");
            link.href = url;
            link.setAttribute("download", `rewritten_${role.replace(/ /g, "_")}.docx`);
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            toast.success("CV rewritten successfully!");
            /*if (response.rewritten_cv) {
                toast.success("CV rewritten successfully!");
                //setRewrite(response.rewritten_cv);
            } else {
                toast.error("Failed to rewrite CV");
            }*/
        } catch (error) {
            console.error("Error rewriting CV:", error);
            toast.error("Error rewriting CV");
        } finally {
            setLoading("");
        }
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
            <div className="cv-page">
                    <h2>CV Tool</h2>

                    <div className="upload-section">
                        <Button variant="contained" component="label" className="mb-4">
                            <Upload className="text-primary"/>
                            {cvFile ? cvFile.name : "Upload CV"}
                            <input 
                                type="file" 
                                hidden 
                                onChange={handleFileChange}
                            />
                        </Button>
                        <TextField
                            label="Role you're applying for"
                            variant="outlined"
                            fullWidth
                            value={role}
                            onChange={(e) => setRole(e.target.value)}
                        />
                        {cvFile && <p>File selected: {cvFile.name}</p>}
                    </div>

                    {preview && (
                        <div className="preview">
                            <p>Preview: {preview}</p>
                            <button onClick={getReview}>
                                {loading === "reviewing" ? "Reviewing..." : "Review CV"}
                            </button>
                           <button onClick={getRewrite}>
                                {loading === "rewriting" ? "Rewriting..." : "Rewrite CV"}
                                {loading === "rewriting" && <ArrowUpwardTwoTone className="animate-bounce"/>}
                            </button>
                        </div>
                    )}

                    {review && (
                        <div className="review-result">
                            <h3>Review — Score: {review.score || "N/A"}/10</h3>
                            <p>{review.summary}</p>
                            <p><strong>Strengths:</strong> {review.strengths?.join(", ")}</p>
                            <p><strong>Weaknesses:</strong> {review.weaknesses?.join(", ")}</p>
                            {review.missing?.length > 0 && (
                                <p><strong>Missing:</strong> {review.missing?.join(", ")}</p>
                            )}
                            <button onClick={() => navigator.clipboard.writeText(JSON.stringify(review))}>
                                Copy Review JSON
                            </button>
                        </div>
                    )}

                    {rewrite && (
                        <div className="rewrite-result">
                            <h3>Rewritten CV</h3>
                            <pre>{rewrite}</pre>
                            <button onClick={() => navigator.clipboard.writeText(rewrite)}>
                                Copy
                            </button>
                        </div>
                    )}
                </div>
            </section>
        </div>
  );
}
