import React, { useState, useRef, useEffect } from 'react';
import { Button, TextField, Divider } from '@mui/material';
import toast from 'react-hot-toast';
import { useAuth } from '../AuthContext';
import { io } from "socket.io-client";
const WS_URL = import.meta.env.VITE_AI_SPEECH_WS_URL || "http://localhost:5050";
const storageKey = (uid) => `twin_notepad_${uid}`;

function loadNote(uid) {
    try {
        const saved = JSON.parse(localStorage.getItem(storageKey(uid)) || "null");
        return { title: saved?.title || "", content: saved?.content || "" };
    } catch {
        return { title: "", content: "" };
    }
}

export default function Notepad() {
    const [noteContent, setNoteContent] = useState('');
    const [noteTitle, setNoteTitle] = useState('');
    const [isRecording, setIsRecording] = useState(false);
    const [loadedFor, setLoadedFor] = useState(null);
    const socketRef = useRef(null);
    const mediaStreamRef = useRef(null);
    const audioContextRef = useRef(null);
    const processorRef = useRef(null);
    // Audio is only streamed once the server confirms the OpenAI session is open.
    const sessionReadyRef = useRef(false);
    const { isLoggedIn, user } = useAuth();

    // Load this user's saved note.
    useEffect(() => {
        if (!user) return;
        const saved = loadNote(user.uid);
        setNoteTitle(saved.title);
        setNoteContent(saved.content);
        setLoadedFor(user.uid);
    }, [user]);

    // Save on every change (only after the load above, so we don't overwrite it with blanks).
    useEffect(() => {
        if (!user || loadedFor !== user.uid) return;
        try {
            localStorage.setItem(storageKey(user.uid), JSON.stringify({ title: noteTitle, content: noteContent }));
        } catch {
            // Storage blocked/full: the note still works for this session.
        }
    }, [noteTitle, noteContent, user, loadedFor]);

    useEffect(() => {
        if (!user) return;
        let cancelled = false;
        let newSocket;

        (async () => {
            let token;
            try {
                token = await user.getIdToken();
            } catch (error) {
                console.error("Could not get auth token:", error);
                return;
            }
            // StrictMode / fast unmount: cleanup already ran, so don't create an orphan socket.
            if (cancelled) return;
            newSocket = io(WS_URL, {
                transports: ['websocket'],
                auth: { token }
            });
            socketRef.current = newSocket;

            newSocket.on('connect', () => console.log('Connected to WebSocket server'));
            newSocket.on('disconnect', () => {
                console.log('Disconnected from WebSocket server');
                sessionReadyRef.current = false;
                stopAudioCapture();
                setIsRecording(false);
            });
            newSocket.on('transcript_response', (data) => {
                if (data.type === 'started') {
                    sessionReadyRef.current = true;
                    // Keep a new recording separate from text already in the note.
                    setNoteContent(prev => (prev && !/\s$/.test(prev) ? prev + "\n" : prev));
                }
                else if (data.type === 'done') {
                    toast.success("Transcription completed.");
                }
                else if (data.type === 'delta') {
                    setNoteContent(prev => prev + data.delta);
                }
                else if (data.type === 'error') {
                    toast.error(`Error: ${data.error}`);
                    sessionReadyRef.current = false;
                    stopAudioCapture();
                    setIsRecording(false);
                }
            });
        })();

        return () => {
            cancelled = true;
            sessionReadyRef.current = false;
            stopAudioCapture();
            if (newSocket) {
                newSocket.off('transcript_response');
                newSocket.disconnect(); // server closes the OpenAI session on disconnect
            }
            if (socketRef.current === newSocket) socketRef.current = null;
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

    function stopAudioCapture() {
        if (processorRef.current) processorRef.current.onaudioprocess = null;
        processorRef.current?.disconnect();
        audioContextRef.current?.close().catch(() => {});
        mediaStreamRef.current?.getTracks().forEach(track => track.stop());
        processorRef.current = null;
        audioContextRef.current = null;
        mediaStreamRef.current = null;
    }

    const handleStartRecording = () => {
        if (!isLoggedIn) {
            toast.error("Please log in to use the live transcription feature.");
            return;
        }
        if (!socketRef.current?.connected) {
            toast.error("Not connected to the server yet. Try again in a moment.");
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
            sessionReadyRef.current = false;
            // Ask for the mic first so a denied permission never opens a server session.
            const mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
            mediaStreamRef.current = mediaStream;
            socketRef.current.emit('start_live_transcription', {});
            const audioContext = new AudioContext({ sampleRate: 24000 });
            const source = audioContext.createMediaStreamSource(mediaStream);
            const processor = audioContext.createScriptProcessor(4096, 1, 1);

            source.connect(processor);
            processor.connect(audioContext.destination);

            processor.onaudioprocess = (e) => {
                if (!sessionReadyRef.current || !socketRef.current) return;
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
            const sessionRequested = Boolean(mediaStreamRef.current);
            stopAudioCapture();
            setIsRecording(false);
            if (sessionRequested) socketRef.current?.emit('stop_live_transcription', {});
        }
    };
    const stopLiveTranscription = async () => {
        if (!socketRef.current) return;
        try {
            stopAudioCapture();
            sessionReadyRef.current = false;
            socketRef.current.emit('stop_live_transcription', {});
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
                <p className="text-sm text-gray-400 mt-1">
                    Your note is saved in this browser only. Live transcription sends your audio to OpenAI to convert it to text; it isn't stored on our server.
                </p>
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
