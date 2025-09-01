import React from 'react';
import { Login as LoginIcon,} from '@mui/icons-material';
import { Link } from 'react-router-dom';
import { TextField, Button, Box, Typography } from '@mui/material';
function Login () {
    return(
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
            <Typography variant="h4" gutterBottom>Login</Typography>
            <LoginIcon />
            <TextField label="Username" variant="outlined"
            inputProps={{ style: { color: 'white' } }}
            InputLabelProps={{ style: { color: 'white' } }}
             className="m-2 bg-gray-800" />
            <TextField label="Password" type="password" variant="filled"
            inputProps={{ style: { color: 'white'} }}
            InputLabelProps={{ style: { color: 'white' } }}
             className="m-2 bg-gray-800 border border-white text-white" />
            <Button variant="contained" color="primary" className="m-2">Login</Button>
            <Typography variant="body2">
                Don't have an account? <Link to="/register" className="text-blue-500">Register here</Link>
            </Typography>
            </Box>
        </div>
    );
}
export default Login;