// Import React's strict mode helper, which catches common mistakes while we build
import { StrictMode } from 'react'
// Import the tool that puts React into the page
import { createRoot } from 'react-dom/client'
// Import our styles
import './index.css'
// Import the main app
import App from './App.jsx'

// Find the "root" box in index.html and draw our app inside it
createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)