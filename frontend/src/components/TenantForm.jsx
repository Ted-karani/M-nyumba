// Import the React tool for remembering values
import { useState } from 'react'
// Import the spinner icon
import { Loader2 } from 'lucide-react'
// Import our shared text box styles and phone formatter
import { Field, inputClass } from './Field'
import { phoneLocal } from '../format'

// The form for adding or editing a tenant
export default function TenantForm({ initial, submitLabel, onSubmit, onCancel }) {
  // What the person has typed so far (starting from the saved values when editing)
  const [fullName, setFullName] = useState(initial?.full_name ?? '')
  const [phone, setPhone] = useState(initial ? phoneLocal(initial.phone) : '')
  const [email, setEmail] = useState(initial?.email ?? '')
  const [idNumber, setIdNumber] = useState(initial?.id_number ?? '')
  const [emergencyName, setEmergencyName] = useState(initial?.emergency_contact_name ?? '')
  const [emergencyPhone, setEmergencyPhone] = useState(initial ? phoneLocal(initial.emergency_contact_phone) : '')
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
        full_name: fullName.trim(),
        phone: phone.trim(),
        email: email.trim() || null,
        id_number: idNumber.trim() || null,
        emergency_contact_name: emergencyName.trim() || null,
        emergency_contact_phone: emergencyPhone.trim() || null,
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
      <Field label="Full name">
        <input
          className={inputClass}
          value={fullName}
          onChange={(e) => setFullName(e.target.value)}
          placeholder="Peter Kamau"
          required
          minLength={2}
          autoComplete="off"
        />
      </Field>
      <Field label="Phone number" hint="Any format works: 0712 345 678 or +254712345678.">
        <input
          className={inputClass}
          type="tel"
          inputMode="tel"
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
          placeholder="0712 345 678"
          required
          autoComplete="off"
        />
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Email (optional)">
          <input className={inputClass} type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="off" />
        </Field>
        <Field label="ID number (optional)">
          <input className={inputClass} inputMode="numeric" value={idNumber} onChange={(e) => setIdNumber(e.target.value)} autoComplete="off" />
        </Field>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Emergency contact">
          <input className={inputClass} value={emergencyName} onChange={(e) => setEmergencyName(e.target.value)} placeholder="Name" autoComplete="off" />
        </Field>
        <Field label="Their phone">
          <input
            className={inputClass}
            type="tel"
            inputMode="tel"
            value={emergencyPhone}
            onChange={(e) => setEmergencyPhone(e.target.value)}
            autoComplete="off"
          />
        </Field>
      </div>
      <Field label="Notes (optional)">
        <textarea className={`${inputClass} min-h-20`} value={notes} onChange={(e) => setNotes(e.target.value)} />
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