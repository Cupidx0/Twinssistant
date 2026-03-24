import React from 'react'
import Layout from './pages/Layout'
import Home from './pages/home'
import Error404 from './pages/Error'
import Login from './pages/Login'
import Register from './pages/Register'
import Weather_cv from './pages/page_connect/Weather_cv'
import './App.css'
import './index.css'
import { BrowserRouter as Router,Routes,Route } from 'react-router-dom'
function App() {
  return (
    <>
      <Router>
        <Routes>
          <Route path="/" element={<Layout />}>
            <Route index element={<Home />}/>
            <Route path="/cv" element={<Weather_cv />} />
            <Route path="/home" element={<Home />} />
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />
            <Route path="*" element={<Error404 />} />
          </Route>
        </Routes>
      </Router>
    </>
  )
}

export default App
