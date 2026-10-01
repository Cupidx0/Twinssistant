import React, { useState , useEffect} from 'react';
import { Card, CardContent, Typography, Button, TextField, Stack, Divider } from '@mui/material';
import toast, { Toaster } from 'react-hot-toast';
import { ChatAPI } from '../../Utils/Assistant';
import { useAuth } from '../AuthContext';
import { Link,replace } from 'react-router-dom';
import { Anchor, Delete, SmartToy, Inventory, MusicNote, Settings, CalendarMonth, Inventory2, Cloud, Upload, Work, Code, ArrowUpwardTwoTone } from '@mui/icons-material';

export default function Notepad() {
  const [noteContent, setNoteContent] = useState('');
  const [noteTitle, setNoteTitle] = useState('');
  //const { isLoggedIn } = useAuth();
    return (
        <div className="flex flex-col gap-4">
            <section className="block flex-col md:flex-row md:h-auto w-auto p-2 rounded-md border border-slate-800 !overflow-auto">
                <h1 className="text-2xl font-bold">Notepad</h1>
                <TextField
                label="Note Title"
                variant="outlined"
                fullWidth
                value={noteTitle}
                onChange={(e) => setNoteTitle(e.target.value)}
                sx={{ mb: 2 }}
                />
                <TextField
                    label="Write your note here..."
                    variant="outlined"
                    fullWidth
                    multiline
                    rows={10}
                    value={noteContent}
                    placeholder={"Start typing your note..."}
                    onChange={(e) => setNoteContent(e.target.value)}
                />
                <text className="text-sm text-gray-400 mt-1">Your notes are stored locally in your browser and will not be saved to the server.</text>
                <Divider sx={{ my: 2 }} />
                <Button variant="contained" color="primary" onClick="" sx={{ mt: 2 }}>
                Save Note
                </Button>
            </section>
        </div>
    );
}
