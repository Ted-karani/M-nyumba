// Import the React tools we need
import { useEffect, useState } from 'react'
// Import the animation tools
import { AnimatePresence, motion } from 'framer-motion'
// Import the icons we use
import { CalendarPlus, CheckCircle2, ChevronDown, ChevronUp, Loader2 } from 'lucide-react'
// Import our own files
import { generateRent, getRentPreview } from '../api'
import { currentPeriod, money, monthLabel } from '../format'

// Write a month in short form: "2026-09" becomes "Sep 2026"
function shortMonth(period) {
  // Split "2026-09" into the year and the month number
  const [year, month] = period.split('-').map(Number)
  return new Date(year, month - 1, 1).toLocaleDateString('en-GB', { month: 'short', year: 'numeric' })
}

// The card on the dashboard that offers to add this month's rent for everyone
export default function RentBanner({ onDone }) {
  // What rent is waiting to be added (nothing until it arrives)
  const [preview, setPreview] = useState(null)
  // Whether the list of tenants is open
  const [open, setOpen] = useState(false)
  // True while we wait for the backend
  const [busy, setBusy] = useState(false)
  // The error message to show (empty means none)
  const [error, setError] = useState('')
  // What was added (shown after the button is pressed)
  const [done, setDone] = useState(null)

  // Ask the backend what is waiting when the card first appears
  useEffect(() => {
    getRentPreview()
      .then(setPreview)
      // If this fails, we simply show nothing
      .catch(() => setPreview(null))
  }, [])

  // Run when the button is pressed
  async function handleGenerate() {
    // Clear any old error and show the loading state
    setError('')
    setBusy(true)
    try {
      // Add the rent charges
      const result = await generateRent()
      // Show the success message and hide the offer
      setDone(result)
      setPreview(null)
      // Tell the dashboard to reload its numbers
      onDone()
    } catch (err) {
      // Show why it failed
      setError(err.message)
    } finally {
      // Stop the loading state
      setBusy(false)
    }
  }

  // After adding, show a short success message
  if (done) {
    return (
      <motion.div
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        className="mb-6 flex items-center gap-3 rounded-2xl bg-forest-100 p-4 text-forest-700"
      >
        <CheckCircle2 size={22} className="shrink-0" />
        <p className="text-sm font-medium">
          {done.created_count === 0
            ? 'Nothing to add. Rent was already up to date.'
            : `Added ${done.created_count} rent charge${done.created_count === 1 ? '' : 's'} for ${done.lease_count} tenant${
                done.lease_count === 1 ? '' : 's'
              } (${money(done.total_amount)}).`}
        </p>
      </motion.div>
    )
  }

  // If nothing is waiting, show nothing at all
  if (!preview || preview.charge_count === 0) return null

  return (
    <motion.div
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      className="mb-6 rounded-3xl border border-gold/50 bg-gold/10 p-5"
    >
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-start gap-3">
          <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-gold text-forest-900">
            <CalendarPlus size={22} />
          </span>
          <div>
            <p className="font-display text-lg font-bold text-forest-900">
              Rent for {monthLabel(currentPeriod())} is ready to add
            </p>
            <p className="text-sm text-muted">
              {preview.lease_count} tenant{preview.lease_count === 1 ? '' : 's'} · {preview.charge_count} charge
              {preview.charge_count === 1 ? '' : 's'} · {money(preview.total_amount)}
            </p>
          </div>
        </div>
        <motion.button
          whileTap={{ scale: 0.97 }}
          onClick={handleGenerate}
          disabled={busy}
          className="flex shrink-0 items-center justify-center gap-2 rounded-xl bg-forest-900 px-5 py-3 text-sm font-semibold text-white shadow-lg shadow-forest-900/20 hover:bg-forest-700 disabled:opacity-70"
        >
          {busy && <Loader2 size={16} className="animate-spin" />}
          Add rent charges
        </motion.button>
      </div>

      {/* The button that opens and closes the list of tenants */}
      <button
        onClick={() => setOpen(!open)}
        className="mt-3 flex items-center gap-1 text-sm font-medium text-forest-700 hover:underline"
      >
        {open ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        {open ? 'Hide who is included' : 'Show who is included'}
      </button>

      {/* The list of tenants, sliding open */}
      <AnimatePresence initial={false}>
        {open && (
          <motion.ul
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="mt-3 divide-y divide-gold/30 overflow-hidden rounded-2xl bg-paper"
          >
            {preview.items.map((item) => (
              <li key={item.lease_id} className="flex items-center justify-between gap-3 px-4 py-3">
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold text-forest-900">{item.tenant_name}</p>
                  <p className="truncate text-xs text-muted">
                    {item.unit_number} · {item.property_name}
                  </p>
                  <p className="truncate text-xs text-muted">{item.periods.map(shortMonth).join(', ')}</p>
                </div>
                <p className="text-sm font-semibold text-forest-900">{money(item.amount)}</p>
              </li>
            ))}
          </motion.ul>
        )}
      </AnimatePresence>

      {/* The error appears here if something goes wrong */}
      {error && (
        <div role="alert" className="mt-3 rounded-xl bg-terracotta/10 px-4 py-3 text-sm font-medium text-terracotta">
          {error}
        </div>
      )}
    </motion.div>
  )
}