import React from 'react'
import { Box, Button, TextField, Typography } from '@mui/material';
import { Login as LoginIcon } from '@mui/icons-material';
import { Link } from 'react-router-dom';
function Register() {
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
                <Typography variant="h4" gutterBottom>Register</Typography>
                <LoginIcon />
                <TextField label="Username" variant="outlined"
                inputProps={{ style: { color: 'white' } }}
                InputLabelProps={{ style: { color: 'white' } }}
                 className="m-2 bg-gray-800" />
                <TextField label="Email" type="email" variant="filled"
                inputProps={{ style: { color: 'white' } }}
                InputLabelProps={{ style: { color: 'white' } }}
                className="m-2 bg-gray-800 border border-white text-white" />
                <TextField label="Password" type="password" variant="filled"
                inputProps={{ style: { color: 'white' } }}
                InputLabelProps={{ style: { color: 'white' } }}
                className="m-2 bg-gray-800 border border-white text-white" />
                <TextField label="Confirm Password" type="password" variant="filled"
                inputProps={{ style: { color: 'white' } }}
                InputLabelProps={{ style: { color: 'white' } }}
                className="m-2 bg-gray-800 border border-white text-white" />
                <Button variant="contained" color="primary" className="m-2">Register</Button>
                <Typography variant="body2">
                    Already have an account? <Link to="/login" className="text-blue-500">Login here</Link>
                </Typography>
            </Box>
        </div>
    );
}

export default Register;
