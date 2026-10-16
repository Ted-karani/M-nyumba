// Import the React tool for remembering values
import { useState } from 'react'
// Import the icons we use
import { Loader2, Trash2 } from 'lucide-react'
// Import our own files
import { Field, inputClass } from './Field'
import { EXPENSE_CATEGORIES } from '../categories'
import { todayISO } from '../format'

// The form for recording an expense, or editing one
export default function ExpenseForm({ properties, initial, submitLabel, onSubmit, onCancel, onDelete }) {
  // What the person has typed so far (starting from the saved values when editing)
  const [propertyId, setPropertyId] = useState(initial?.property_id != null ? String(initial.property_id) : '')
  const [category, setCategory] = useState(initial?.category ?? 'caretaker')
  const [amount, setAmount] = useState(initial ? String(initial.amount) : '')
  const [spentOn, setSpentOn] = useState(initial?.spent_on ?? todayISO())
  const [description, setDescription] = useState(initial?.description ?? '')
  const [paidTo, setPaidTo] = useState(initial?.paid_to ?? '')
  // The error message to show (empty means none)
  const [error, setError] = useState('')
  // True while we wait for the backend
  const [busy, setBusy] = useState(false)

  // Run when the form is sent
  async function handleSubmit(event) {
    // Stop the page from reloading
    event.preventDefault()
    // Clear any old error and show the loading state
    setError('')
    setBusy(true)
    try {
      // Send the expense (empty boxes become "nothing")
      await onSubmit({
        property_id: propertyId ? Number(propertyId) : null,
        category,
        amount: Math.round(Number(amount)),
        spent_on: spentOn,
        description: description.trim() || null,
        paid_to: paidTo.trim() || null,
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
      <Field label="What was it for?">
        <select className={inputClass} value={category} onChange={(e) => setCategory(e.target.value)}>
          {EXPENSE_CATEGORIES.map((item) => (
            <option key={item.key} value={item.key}>
              {item.label}
            </option>
          ))}
        </select>
      </Field>

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
            placeholder="8000"
            required
            autoFocus
          />
        </Field>
        <Field label="Date">
          <input className={inputClass} type="date" value={spentOn} onChange={(e) => setSpentOn(e.target.value)} required />
        </Field>
      </div>

      <Field label="Which property?" hint="Choose General for things that cover all your properties.">
        <select className={inputClass} value={propertyId} onChange={(e) => setPropertyId(e.target.value)}>
          <option value="">General (all properties)</option>
          {properties.map((prop) => (
            <option key={prop.property_id} value={prop.property_id}>
              {prop.name}
            </option>
          ))}
        </select>
      </Field>

      <div className="grid grid-cols-2 gap-3">
        <Field label="Paid to (optional)">
          <input className={inputClass} value={paidTo} onChange={(e) => setPaidTo(e.target.value)} placeholder="John Mutua" autoComplete="off" />
        </Field>
        <Field label="Note (optional)">
          <input className={inputClass} value={description} onChange={(e) => setDescription(e.target.value)} placeholder="October salary" autoComplete="off" />
        </Field>
      </div>

      <p className="rounded-xl bg-forest-100 px-4 py-3 text-xs text-forest-700">
        Repairs are counted automatically from the Repairs page, so do not enter them here too.
      </p>

      {/* The error appears here if something goes wrong */}
      {error && (
        <div role="alert" className="rounded-xl bg-terracotta/10 px-4 py-3 text-sm font-medium text-terracotta">
          {error}
        </div>
      )}

      <div className="flex gap-3 pt-2">
        {onDelete && (
          <button
            type="button"
            onClick={onDelete}
            aria-label="Delete this expense"
            className="rounded-xl bg-terracotta/10 px-4 text-terracotta hover:bg-terracotta hover:text-white"
          >
            <Trash2 size={18} />
          </button>
        )}
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
          {submitLabel}
        </button>
      </div>
    </form>
  )
}