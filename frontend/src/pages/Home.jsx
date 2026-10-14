// Import the animation tool
import { motion } from 'framer-motion'
// Import the icons we use
import { LogOut, LayoutDashboard } from 'lucide-react'
// Import our login information
import { useAuth } from '../AuthContext'

// Pick a greeting based on the time of day
function greeting() {
  // The current hour, from 0 to 23
  const hour = new Date().getHours()
  if (hour < 12) return 'Good morning'
  if (hour < 17) return 'Good afternoon'
  return 'Good evening'
}

// The screen people see after logging in
export default function Home() {
  // Get the logged-in user and the logout function
  const { user, signOut } = useAuth()
  // Use only the first name in the greeting
  const firstName = user.full_name.split(' ')[0]

  return (
    <main className="mx-auto min-h-screen max-w-2xl px-6 py-10">
      {/* The top row: greeting on the left, logout on the right */}
      <div className="flex items-start justify-between">
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
          <p className="text-muted">{greeting()}</p>
          <h1 className="text-3xl font-extrabold text-forest-900">{firstName}</h1>
        </motion.div>
        <motion.button
          whileTap={{ scale: 0.95 }}
          onClick={signOut}
          className="flex items-center gap-2 rounded-xl bg-paper px-4 py-2 text-sm font-medium shadow-sm hover:bg-forest-100"
        >
          <LogOut size={16} /> Log out
        </motion.button>
      </div>

      {/* A card that says the dashboard is coming */}
      <motion.div
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.15 }}
        className="mt-8 rounded-3xl bg-forest-900 p-6 text-white shadow-xl"
      >
        <div className="flex items-center gap-2 text-forest-200">
          <LayoutDashboard size={18} />
          <span className="text-sm">You are logged in as {user.role}</span>
        </div>
        <p className="mt-3 font-display text-2xl font-bold">Your dashboard is coming next.</p>
        <p className="mt-1 text-sm text-forest-200">{user.email}</p>
      </motion.div>
    </main>
  )
}