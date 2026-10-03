import React, { useState ,useRef, useEffect} from 'react';
import SpeechRecognition, { useSpeechRecognition } from "react-speech-recognition";
import { Card, CardContent, Typography, Button, TextField, Stack, Divider } from '@mui/material';
import toast, { Toaster } from 'react-hot-toast';
import { ChatAPI } from '../../Utils/Assistant';
import { useAuth } from '../AuthContext';
import { Link,replace } from 'react-router-dom';
import { Anchor, Delete, SmartToy, Inventory, MusicNote, Settings, CalendarMonth, Inventory2, Cloud, Upload, Work, Code, ArrowUpwardTwoTone } from '@mui/icons-material';
import { io } from "socket.io-client";
const WS_URL = import.meta.env.VITE_AI_SPEECH_WS_URL || "http://localhost:5000";
export default function Notepad() {
    const [transcript, setTranscript] = useState('');
    const [noteContent, setNoteContent] = useState('');
    const [noteTitle, setNoteTitle] = useState('');
    const [isRecording, setIsRecording] = useState(false);
    const socketRef = useRef(null);
    const mediaStreamRef = useRef(null);
    const audioContextRef = useRef(null);
    const processorRef = useRef(null);
    const { isLoggedIn, user } = useAuth();

    useEffect(() => {
        if (!user) return;
        let newSocket;

        (async () => {
            const token = await user.getIdToken();
            newSocket = io(WS_URL, {
                transports: ['websocket'],
                auth: { token }
            });
            socketRef.current = newSocket;

            newSocket.on('connect', () => console.log('Connected to WebSocket server'));
            newSocket.on('disconnect', () => console.log('Disconnected from WebSocket server'));
            newSocket.on('transcript_response', (data) => {
                if (data.type === 'done') {
                    setTranscript(data.transcript || '');
                    setNoteContent(data.transcript || '');
                    setNoteTitle(data.title || 'Untitled');
                    toast.success("Transcription completed.");
                }
            });
        })();

        return () => {
            if (newSocket) {
                newSocket.off('transcript_response');
                newSocket.disconnect();
            }
        };
    }, [user]);

    function floatTo16BitPCM(float32Array) {
        const pcm16 = new Int16Array(float32Array.length);
        for (let i = 0; i < float32Array.length; i++) {
            const s = Math.max(-1, Math.min(1, float32Array[i]));
            pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
        }
        return pcm16;
    }

    function arrayBufferToBase64(buffer) {
        let binary = '';
        const bytes = new Uint8Array(buffer);
        for (let i = 0; i < bytes.byteLength; i++) {
            binary += String.fromCharCode(bytes[i]);
        }
        return window.btoa(binary);
    }

    const handleStartRecording = () => {
        if (!isLoggedIn) {
            toast.error("Please log in to use the live transcription feature.");
            return;
        }
        setIsRecording(true);
        startLiveTranscription();
    };

    const handleStopRecording = () => {
        setIsRecording(false);
        stopLiveTranscription();
    };

    const startLiveTranscription = async () => {
        if (!socketRef.current) return;
        try {
            socketRef.current.emit('start_live_transcription', { userId: user.uid });
            const mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
            const audioContext = new AudioContext({ sampleRate: 24000 });
            const source = audioContext.createMediaStreamSource(mediaStream);
            const processor = audioContext.createScriptProcessor(4096, 1, 1);

            source.connect(processor);
            processor.connect(audioContext.destination);

            processor.onaudioprocess = (e) => {
                const float32 = e.inputBuffer.getChannelData(0);
                const pcm16 = floatTo16BitPCM(float32);
                const base64 = arrayBufferToBase64(pcm16.buffer);
                socketRef.current.emit('live_audio_chunk', { audio: base64 });
            };

            mediaStreamRef.current = mediaStream;
            audioContextRef.current = audioContext;
            processorRef.current = processor;
            toast.success("Live transcription started.");
        } catch (error) {
            console.error("Error starting live transcription:", error);
            toast.error("Failed to start live transcription.");
        }
    };

    const stopLiveTranscription = async () => {
        if (!socketRef.current) return;
        try {
            processorRef.current?.disconnect();
            audioContextRef.current?.close();
            mediaStreamRef.current?.getTracks().forEach(track => track.stop());

            socketRef.current.emit('stop_live_transcription', { userId: user.uid });
            toast.success("Live transcription stopped.");
        } catch (error) {
            console.error("Error stopping live transcription:", error);
            toast.error("Failed to stop live transcription.");
        }
    };
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
                <Button variant="contained" color="primary" onClick={handleStartRecording} disabled={isRecording} sx={{ mt: 2 }}>
                    {isRecording ? "Recording..." : "Start live transcription"}
                </Button>
                <Button variant="contained" color="secondary" onClick={handleStopRecording} disabled={!isRecording} sx={{ mt: 2, ml: 2 }}>
                    Stop live transcription
                </Button>
            </section>
        </div>
    );
}
