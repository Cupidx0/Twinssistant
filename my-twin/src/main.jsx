import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { ThemeProvider, createTheme } from '@mui/material/styles'
import { AuthProvider } from './pages/AuthContext.jsx'
import './index.css'
import App from './App.jsx'

// Keep MUI components on the Ember palette instead of MUI's default blue
const theme = createTheme({
  palette: {
    mode: 'dark',
    primary: { main: 'hsl(24, 88%, 60%)', contrastText: 'hsl(20, 40%, 8%)' },
    secondary: { main: 'hsl(40, 82%, 62%)' },
    error: { main: 'hsl(0, 60%, 55%)' },
    background: { default: 'hsl(20, 14%, 7%)', paper: 'hsl(22, 12%, 11%)' },
    text: { primary: 'hsl(32, 24%, 92%)', secondary: 'hsl(28, 8%, 62%)' },
  },
  shape: { borderRadius: 12 },
  typography: { fontFamily: 'system-ui, Avenir, Helvetica, Arial, sans-serif' },
})

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <ThemeProvider theme={theme}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </ThemeProvider>
  </StrictMode>,
)
