// Import the page-switching tools
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
// Import the spinner icon
import { Loader2 } from 'lucide-react'
// Import our login information tools
import { AuthProvider, useAuth } from './AuthContext'
// Import our screens
import Layout from './components/Layout'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import ComingSoon from './pages/ComingSoon'

// Decide which screen to show
function Screens() {
  // Find out if we are still checking the saved token, and who is logged in
  const { user, loading } = useAuth()
  // While checking, show a spinner
  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center text-forest-700">
        <Loader2 className="animate-spin" size={32} />
      </div>
    )
  }
  // Not logged in? Show the login screen
  if (!user) return <Login />
  // Logged in: show the pages inside the menu frame
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="properties" element={<ComingSoon title="Properties" />} />
        <Route path="tenants" element={<ComingSoon title="Tenants" />} />
        <Route path="payments" element={<ComingSoon title="Payments" />} />
        {/* Any other address goes back to the dashboard */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}

// The main app: wrap everything so every screen can read the login information
export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Screens />
      </AuthProvider>
    </BrowserRouter>
  )
}