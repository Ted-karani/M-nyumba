// Import the React tools we need
import { useCallback, useEffect, useState } from 'react'
// Import the animation tool
import { motion } from 'framer-motion'
// Import the icons we use
import { CheckCircle2, Loader2, RefreshCw, Undo2 } from 'lucide-react'
// Import our own files
import { billMeters, getMeterSheet, undoReading } from '../api'
import { money } from '../format'
import ConfirmDialog from './ConfirmDialog'
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

// Write a number with at most two decimals, like 12.5
const num = (value) => Number(value).toLocaleString('en-US', { maximumFractionDigits: 2 })

// The meter reading sheet for water or electricity
export default function MeterSheet({ propertyId, utility, period }) {
  // The name we remember the price under, so it does not need typing every month
  const rateKey = `mnyumba_rate_${utility}`
  // The word we show for this utility
  const label = utility === 'water' ? 'Water' : 'Electricity'
  // The sheet from the backend (nothing until it arrives)
  const [sheet, setSheet] = useState(null)
  // The error message if the sheet could not load
  const [loadError, setLoadError] = useState('')
  // The price per unit (starting from the last one we remembered)
  const [rate, setRate] = useState(() => {
    try {
      return localStorage.getItem(rateKey) || ''
    } catch {
      return ''
    }
  })
  // The date the money is due
  const [dueDate, setDueDate] = useState(inDays(7))
  // What has been typed in each reading box, kept by unit id
  const [inputs, setInputs] = useState({})
  // True while we wait for the backend
  const [busy, setBusy] = useState(false)
  // The error and success messages under the sheet
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  // The row chosen for undoing (nothing when closed)
  const [undoing, setUndoing] = useState(null)

  // Load the sheet from the backend
  const load = useCallback(() => {
    setLoadError('')
    getMeterSheet(propertyId, utility, period)
      .then(setSheet)
      .catch((err) => setLoadError(err.message))
  }, [propertyId, utility, period])

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
        <div className="h-24 animate-pulse rounded-2xl bg-forest-100" />
        <div className="h-24 animate-pulse rounded-2xl bg-forest-100" />
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

  // The price as a number
  const rateNumber = Number(rate)
  // Work out each typed reading: how much was used, and what it costs
  const entries = sheet.rows
    .filter((row) => row.reading_id === null && inputs[row.unit_id] !== undefined && inputs[row.unit_id] !== '')
    .map((row) => {
      const value = Number(inputs[row.unit_id])
      // With no earlier reading there is nothing to subtract
      const used = row.previous_reading === null ? null : Math.round((value - row.previous_reading) * 1000) / 1000
      return {
        row,
        value,
        used,
        amount: used !== null && used > 0 && rateNumber > 0 ? Math.round(used * rateNumber) : 0,
        tooLow: used !== null && used < 0,
      }
    })
  // Can we save?
  const hasTooLow = entries.some((entry) => entry.tooLow)
  const needsPrice = entries.some((entry) => entry.used !== null) && !(rateNumber > 0)
  const chargeTotal = entries.reduce((sum, entry) => sum + entry.amount, 0)
  const canSave = entries.length > 0 && !hasTooLow && !needsPrice && dueDate !== '' && !busy

  // Run when the save button is pressed
  async function handleSave() {
    // Clear old messages and show the loading state
    setError('')
    setMessage('')
    setBusy(true)
    try {
      // Send the readings
      const result = await billMeters({
        property_id: Number(propertyId),
        utility,
        period,
        rate_per_unit: rateNumber > 0 ? rateNumber : 0,
        due_date: dueDate,
        readings: entries.map((entry) => ({ unit_id: entry.row.unit_id, reading: entry.value })),
      })
      // Remember the price for next time
      try {
        if (rateNumber > 0) localStorage.setItem(rateKey, String(rateNumber))
      } catch {
        // Not being able to remember the price is fine
      }
      // Write a short summary of what happened
      const parts = []
      if (result.charged > 0) parts.push(`Charged ${result.charged} tenant${result.charged === 1 ? '' : 's'} ${money(result.total_amount)}`)
      if (result.baselines > 0) {
        parts.push(`${result.baselines} first reading${result.baselines === 1 ? '' : 's'} saved as the starting point (no charge)`)
      }
      if (parts.length === 0) parts.push('Readings saved. Nothing was used, so nothing was charged')
      setMessage(parts.join('. ') + '.')
      // Clear the boxes and reload the sheet
      setInputs({})
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
      {/* The price and due date */}
      <div className="grid grid-cols-2 gap-3">
        <Field label="Price per unit (KSh)">
          <input
            className={inputClass}
            type="number"
            inputMode="decimal"
            min="0"
            step="any"
            value={rate}
            onChange={(e) => setRate(e.target.value)}
            placeholder={utility === 'water' ? '150' : '25'}
          />
        </Field>
        <Field label="Due date">
          <input className={inputClass} type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} />
        </Field>
      </div>

      {/* One card for each occupied unit */}
      <div className="mt-5 space-y-3">
        {sheet.rows.map((row) => {
          // Is a reading already saved for this month?
          const saved = row.reading_id !== null
          // The live working for a typed reading
          const entry = entries.find((item) => item.row.unit_id === row.unit_id)
          return (
            <motion.div key={row.unit_id} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="rounded-2xl bg-paper p-4 shadow-sm">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="font-display text-xl font-bold text-forest-900">{row.unit_number}</p>
                  <p className="truncate text-sm text-muted">{row.tenant_name}</p>
                  {row.meter_no && <p className="text-xs text-muted">Meter {row.meter_no}</p>}
                </div>
                <div className="text-right text-xs text-muted">
                  <p>Last reading</p>
                  <p className="text-base font-semibold text-forest-900">
                    {row.previous_reading === null ? '—' : num(row.previous_reading)}
                  </p>
                </div>
              </div>

              {saved ? (
                // A reading was already saved for this month
                <div className="mt-3 flex items-center justify-between gap-3 rounded-xl bg-forest-100 px-4 py-3">
                  <div className="min-w-0 text-sm text-forest-900">
                    <p className="flex items-center gap-1.5 font-semibold">
                      <CheckCircle2 size={16} className="shrink-0 text-forest-500" />
                      Reading {num(row.reading)}
                    </p>
                    <p className="text-xs text-forest-700">
                      {row.units_used === null
                        ? 'Starting reading (no charge)'
                        : row.charged
                        ? `${num(row.units_used)} units · ${money(row.amount)} charged`
                        : `${num(row.units_used)} units · ${row.amount > 0 ? 'charge was removed' : 'nothing to charge'}`}
                    </p>
                  </div>
                  <button
                    onClick={() => setUndoing(row)}
                    className="flex shrink-0 items-center gap-1 rounded-lg px-3 py-2 text-sm font-semibold text-terracotta hover:bg-terracotta/10"
                  >
                    <Undo2 size={15} /> Undo
                  </button>
                </div>
              ) : (
                // Type this month's reading
                <div className="mt-3">
                  <input
                    className={inputClass}
                    type="number"
                    inputMode="decimal"
                    min="0"
                    step="any"
                    value={inputs[row.unit_id] ?? ''}
                    onChange={(e) => setInputs({ ...inputs, [row.unit_id]: e.target.value })}
                    placeholder="This month's reading"
                    aria-label={`Reading for unit ${row.unit_number}`}
                  />
                  {/* The working appears as soon as a number is typed */}
                  {entry && entry.used === null && (
                    <p className="mt-2 text-sm text-muted">First reading: saved as the starting point, with no charge.</p>
                  )}
                  {entry && entry.tooLow && (
                    <p className="mt-2 text-sm font-medium text-terracotta">
                      This is lower than the last reading ({num(row.previous_reading)}). Check the meter.
                    </p>
                  )}
                  {entry && entry.used !== null && !entry.tooLow && (
                    <p className="mt-2 text-sm font-medium text-forest-700">
                      {num(entry.used)} units used
                      {rateNumber > 0 ? ` · ${money(entry.amount)}` : ' · enter the price per unit'}
                    </p>
                  )}
                </div>
              )}
            </motion.div>
          )
        })}
      </div>

      {/* The success and error messages */}
      {message && (
        <div role="status" className="mt-4 rounded-xl bg-forest-100 px-4 py-3 text-sm font-medium text-forest-700">
          {message}
        </div>
      )}
      {error && (
        <div role="alert" className="mt-4 rounded-xl bg-terracotta/10 px-4 py-3 text-sm font-medium text-terracotta">
          {error}
        </div>
      )}

      {/* The save button, with a summary of what it will do */}
      <motion.button
        whileTap={{ scale: 0.98 }}
        onClick={handleSave}
        disabled={!canSave}
        className="mt-5 flex w-full items-center justify-center gap-2 rounded-xl bg-forest-900 py-3.5 font-semibold text-white shadow-lg shadow-forest-900/20 transition hover:bg-forest-700 disabled:opacity-50"
      >
        {busy && <Loader2 size={18} className="animate-spin" />}
        {entries.length === 0
          ? `Enter ${label.toLowerCase()} readings above`
          : chargeTotal > 0
          ? `Save ${entries.length} reading${entries.length === 1 ? '' : 's'} and charge ${money(chargeTotal)}`
          : `Save ${entries.length} reading${entries.length === 1 ? '' : 's'}`}
      </motion.button>

      {/* Undo a reading */}
      <ConfirmDialog
        open={undoing !== null}
        title="Undo this reading?"
        message={
          undoing
            ? `This removes the ${label.toLowerCase()} reading for unit ${undoing.unit_number} and its charge, so you can enter it again.`
            : ''
        }
        confirmLabel="Undo reading"
        onClose={() => setUndoing(null)}
        onConfirm={async () => {
          await undoReading(undoing.reading_id)
          setUndoing(null)
          setMessage('')
          load()
        }}
      />
    </div>
  )
}