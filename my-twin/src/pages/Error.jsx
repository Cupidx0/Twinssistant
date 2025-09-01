import React from "react";
import { Box, Typography, Button } from "@mui/material";
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import SmartToyOutlinedIcon from '@mui/icons-material/SmartToyOutlined';
import { Link } from "react-router-dom";
function Error404 (){
    return(
       <Box
        sx={{
            minHeight: "100vh",
            minWidth: "100vw",
            bgcolor: "#0D0D0D", // Dark background
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            textAlign: "center",
            position: "relative",
            overflow: "hidden",
            color: "#E0E0E0",
            p: 2
        }}
        >
      {/* Floating sparkles */}
      {[...Array(15)].map((_, i) => (
        <AutoAwesomeIcon
          key={i}
          sx={{
            position: "absolute",
            top: `${Math.random() * 100}%`,
            left: `${Math.random() * 100}%`,
            fontSize: `${Math.random() * 20 + 10}px`,
            color: "#6366F1",
            opacity: 0.3,
            animation: "floatY 6s ease-in-out infinite",
          }}
        />
      ))}

      {/* Floating robot icon */}
      <SmartToyOutlinedIcon
        sx={{
          fontSize: 80,
          mb: 2,
          color: "#6366F1",
          animation: "floatY 3s ease-in-out infinite",
        }}
      />

      {/* Big error text */}
      <Typography
        variant="h1"
        sx={{ fontWeight: "bold", color: "#6366F1", fontSize: "6rem" }}
      >
        404
      </Typography>

      {/* Subtext */}
      <Typography variant="h6" sx={{ mb: 3, color: "#A0A0A0" }}>
        Looks like you wandered into the AI void...
      </Typography>

      {/* Back home button */}
      <Button
        component={Link}
        to="/"
        variant="contained"
        sx={{
          bgcolor: "#6366F1",
          ":hover": { bgcolor: "#3122FF" },
          borderRadius: 3,
          px: 3,
          py: 1.5,
        }}
      >
        Return Home
      </Button>

      {/* Floating animation keyframes */}
      <style>
        {`
          @keyframes floatY {
            0% { transform: translateY(0px); }
            50% { transform: translateY(-15px); }
            100% { transform: translateY(0px); }
          }
        `}
      </style>
    </Box> 
    );
}
export default Error404;