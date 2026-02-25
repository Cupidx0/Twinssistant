import React,{useState} from 'react'
import { Box, Button, TextField, Typography } from '@mui/material';
import { Login as LoginIcon } from '@mui/icons-material';
import { Link,useNavigate } from 'react-router-dom';
import {auth} from '../Utils/Firebase';
import { db } from '../Utils/Firebase';  
import { doc, setDoc } from "firebase/firestore";
import {createUserWithEmailAndPassword,} from 'firebase/auth';
import toast from 'react-hot-toast';
function Register() {
    const [username, setUsername] = useState("");
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [confirmPassword, setConfirmPassword] = useState("");
    const [error, setError] = useState("");
    const navigate = useNavigate();
    const handleRegister = async (e) => {
        e.preventDefault();
            setError("");
            if (!username || !email || !password || !confirmPassword) {
                setError("All fields are required");
                toast.error("All fields are required");
                return;
            }
            if (password !== confirmPassword) {
                setError("Passwords do not match");
                toast.error("Passwords do not match");
                return;
            }
            const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            if (!emailRegex.test(email)) {
                setError("Invalid email format");
                toast.error("Invalid email format");
                return;
            }
        try {
            const userCredential = await createUserWithEmailAndPassword(auth, email, password);
            const user = userCredential.user;
            await setDoc(doc(db, "users", user.uid), {
                username: username,
                email: email,
                createdAt: new Date()
            });
            console.log("Registered user:", userCredential.user.email);
            navigate("/home");
            toast.success("Registration successful!");
        } catch (error) {
            let msg =error.message.replace("Firebase: ","").replace("(auth/","").replace(").","");
            setError(msg);
            console.error("Registration error:", error);
            toast.error("Registration failed: " + msg);
        }
    };
    return (
        <div>
            <Box
                display="flex"
                flexDirection="column"
                alignItems="center"
                justifyContent="center"
                className="bg-black text-white p-4 w-screen box-border border border-white"
                minHeight="100vh"
                gap={2}
            >
                <form onSubmit={handleRegister} className="flex flex-col items-center gap-2">
                    <Typography variant="h4" gutterBottom>Register</Typography>
                    <LoginIcon />
                    <TextField label="Username"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    variant="outlined"
                    inputProps={{ style: { color: 'white' } }}
                    InputLabelProps={{ style: { color: 'white' } }}
                    className="m-2 bg-gray-800" />
                    <TextField label="Email" type="email"
                    value={email}
                    onChange={(e)=>setEmail(e.target.value)}
                    variant="filled"
                    inputProps={{ style: { color: 'white' } }}
                    InputLabelProps={{ style: { color: 'white' } }}
                    className="m-2 bg-gray-800 border border-white text-white" />
                    <TextField label="Password" type="password" variant="filled"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    inputProps={{ style: { color: 'white' } }}
                    InputLabelProps={{ style: { color: 'white' } }}
                    className="m-2 bg-gray-800 border border-white text-white" />
                    <TextField label="Confirm Password" type="password" variant="filled"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    inputProps={{ style: { color: 'white' } }}
                    InputLabelProps={{ style: { color: 'white' } }}
                    className="m-2 bg-gray-800 border border-white text-white" />
                    <Button variant="contained" color="primary" className="m-2"
                    type='submit'
                    >Register</Button>
                    <Typography variant="body2">
                        Already have an account? <Link to="/login" className="text-blue-500">Login here</Link>
                    </Typography>
                </form>
            {error && <Typography color="error">{error}</Typography>}
            </Box>
        </div>
    );
}

export default Register;
