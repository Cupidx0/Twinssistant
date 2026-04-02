import React, { useState, useEffect } from "react";
import {Card, CardContent, Typography,
  Button, TextField, Stack, Divider} from "@mui/material";
import toast, { Toaster } from "react-hot-toast";
import { ChatAPI } from "../../Utils/Assistant";
import {Link, replace} from "react-router-dom";
import {Anchor,Delete,SmartToy,Inventory,MusicNote,
        Settings,CalendarMonth,Inventory2,Cloud,
        Upload,Work,Code,ArrowUpwardTwoTone} from "@mui/icons-material";  
//import {useAuth} from "./AuthContext";
//import {store,db} from "../Utils/Firebase";
//import { collection, getDoc, query, where, doc, deleteDoc } from "firebase/firestore";
import { Dialog, DialogTitle, DialogContent, DialogActions} from "@mui/material";
/* Stashed changes*/
export default function Outfit_of_day() {
    const [outstart, setOutstart] = useState(null);
    useEffect(()=>{
        fetchFit()
        const interval = setInterval(fetchFit, 1800000);
        return ()=> clearInterval(interval);
    }, []);
    const fetchFit = async () => {
        const fit = "generate a random outfit for me to wear based on the weather."
        try{
            const response = await ChatAPI.fetchFit(fit);
            if(response.outgen){
                setOutstart(response.outgen);
                toast.success("Today's outfit suggestion is ready!");
            } else {
                toast.error("Failed to get outfit suggestion");
            }
        }catch(error){
            console.error("Error fetching outfit suggestion:", error);
            toast.error("Error fetching outfit suggestion");
        }
    };
    return (
        <div className="flex flex-col gap-4">
            <section className="block flex-col md:flex-row md:h-auto w-auto p-2 rounded-md border border-slate-800 !overflow-auto">
                <h1 className="text-2xl font-bold">Outfit of the Day</h1>
                {outstart ? <p className="text-white">{outstart}</p>:<p className="text-white">Today's outfit suggestion based on weather and schedule.</p>}
                <p>Feature coming soon! Stay tuned for personalized outfit recommendations based on your calendar events and weather conditions.</p>
            </section>
        </div>
    );
}