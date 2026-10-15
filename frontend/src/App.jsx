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
import Properties from './pages/Properties'
import PropertyDetail from './pages/PropertyDetail'
import Tenants from './pages/Tenants'
import TenantDetail from './pages/TenantDetail'
import Bills from './pages/Bills'
import Payments from './pages/Payments'
import Repairs from './pages/Repairs'

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
        <Route path="properties" element={<Properties />} />
        <Route path="properties/:id" element={<PropertyDetail />} />
        <Route path="tenants" element={<Tenants />} />
        <Route path="tenants/:id" element={<TenantDetail />} />
        <Route path="bills" element={<Bills />} />
        <Route path="payments" element={<Payments />} />
        <Route path="repairs" element={<Repairs />} />
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