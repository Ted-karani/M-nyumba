// Import the React tools we need
import { useEffect, useState } from 'react'
// Import the page-switching tool that shows the page inside
import { Outlet } from 'react-router-dom'
// Import the icons we use
import { Loader2, ShieldAlert } from 'lucide-react'
// Import our own files
import { getTwoStep } from '../api'
import TwoStepCard from './TwoStepCard'

// A gate around the admin pages: 2-step login must be on first
export default function AdminGate() {
  // Whether 2-step login is on (nothing until we know)
  const [on, setOn] = useState(null)
  // The error message, if we could not find out
  const [error, setError] = useState('')

  // Find out whether 2-step login is on
  function check() {
    getTwoStep()
      .then((result) => setOn(result.enabled))
      .catch((err) => setError(err.message))
  }

  // Check when the gate first appears
  useEffect(() => {
    check()
  }, [])

  if (error) return <p className="rounded-2xl bg-terracotta/10 p-4 text-terracotta">{error}</p>
  if (on === null) {
    return (
      <div className="flex justify-center py-20 text-forest-700">
        <Loader2 className="animate-spin" size={28} />
      </div>
    )
  }
  // 2-step login is off: ask for it before showing anything
  if (!on) {
    return (
      <div className="mx-auto max-w-xl">
        <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-gold/25 text-forest-900">
          <ShieldAlert size={26} />
        </div>
        <h1 className="mt-4 text-3xl font-extrabold text-forest-900">Turn on 2-step login first</h1>
        <p className="mt-1 text-muted">
          The admin account can reset other people's passwords, so it must be the best protected account you have. Set up 2-step login below, save the recovery codes, and then continue.
        </p>
        <TwoStepCard />
        <button onClick={check} className="mt-5 w-full rounded-xl bg-forest-900 py-3.5 font-semibold text-white hover:bg-forest-700">
          I turned it on: continue
        </button>
      </div>
    )
  }
  // 2-step login is on: show the admin pages
  return <Outlet />
}