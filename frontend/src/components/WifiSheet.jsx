// Import the React tools we need
import { useCallback, useEffect, useState } from 'react'
// Import the animation tool
import { motion } from 'framer-motion'
// Import the icons we use
import { Check, Loader2, RefreshCw } from 'lucide-react'
// Import our own files
import { billWifi, getWifiSheet } from '../api'
import { money } from '../format'
import { Field, inputClass } from './Field'

// A date a few days from today, written like "2026-10-21" (used as the starting due date)
function inDays(days) {
  // Start from today and move forward
  const date = new Date()
  date.setDate(date.getDate() + days)
  // Month and day need a zero in front when they are a single digit
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${date.getFullYear()}-${month}-${day}`
}

// The Wi-Fi sheet: one flat fee for the units you tick
export default function WifiSheet({ propertyId, period }) {
  // The sheet from the backend (nothing until it arrives)
  const [sheet, setSheet] = useState(null)
  // The error message if the sheet could not load
  const [loadError, setLoadError] = useState('')
  // The flat fee (starting from the last one we remembered)
  const [amount, setAmount] = useState(() => {
    try {
      return localStorage.getItem('mnyumba_rate_wifi') || ''
    } catch {
      return ''
    }
  })
  // The date the money is due
  const [dueDate, setDueDate] = useState(inDays(7))
  // The units the person has switched OFF (everyone starts ticked)
  const [unticked, setUnticked] = useState({})
  // True while we wait for the backend
  const [busy, setBusy] = useState(false)
  // The error and success messages under the sheet
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  // Load the sheet from the backend
  const load = useCallback(() => {
    setLoadError('')
    getWifiSheet(propertyId, period)
      .then(setSheet)
      .catch((err) => setLoadError(err.message))
  }, [propertyId, period])

  // Load it when the sheet first appears
  useEffect(() => {
    load()
  }, [load])

  // If the sheet could not load, show the message and a retry button
  if (loadError) {
    return (
      <div className="mt-6 rounded-3xl bg-terracotta/10 p-6 text-terracotta">
        <p className="font-semibold">Could not load the sheet</p>
        <p className="mt-1 text-sm">{loadError}</p>
        <button onClick={load} className="mt-4 flex items-center gap-2 rounded-xl bg-terracotta px-4 py-2 text-sm font-semibold text-white">
          <RefreshCw size={16} /> Try again
        </button>
      </div>
    )
  }

  // While waiting, show grey placeholder boxes
  if (!sheet) {
    return (
      <div className="mt-6 space-y-3">
        <div className="h-16 animate-pulse rounded-2xl bg-forest-100" />
        <div className="h-16 animate-pulse rounded-2xl bg-forest-100" />
      </div>
    )
  }

  // If nobody lives in this property yet, say so
  if (sheet.rows.length === 0) {
    return (
      <div className="mt-6 rounded-3xl bg-paper p-10 text-center shadow-sm">
        <p className="font-semibold text-forest-900">No occupied units</p>
        <p className="mt-1 text-sm text-muted">Bills are only added for units that have a tenant living in them.</p>
      </div>
    )
  }

  // The units that will be charged: not already charged, and still ticked
  const chosen = sheet.rows.filter((row) => !row.already_charged && !unticked[row.unit_id])
  // The fee as a whole number
  const fee = Math.round(Number(amount))
  // Can we save?
  const canSave = chosen.length > 0 && fee > 0 && dueDate !== '' && !busy

  // Run when the charge button is pressed
  async function handleSave() {
    // Clear old messages and show the loading state
    setError('')
    setMessage('')
    setBusy(true)
    try {
      // Send the units to charge
      const result = await billWifi({
        property_id: Number(propertyId),
        period,
        amount: fee,
        due_date: dueDate,
        unit_ids: chosen.map((row) => row.unit_id),
      })
      // Remember the fee for next time
      try {
        localStorage.setItem('mnyumba_rate_wifi', String(fee))
      } catch {
        // Not being able to remember the fee is fine
      }
      // Say what happened, then reload the sheet
      setMessage(`Charged ${result.charged} tenant${result.charged === 1 ? '' : 's'} ${money(result.total_amount)}.`)
      load()
    } catch (err) {
      // Show why it failed
      setError(err.message)
    } finally {
      // Stop the loading state
      setBusy(false)
    }
  }

  return (
    <div className="mt-6">
      {/* The fee and due date */}
      <div className="grid grid-cols-2 gap-3">
        <Field label="Wi-Fi fee per unit (KSh)">
          <input
            className={inputClass}
            type="number"
            inputMode="numeric"
            min="1"
            step="1"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            placeholder="1500"
          />
        </Field>
        <Field label="Due date">
          <input className={inputClass} type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} />
        </Field>
      </div>

      {/* One row for each occupied unit, with a tick box */}
      <div className="mt-5 divide-y divide-forest-100 overflow-hidden rounded-2xl bg-paper shadow-sm">
        {sheet.rows.map((row) => {
          // Is this unit going to be charged?
          const ticked = !row.already_charged && !unticked[row.unit_id]
          return (
            <button
              key={row.unit_id}
              type="button"
              disabled={row.already_charged}
              onClick={() => setUnticked({ ...unticked, [row.unit_id]: ticked })}
              className="flex w-full items-center gap-4 p-4 text-left transition hover:bg-forest-100/50 disabled:cursor-default disabled:hover:bg-transparent"
            >
              {/* The tick box */}
              <span
                className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-lg border-2 transition ${
                  row.already_charged
                    ? 'border-forest-200 bg-forest-100 text-forest-500'
                    : ticked
                    ? 'border-forest-900 bg-forest-900 text-white'
                    : 'border-forest-200 bg-paper'
                }`}
              >
                {(ticked || row.already_charged) && <Check size={14} />}
              </span>
              <div className="min-w-0 flex-1">
                <p className="font-semibold text-forest-900">{row.unit_number}</p>
                <p className="truncate text-sm text-muted">{row.tenant_name}</p>
              </div>
              {row.already_charged && (
                <span className="rounded-full bg-forest-100 px-2.5 py-0.5 text-xs font-semibold text-forest-700">Charged</span>
              )}
            </button>
          )
        })}
      </div>

      {/* The success and error messages */}
      {message && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} role="status" className="mt-4 rounded-xl bg-forest-100 px-4 py-3 text-sm font-medium text-forest-700">
          {message}
        </motion.div>
      )}
      {error && (
        <div role="alert" className="mt-4 rounded-xl bg-terracotta/10 px-4 py-3 text-sm font-medium text-terracotta">
          {error}
        </div>
      )}

      {/* The charge button, with a summary of what it will do */}
      <motion.button
        whileTap={{ scale: 0.98 }}
        onClick={handleSave}
        disabled={!canSave}
        className="mt-5 flex w-full items-center justify-center gap-2 rounded-xl bg-forest-900 py-3.5 font-semibold text-white shadow-lg shadow-forest-900/20 transition hover:bg-forest-700 disabled:opacity-50"
      >
        {busy && <Loader2 size={18} className="animate-spin" />}
        {chosen.length === 0
          ? 'Nothing left to charge'
          : fee > 0
          ? `Charge ${chosen.length} tenant${chosen.length === 1 ? '' : 's'} ${money(fee * chosen.length)}`
          : 'Enter the Wi-Fi fee above'}
      </motion.button>
    </div>
  )
}