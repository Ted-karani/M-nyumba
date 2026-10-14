// Import the spinner icon
import { Loader2 } from 'lucide-react'
// Import our login information tools
import { AuthProvider, useAuth } from './AuthContext'
// Import our two screens
import Login from './pages/Login'
import Home from './pages/Home'

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
  // Logged in? Show the home screen. Otherwise show login.
  return user ? <Home /> : <Login />
}

// The main app: wrap everything so every screen can read the login information
export default function App() {
  return (
    <AuthProvider>
      <Screens />
    </AuthProvider>
  )
}