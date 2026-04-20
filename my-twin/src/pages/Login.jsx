import React,{useState} from 'react';
import { Login as LoginIcon,} from '@mui/icons-material';
import { Link ,useNavigate} from 'react-router-dom';
import { TextField, Button, Box, Typography } from '@mui/material';
import {auth,db} from '../Utils/Firebase';
import { collection, addDoc } from "firebase/firestore";
import { signInWithEmailAndPassword } from 'firebase/auth';
function Login () {
    const[Email,setEmail]=useState("");
    const[Password,setPassword]=useState("");
    const[error,setError]=useState("");
    const navigate = useNavigate();
    const handleLogin = async (e) => {
        e.preventDefault();
        setError("");
        if (!Email || !Password) {
            setError("All fields are required");
            return;
        }else if (Password.length < 6) {
            setError("Password must be at least 6 characters");
            return;
        }
        try {
            const userCredential = await signInWithEmailAndPassword(auth, Email, Password);
            const user = userCredential.user;
            await addDoc(collection(db, "logins"), {
                email: Email,
                timestamp: new Date()
            });
            console.log('Logged in:', user);
            navigate("/home");
            toast.success("Login successful!");
            setEmail("");
            setPassword("");
        } catch (error) {
            let msg =error.message.replace("Firebase: ","").replace("(auth/","").replace(").","");
            setError(msg);
            console.error("Registration error:", msg);
            setError("Login failed: " + msg);
            toast.error("Login failed: " + msg);
        }
    };
    return(
        <div>
            <Box
            display="flex" 
            flexDirection="column" 
            alignItems="center" 
            justifyContent="center" 
            className="bg-background text-foreground p-4 w-screen box-border border border-border/50"
            minHeight="100vh"
            gap={2}
            >
            <Typography variant="h4" gutterBottom>Login</Typography>
            <LoginIcon />
            <form onSubmit={handleLogin} className="flex flex-col items-center gap-2">
                {error && <Typography color="error">{error}</Typography>}
                <TextField label="Username" variant="outlined"
                value={Email}
                onChange={(e)=>setEmail(e.target.value)}
                inputProps={{ style: { color: 'white' } }}
                InputLabelProps={{ style: { color: 'white' } }}
                className="m-2 bg-input" />
                <TextField label="Password" type="password" variant="filled"
                value={Password}
                onChange={(e)=>setPassword(e.target.value)}
                inputProps={{ style: { color: 'white'} }}
                InputLabelProps={{ style: { color: 'white' } }}
                className="m-2 bg-input border border-border/50 text-foreground" />
                <Button variant="contained"
                type='submit' color="primary" className="m-2">Login</Button>
                <Typography variant="body2">
                    Don't have an account? <Link to="/register" className="text-primary">Register here</Link>
                </Typography>
            </form>
            </Box>
        </div>
    );
}
export default Login;
