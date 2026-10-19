// Import the page-switching tools
import { BrowserRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom'
// Import the spinner icon
import { Loader2 } from 'lucide-react'
// Import our login information tools
import { AuthProvider, useAuth } from './AuthContext'
// Import our screens
import Layout from './components/Layout'
import TenantGate from './components/TenantGate'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Properties from './pages/Properties'
import PropertyDetail from './pages/PropertyDetail'
import Tenants from './pages/Tenants'
import TenantDetail from './pages/TenantDetail'
import Bills from './pages/Bills'
import Payments from './pages/Payments'
import Repairs from './pages/Repairs'
import Team from './pages/Team'
import Work from './pages/Work'
import Setup from './pages/Setup'
import More from './pages/More'
import Owing from './pages/Owing'
import Expenses from './pages/Expenses'
import Reports from './pages/Reports'
import Documents from './pages/Documents'
import Tasks from './pages/Tasks'
import Inspection from './pages/Inspection'
import Account from './pages/Account'
import Activity from './pages/Activity'
import Listings from './pages/Listings'
import PublicListing from './pages/PublicListing'
import Notices from './pages/Notices'
import PortalAccess from './pages/PortalAccess'
import PortalHome from './pages/PortalHome'
import PortalRepairs from './pages/PortalRepairs'
import PortalNotices from './pages/PortalNotices'
import PortalAccount from './pages/PortalAccount'

// Decide which screen to show
function Screens() {
  // Know which address we are on
  const location = useLocation()
  // Find out if we are still checking the saved token, and who is logged in
  const { user, loading } = useAuth()

  // Public listing pages are for anyone, so they never ask for a login
  if (location.pathname.startsWith('/l/')) {
    return (
      <Routes>
        <Route path="/l/:token" element={<PublicListing />} />
      </Routes>
    )
  }

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

  // A tenant gets the portal (after choosing their own password if they still have a temporary one)
  if (user.role === 'tenant') {
    return (
      <Routes>
        <Route element={<TenantGate />}>
          <Route element={<Layout />}>
            <Route index element={<PortalHome />} />
            <Route path="repairs" element={<PortalRepairs />} />
            <Route path="notices" element={<PortalNotices />} />
            <Route path="account" element={<PortalAccount />} />
            {/* Any other address goes back to the tenant home */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Route>
      </Routes>
    )
  }

  // A caretaker gets their home screen, repairs, the checklists, and their account
  if (user.role === 'caretaker') {
    return (
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Work />} />
          <Route path="repairs" element={<Repairs />} />
          <Route path="leases/:leaseId/inspection/:kind" element={<Inspection />} />
          <Route path="account" element={<Account />} />
          {/* Any other address goes back to the caretaker home */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    )
  }

  // An owner gets everything
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="properties" element={<Properties />} />
        <Route path="properties/:id" element={<PropertyDetail />} />
        <Route path="tenants" element={<Tenants />} />
        <Route path="tenants/:id" element={<TenantDetail />} />
        <Route path="leases/:leaseId/inspection/:kind" element={<Inspection />} />
        <Route path="payments" element={<Payments />} />
        <Route path="more" element={<More />} />
        <Route path="owing" element={<Owing />} />
        <Route path="listings" element={<Listings />} />
        <Route path="notices" element={<Notices />} />
        <Route path="portal-access" element={<PortalAccess />} />
        <Route path="bills" element={<Bills />} />
        <Route path="repairs" element={<Repairs />} />
        <Route path="expenses" element={<Expenses />} />
        <Route path="reports" element={<Reports />} />
        <Route path="documents" element={<Documents />} />
        <Route path="tasks" element={<Tasks />} />
        <Route path="team" element={<Team />} />
        <Route path="activity" element={<Activity />} />
        <Route path="setup" element={<Setup />} />
        <Route path="account" element={<Account />} />
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