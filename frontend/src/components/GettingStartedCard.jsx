// Import the React tools we need
import { useEffect, useState } from 'react'
// Import the page-switching tool
import { Link } from 'react-router-dom'
// Import the animation tool
import { motion } from 'framer-motion'
// Import the icons we use
import { ArrowRight, Rocket, X } from 'lucide-react'
// Import our own files
import { useAuth } from '../AuthContext'
import { getGettingStarted } from '../api'

// The card on a new landlord's dashboard. It shows only while the building, its units or a tenant are still missing.
export default function GettingStartedCard() {
  const { user } = useAuth()
  // The landlord can hide it (remembered on this device)
  const storageKey = `estateloom_gs_hidden_${user.id}`
  const [progress, setProgress] = useState(null)
  const [hidden, setHidden] = useState(() => {
    try {
      return localStorage.getItem(storageKey) === '1'
    } catch {
      return false
    }
  })

  // Load the checklist (if it fails, the card simply does not show)
  useEffect(() => {
    if (hidden) return
    getGettingStarted()
      .then(setProgress)
      .catch(() => setProgress(null))
  }, [hidden])

  // Hide the card
  function hide() {
    try {
      localStorage.setItem(storageKey, '1')
    } catch {
      // Not being able to remember it is fine
    }
    setHidden(true)
  }

  if (hidden || !progress || progress.core_done) return null
  // The next three things to do
  const next = progress.steps.filter((step) => !step.done).slice(0, 3)
  const percent = Math.round((progress.done_count / progress.total) * 100)

  return (
    <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="mb-6 rounded-3xl bg-forest-900 p-6 text-white shadow-xl">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-gold/25 text-gold">
            <Rocket size={22} />
          </div>
          <div>
            <h2 className="font-display text-xl font-bold">Let’s get you set up</h2>
            <p className="text-sm text-forest-200">
              {progress.done_count} of {progress.total} done
            </p>
          </div>
        </div>
        <button onClick={hide} aria-label="Hide this" className="rounded-lg p-1.5 text-forest-200 hover:bg-white/10 hover:text-white">
          <X size={18} />
        </button>
      </div>

      {/* A bar that fills as steps are done */}
      <div className="mt-4 h-2 overflow-hidden rounded-full bg-white/15">
        <motion.div className="h-full rounded-full bg-gold" initial={{ width: 0 }} animate={{ width: `${percent}%` }} transition={{ duration: 0.6 }} />
      </div>

      {/* What to do next */}
      <ul className="mt-4 space-y-2">
        {next.map((step) => (
          <li key={step.id}>
            <Link to={step.link} className="flex items-center justify-between gap-3 rounded-2xl bg-white/10 px-4 py-3 transition hover:bg-white/20">
              <span className="min-w-0">
                <span className="block text-sm font-semibold">{step.title}</span>
                <span className="block truncate text-xs text-forest-200">{step.description}</span>
              </span>
              <ArrowRight size={18} className="shrink-0 text-gold" />
            </Link>
          </li>
        ))}
      </ul>
      <Link to="/getting-started" className="mt-4 inline-block text-sm font-semibold text-gold hover:underline">
        See all the steps
      </Link>
    </motion.div>
  )
}