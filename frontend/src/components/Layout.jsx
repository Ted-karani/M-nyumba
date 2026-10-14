// Import the page-switching tools
import { NavLink, Outlet, useLocation } from 'react-router-dom'
// Import the animation tool
import { motion } from 'framer-motion'
// Import the icons we use
import { Building2, LayoutDashboard, LogOut, Users, Wallet } from 'lucide-react'
// Import our login information
import { useAuth } from '../AuthContext'

// The pages in the menu
const NAV_ITEMS = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/properties', label: 'Properties', icon: Building2 },
  { to: '/tenants', label: 'Tenants', icon: Users },
  { to: '/payments', label: 'Payments', icon: Wallet },
]

// The frame around every screen: sidebar on desktop, bottom bar on phones
export default function Layout() {
  // Get the logged-in user and the logout function
  const { user, signOut } = useAuth()
  // Know which page we are on, so we can animate when it changes
  const location = useLocation()

  return (
    <div className="min-h-screen lg:flex">
      {/* The desktop sidebar (hidden on phones) */}
      <aside className="sticky top-0 hidden h-screen w-64 flex-col justify-between bg-forest-900 p-6 text-white lg:flex">
        <div>
          {/* The logo */}
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-gold text-forest-900">
              <Building2 size={20} />
            </div>
            <span className="font-display text-xl font-bold">M-nyumba</span>
          </div>
          {/* The menu links */}
          <nav className="mt-10 space-y-1">
            {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
              <NavLink
                key={to}
                to={to}
                end={to === '/'}
                className={({ isActive }) =>
                  `relative flex items-center gap-3 rounded-xl px-4 py-3 text-sm font-medium transition ${
                    isActive ? 'text-white' : 'text-forest-200 hover:text-white'
                  }`
                }
              >
                {({ isActive }) => (
                  <>
                    {/* The highlight slides between menu items */}
                    {isActive && (
                      <motion.span
                        layoutId="sidebar-pill"
                        className="absolute inset-0 rounded-xl bg-forest-700"
                        transition={{ type: 'spring', stiffness: 400, damping: 32 }}
                      />
                    )}
                    <Icon size={18} className="relative" />
                    <span className="relative">{label}</span>
                  </>
                )}
              </NavLink>
            ))}
          </nav>
        </div>
        {/* The user and the logout button */}
        <div>
          <p className="truncate text-sm font-semibold">{user.full_name}</p>
          <p className="truncate text-xs text-forest-200">{user.email}</p>
          <motion.button
            whileTap={{ scale: 0.97 }}
            onClick={signOut}
            className="mt-4 flex w-full items-center gap-2 rounded-xl bg-white/10 px-4 py-2.5 text-sm font-medium hover:bg-white/20"
          >
            <LogOut size={16} /> Log out
          </motion.button>
        </div>
      </aside>

      {/* The main area */}
      <div className="min-w-0 flex-1">
        {/* The top bar on phones: logo and logout */}
        <header className="flex items-center justify-between px-5 pt-5 lg:hidden">
          <div className="flex items-center gap-2">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-forest-900 text-gold">
              <Building2 size={18} />
            </div>
            <span className="font-display text-lg font-bold text-forest-900">M-nyumba</span>
          </div>
          <motion.button
            whileTap={{ scale: 0.92 }}
            onClick={signOut}
            aria-label="Log out"
            className="rounded-xl bg-paper p-2.5 text-forest-700 shadow-sm"
          >
            <LogOut size={18} />
          </motion.button>
        </header>

        {/* The page itself, which fades in each time you switch pages */}
        <main className="mx-auto max-w-5xl px-5 pb-28 pt-5 lg:px-10 lg:pb-10 lg:pt-10">
          <motion.div
            key={location.pathname}
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35 }}
          >
            <Outlet />
          </motion.div>
        </main>
      </div>

      {/* The bottom bar on phones (hidden on desktop) */}
      <nav className="fixed inset-x-0 bottom-0 z-10 border-t border-forest-100 bg-paper/95 px-2 pb-[env(safe-area-inset-bottom)] backdrop-blur lg:hidden">
        <div className="flex">
          {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                `relative flex flex-1 flex-col items-center gap-1 py-3 text-[11px] font-medium transition ${
                  isActive ? 'text-forest-900' : 'text-muted'
                }`
              }
            >
              {({ isActive }) => (
                <>
                  {/* A small green line slides above the active item */}
                  {isActive && (
                    <motion.span
                      layoutId="bottom-pill"
                      className="absolute top-0 h-1 w-10 rounded-b-full bg-forest-500"
                      transition={{ type: 'spring', stiffness: 400, damping: 32 }}
                    />
                  )}
                  <Icon size={21} />
                  {label}
                </>
              )}
            </NavLink>
          ))}
        </div>
      </nav>
    </div>
  )
}