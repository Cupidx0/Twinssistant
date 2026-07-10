import React from 'react'
import Layout from './pages/Layout'
import Home from './pages/home'
import Error404 from './pages/Error'
import Login from './pages/Login'
import Register from './pages/Register'
import Settings from './pages/Settings'
import Weather_cv from './pages/page_connect/Weather_cv'
import AiSpeech from './pages/page_connect/ai_speech'
import './App.css'
import './index.css'
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'

function App() {
  return (
    <>
      <Router>
        <Toaster
          position="top-right"
          reverseOrder={false}
          toastOptions={{
            duration: 1500,
            style: {
              background: 'hsl(22, 12%, 11%)',
              color: 'hsl(32, 24%, 92%)',
              border: '1px solid hsl(24, 10%, 18%)',
            },
          }}
        />
        <Routes>
          {/* Full-screen surfaces (no header/footer chrome) */}
          <Route index element={<Home />} />
          <Route path="/home" element={<Home />} />
          <Route path="/speech" element={<AiSpeech />} />

          {/* Pages that keep the classic header/footer */}
          <Route path="/" element={<Layout />}>
            <Route path="/cv" element={<Weather_cv />} />
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="*" element={<Error404 />} />
          </Route>
        </Routes>
      </Router>
    </>
  )
}

export default App
