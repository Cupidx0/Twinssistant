import React,{use, useEffect,useState} from "react";
import {Card, CardContent, Typography,
  Button, TextField, Stack, Divider} from "@mui/material";
import toast, { Toaster } from "react-hot-toast";
import {Link, replace} from "react-router-dom";
/* Updated upstream*/
import {Anchor,Delete,SmartToy,Inventory,MusicNote,
        Settings,CalendarMonth,Inventory2,Cloud,
        Upload,Work,Code,ArrowUpwardTwoTone} from "@mui/icons-material";  
//import {useAuth} from "./AuthContext";
import { CalendarAPI } from "../../Utils/Assistant";
import { Calendar, dateFnsLocalizer } from "react-big-calendar";
import { format, parse, startOfWeek, getDay, set } from "date-fns";
import "react-big-calendar/lib/css/react-big-calendar.css";
//import {store,db} from "../Utils/Firebase";
//import { collection, getDoc, query, where, doc, deleteDoc } from "firebase/firestore";
import enGB from "date-fns/locale/en-GB";
import { Dialog, DialogTitle, DialogContent, DialogActions} from "@mui/material";
export default function Calendar_g(){
   const [events, setEvents] = useState([]);
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
                    // Fetch events from backend on component mount
                    fetchEvents();
            }, []);
            const fetchEvents = async () => {
                    try {
                            const response = await CalendarAPI.fetchEvents();
                            setEvents(response.data.events || []);
                    } catch (error) {
                            console.error("Error fetching events:", error);
                            toast.error("Failed to load calendar events");
                    }
            };
        return(
        <div className="flex flex-col gap-4">
            <section className="block flex-col md:flex-row md:h-auto w-auto p-2 rounded-md border border-slate-800 !overflow-auto">
                <Card sx={{ p: 4, borderRadius: "16px", boxShadow: 3,height:"auto", maxHeight:450, width: 300, maxWidth: "600px", overflow: "hidden" }}>
                                        <CardContent >
                                        <Typography variant="h6" gutterBottom>
                                                📅 My Calendar
                                        </Typography>

                                        { /*Interactive Calendar*/}
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
            </section>
        </div>
        );
}