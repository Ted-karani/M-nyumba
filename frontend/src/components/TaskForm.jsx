// Import the React tool for remembering values
import { useState } from 'react'
// Import the icons we use
import { Loader2, Trash2 } from 'lucide-react'
// Import our own files
import { Field, inputClass } from './Field'
import { todayISO } from '../format'

// Quick-start ideas (check the exact due dates with the authority yourself)
const PRESETS = [
  { title: 'Rental income tax return', repeat: 'monthly' },
  { title: 'Business permit renewal', repeat: 'yearly' },
  { title: 'Land rates payment', repeat: 'yearly' },
  { title: 'Insurance renewal', repeat: 'yearly' },
  { title: 'Fire safety certificate', repeat: 'yearly' },
  { title: 'Pay caretaker', repeat: 'monthly' },
]

// How often a task can repeat
const REPEATS = [
  { key: 'none', label: 'Does not repeat' },
  { key: 'monthly', label: 'Every month' },
  { key: 'quarterly', label: 'Every 3 months' },
  { key: 'yearly', label: 'Every year' },
]

// The form for adding a task, or editing one
export default function TaskForm({ properties, initial, submitLabel, onSubmit, onCancel, onDelete }) {
  // What the person has typed so far (starting from the saved values when editing)
  const [title, setTitle] = useState(initial?.title ?? '')
  const [dueDate, setDueDate] = useState(initial?.due_date ?? todayISO())
  const [repeat, setRepeat] = useState(initial?.repeat ?? 'none')
  const [propertyId, setPropertyId] = useState(initial?.property_id != null ? String(initial.property_id) : '')
  const [notes, setNotes] = useState(initial?.notes ?? '')
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
      // Send the task (empty boxes become "nothing")
      await onSubmit({
        title: title.trim(),
        due_date: dueDate,
        repeat,
        property_id: propertyId ? Number(propertyId) : null,
        notes: notes.trim() || null,
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
      {/* Quick-start buttons (only when adding a new task) */}
      {!initial && (
        <div>
          <span className="mb-2 block text-sm font-medium">Quick start</span>
          <div className="flex flex-wrap gap-2">
            {PRESETS.map((preset) => (
              <button
                key={preset.title}
                type="button"
                onClick={() => {
                  setTitle(preset.title)
                  setRepeat(preset.repeat)
                }}
                className="rounded-full bg-forest-100 px-3 py-1.5 text-xs font-semibold text-forest-700 hover:bg-forest-200"
              >
                {preset.title}
              </button>
            ))}
          </div>
          <p className="mt-2 text-xs text-muted">Check the exact due dates with the authority, then set the date below.</p>
        </div>
      )}

      <Field label="What needs doing?">
        <input className={inputClass} value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Business permit renewal" required minLength={2} maxLength={150} autoComplete="off" />
      </Field>

      <div className="grid grid-cols-2 gap-3">
        <Field label="Due date">
          <input className={inputClass} type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} required />
        </Field>
        <Field label="Repeats">
          <select className={inputClass} value={repeat} onChange={(e) => setRepeat(e.target.value)}>
            {REPEATS.map((item) => (
              <option key={item.key} value={item.key}>
                {item.label}
              </option>
            ))}
          </select>
        </Field>
      </div>

      <Field label="Property (optional)">
        <select className={inputClass} value={propertyId} onChange={(e) => setPropertyId(e.target.value)}>
          <option value="">All properties / general</option>
          {properties.map((prop) => (
            <option key={prop.property_id} value={prop.property_id}>
              {prop.name}
            </option>
          ))}
        </select>
      </Field>

      <Field label="Notes (optional)">
        <textarea className={`${inputClass} min-h-16`} value={notes} onChange={(e) => setNotes(e.target.value)} maxLength={500} />
      </Field>

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
            aria-label="Delete this task"
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