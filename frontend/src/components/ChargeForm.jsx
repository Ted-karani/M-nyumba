// Import the React tool for remembering values
import { useState } from 'react'
// Import the spinner icon
import { Loader2 } from 'lucide-react'
// Import our shared text box styles and helpers
import { Field, inputClass } from './Field'
import { CHARGE_LABELS, currentPeriod, nextPeriod, todayISO } from '../format'

// The kinds of charge you can add by hand (the deposit is added when a tenant moves in)
const TYPES = ['rent', 'water', 'wifi', 'electricity', 'other']

// The form for adding a charge to a lease
export default function ChargeForm({ lease, charges, onSubmit, onCancel }) {
  // Find the months that already have a rent charge, then suggest the month after the latest one
  const rentPeriods = charges.filter((c) => c.charge_type === 'rent' && c.period).map((c) => c.period).sort()
  const suggested = rentPeriods.length > 0 ? nextPeriod(rentPeriods[rentPeriods.length - 1]) : currentPeriod()
  // Rent is due on the same day of the month the tenant moved in (never later than the 28th)
  const dueDay = String(Math.min(Number(lease.start_date.slice(8, 10)), 28)).padStart(2, '0')

  // What the person has typed so far
  const [type, setType] = useState('rent')
  const [period, setPeriod] = useState(suggested)
  const [amount, setAmount] = useState(String(lease.rent_amount))
  const [dueDate, setDueDate] = useState(`${suggested}-${dueDay}`)
  // Remember if the due date was typed by hand, so we stop changing it automatically
  const [dueTouched, setDueTouched] = useState(false)
  const [description, setDescription] = useState('')
  // The error message to show (empty means none)
  const [error, setError] = useState('')
  // True while we wait for the backend
  const [busy, setBusy] = useState(false)

  // When the kind of charge changes, fill in or clear the rent amount to match
  function changeType(next) {
    if (next === 'rent' && amount === '') setAmount(String(lease.rent_amount))
    if (next !== 'rent' && type === 'rent' && amount === String(lease.rent_amount)) setAmount('')
    setType(next)
  }

  // When the month changes, move the due date along with it (unless it was set by hand)
  function changePeriod(value) {
    setPeriod(value)
    if (value && !dueTouched) setDueDate(`${value}-${dueDay}`)
  }

  // Run when the form is sent
  async function handleSubmit(event) {
    // Stop the page from reloading
    event.preventDefault()
    // Clear any old error and show the loading state
    setError('')
    setBusy(true)
    try {
      // Send the charge
      await onSubmit({
        charge_type: type,
        amount: Math.round(Number(amount)),
        period: period || null,
        due_date: dueDate,
        description: description.trim() || null,
      })
    } catch (err) {
      // Show the error under the form
      setError(err.message)
    } finally {
      // Stop the loading state
      setBusy(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {/* Buttons to choose what the charge is for */}
      <div>
        <span className="mb-1 block text-sm font-medium">What is it for?</span>
        <div className="flex flex-wrap gap-2">
          {TYPES.map((key) => (
            <button
              key={key}
              type="button"
              onClick={() => changeType(key)}
              className={`rounded-full px-4 py-2 text-sm font-semibold transition ${
                type === key ? 'bg-forest-900 text-white' : 'bg-forest-100 text-forest-700 hover:bg-forest-200'
              }`}
            >
              {CHARGE_LABELS[key]}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <Field label="Amount (KSh)">
          <input
            className={inputClass}
            type="number"
            inputMode="numeric"
            min="1"
            step="1"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            required
          />
        </Field>
        <Field label={type === 'rent' ? 'Month' : 'Month (optional)'}>
          <input
            className={inputClass}
            type="month"
            value={period}
            onChange={(e) => changePeriod(e.target.value)}
            required={type === 'rent'}
          />
        </Field>
      </div>

      <Field label="Due date">
        <input
          className={inputClass}
          type="date"
          value={dueDate}
          onChange={(e) => {
            setDueDate(e.target.value)
            setDueTouched(true)
          }}
          required
        />
      </Field>
      <Field label="Note (optional)" hint='For example "Water: 12 units".'>
        <input className={inputClass} value={description} onChange={(e) => setDescription(e.target.value)} />
      </Field>

      {/* The error appears here if something goes wrong */}
      {error && (
        <div role="alert" className="rounded-xl bg-terracotta/10 px-4 py-3 text-sm font-medium text-terracotta">
          {error}
        </div>
      )}

      <div className="flex gap-3 pt-2">
        <button
          type="button"
          onClick={onCancel}
          className="flex-1 rounded-xl bg-forest-100 py-3 font-semibold text-forest-700 hover:bg-forest-200"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={busy}
          className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-forest-900 py-3 font-semibold text-white hover:bg-forest-700 disabled:opacity-70"
        >
          {busy && <Loader2 size={18} className="animate-spin" />}
          Add charge
        </button>
      </div>
    </form>
  )
}