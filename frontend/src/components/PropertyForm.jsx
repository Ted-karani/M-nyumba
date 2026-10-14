// Import the React tool for remembering values
import { useState } from 'react'
// Import the spinner icon
import { Loader2 } from 'lucide-react'
// Import our shared text box styles
import { Field, inputClass } from './Field'

// The form for adding or editing a property
export default function PropertyForm({ initial, submitLabel, onSubmit, onCancel }) {
  // What the person has typed so far (starting from the saved values when editing)
  const [name, setName] = useState(initial?.name ?? '')
  const [county, setCounty] = useState(initial?.county ?? '')
  const [town, setTown] = useState(initial?.town ?? '')
  const [address, setAddress] = useState(initial?.address ?? '')
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
      // Send the values (empty boxes become "nothing" so the backend stores them as empty)
      await onSubmit({
        name: name.trim(),
        county: county.trim() || null,
        town: town.trim() || null,
        address: address.trim() || null,
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
      <Field label="Property name">
        <input
          className={inputClass}
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Kinoru Apartments"
          required
          minLength={2}
        />
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label="County">
          <input className={inputClass} value={county} onChange={(e) => setCounty(e.target.value)} placeholder="Meru" />
        </Field>
        <Field label="Town or estate">
          <input className={inputClass} value={town} onChange={(e) => setTown(e.target.value)} placeholder="Makutano" />
        </Field>
      </div>
      <Field label="Address or directions" hint="Anything that helps someone find the place.">
        <input
          className={inputClass}
          value={address}
          onChange={(e) => setAddress(e.target.value)}
          placeholder="Next to the petrol station"
        />
      </Field>
      <Field label="Notes (optional)">
        <textarea
          className={`${inputClass} min-h-20`}
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
        />
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
          {submitLabel}
        </button>
      </div>
    </form>
  )
}