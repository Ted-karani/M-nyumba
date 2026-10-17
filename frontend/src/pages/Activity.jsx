// Import the React tools we need
import { useCallback, useEffect, useState } from 'react'
// Import the animation tool
import { motion } from 'framer-motion'
// Import the icons we use
import { History, RefreshCw } from 'lucide-react'
// Import our own files
import { getActivity } from '../api'
import { initials } from '../format'
import { inputClass } from '../components/Field'

// The time ranges we offer
const RANGES = [
  { days: 1, label: 'Today' },
  { days: 7, label: '7 days' },
  { days: 30, label: '30 days' },
]

// Read a time from the backend (it saves times in UTC without a "Z" on the end, so we add it)
const parseTime = (value) => new Date(value.endsWith('Z') ? value : `${value}Z`)

// The page that shows who did what, and when
export default function Activity() {
  // The filters: how many days back, and which person
  const [days, setDays] = useState(7)
  const [actorId, setActorId] = useState('')
  // The log from the backend (nothing until it arrives)
  const [report, setReport] = useState(null)
  // The error message, if loading failed
  const [error, setError] = useState('')

  // Load the log (called again when a filter changes)
  const load = useCallback(() => {
    setError('')
    getActivity({ days, actor_id: actorId })
      .then(setReport)
      .catch((err) => setError(err.message))
  }, [days, actorId])

  // Load it when the page opens or a filter changes
  useEffect(() => {
    load()
  }, [load])

  // Put the entries into groups, one group for each day
  const groups = []
  if (report) {
    report.items.forEach((item) => {
      const time = parseTime(item.created_at)
      // The day, written out nicely
      const label = time.toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long' })
      const last = groups[groups.length - 1]
      if (last && last.label === label) last.items.push(item)
      else groups.push({ label, items: [item] })
    })
  }

  return (
    <div>
      {/* The title */}
      <h1 className="text-3xl font-extrabold text-forest-900">Activity log</h1>
      <p className="text-muted">Who changed what, and when. This list cannot be edited.</p>

      {/* The filters */}
      <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="flex gap-2">
          {RANGES.map((range) => (
            <button
              key={range.days}
              onClick={() => setDays(range.days)}
              className={`rounded-full px-4 py-2 text-sm font-semibold transition ${
                days === range.days ? 'bg-forest-900 text-white' : 'bg-paper text-forest-700 hover:bg-forest-100'
              }`}
            >
              {range.label}
            </button>
          ))}
        </div>
        {report && report.people.length > 1 && (
          <select value={actorId} onChange={(e) => setActorId(e.target.value)} className={`${inputClass} sm:w-56`} aria-label="Filter by person">
            <option value="">Everyone</option>
            {report.people.map((person) => (
              <option key={person.id} value={person.id}>
                {person.name}
              </option>
            ))}
          </select>
        )}
      </div>

      {/* If loading failed, show the message and a retry button */}
      {error && (
        <div className="mt-6 rounded-3xl bg-terracotta/10 p-6 text-terracotta">
          <p className="font-semibold">Could not load the activity log</p>
          <p className="mt-1 text-sm">{error}</p>
          <button onClick={load} className="mt-4 flex items-center gap-2 rounded-xl bg-terracotta px-4 py-2 text-sm font-semibold text-white">
            <RefreshCw size={16} /> Try again
          </button>
        </div>
      )}

      {/* While waiting, show grey placeholder boxes */}
      {!error && !report && (
        <div className="mt-6 space-y-3">
          <div className="h-16 animate-pulse rounded-2xl bg-forest-100" />
          <div className="h-16 animate-pulse rounded-2xl bg-forest-100" />
        </div>
      )}

      {/* If there is nothing in this time range, say so */}
      {report && report.items.length === 0 && (
        <div className="mt-6 flex flex-col items-center rounded-3xl bg-paper p-10 text-center shadow-sm">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-forest-100 text-forest-700">
            <History size={26} />
          </div>
          <p className="mt-4 font-semibold text-forest-900">Nothing to show</p>
          <p className="mt-1 text-sm text-muted">No activity in this time range.</p>
        </div>
      )}

      {/* The entries, grouped by day */}
      {groups.map((group) => (
        <div key={group.label} className="mt-6">
          <p className="mb-2 px-1 text-sm font-bold text-forest-900">{group.label}</p>
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="divide-y divide-forest-100 overflow-hidden rounded-2xl bg-paper shadow-sm">
            {group.items.map((item) => (
              <div key={item.id} className="flex items-center gap-3 p-4">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-forest-100 text-sm font-bold text-forest-700">
                  {initials(item.actor_name)}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-sm text-forest-900">
                    <span className="font-semibold">{item.actor_name}</span>
                    {item.actor_role === 'caretaker' && (
                      <span className="ml-2 rounded-full bg-gold/25 px-2 py-0.5 text-xs font-semibold text-forest-900">Caretaker</span>
                    )}
                  </p>
                  <p className="text-sm text-ink/80">{item.summary}</p>
                  {item.summary === 'Signed in' && item.ip && <p className="text-xs text-muted">from {item.ip}</p>}
                </div>
                <p className="shrink-0 text-xs text-muted">
                  {parseTime(item.created_at).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })}
                </p>
              </div>
            ))}
          </motion.div>
        </div>
      ))}
      {report && report.items.length === 300 && (
        <p className="mt-4 text-center text-xs text-muted">Showing the latest 300 entries. Choose a shorter range or a person to see fewer.</p>
      )}
    </div>
  )
}