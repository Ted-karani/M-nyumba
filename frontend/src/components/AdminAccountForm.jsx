// Import the React tool for remembering values
import { useState } from 'react'
// Import the icon we use
import { Loader2 } from 'lucide-react'
// Import our own files
import { daysFromToday } from '../admin'
import { Field, inputClass } from './Field'

// The form for adding a landlord
export default function AdminAccountForm({ onSubmit, onCancel }) {
  // What has been typed so far
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [phone, setPhone] = useState('')
  const [plan, setPlan] = useState('pilot')
  const [accessUntil, setAccessUntil] = useState(daysFromToday(60))
  const [unitLimit, setUnitLimit] = useState('')
  const [notes, setNotes] = useState('')
  // The error message, and whether we are waiting for the backend
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  // Run when the form is sent
  async function handleSubmit(event) {
    // Stop the page from reloading
    event.preventDefault()
    setError('')
    setBusy(true)
    try {
      await onSubmit({
        full_name: fullName.trim(),
        email: email.trim(),
        phone: phone.trim() || null,
        plan,
        access_until: accessUntil || null,
        unit_limit: unitLimit ? Number(unitLimit) : null,
        notes: notes.trim() || null,
      })
    } catch (err) {
      setError(err.message)
      setBusy(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <Field label="Full name">
        <input className={inputClass} value={fullName} onChange={(e) => setFullName(e.target.value)} required minLength={2} maxLength={80} autoFocus />
      </Field>
      <Field label="Email (they sign in with this)">
        <input className={inputClass} type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
      </Field>
      <Field label="Phone (optional)" hint="Used for the WhatsApp message with their password.">
        <input className={inputClass} type="tel" inputMode="tel" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="0712 345 678" />
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Plan">
          <select className={inputClass} value={plan} onChange={(e) => setPlan(e.target.value)}>
            <option value="pilot">Pilot (free trial)</option>
            <option value="paid">Paid</option>
          </select>
        </Field>
        <Field label="Unit limit" hint="Empty means no limit.">
          <input className={inputClass} type="number" min="1" step="1" inputMode="numeric" value={unitLimit} onChange={(e) => setUnitLimit(e.target.value)} />
        </Field>
      </div>
      <Field label="Access until" hint="Empty means no end date. It turns read-only 7 days after this.">
        <input className={inputClass} type="date" value={accessUntil} onChange={(e) => setAccessUntil(e.target.value)} />
      </Field>
      <Field label="Private notes (only you see these)">
        <textarea className={`${inputClass} min-h-16`} value={notes} onChange={(e) => setNotes(e.target.value)} maxLength={1000} />
      </Field>
      {error && (
        <div role="alert" className="rounded-xl bg-terracotta/10 px-4 py-3 text-sm font-medium text-terracotta">
          {error}
        </div>
      )}
      <div className="flex gap-3 pt-2">
        <button type="button" onClick={onCancel} className="flex-1 rounded-xl bg-forest-100 py-3 font-semibold text-forest-700 hover:bg-forest-200">
          Cancel
        </button>
        <button type="submit" disabled={busy} className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-forest-900 py-3 font-semibold text-white hover:bg-forest-700 disabled:opacity-70">
          {busy && <Loader2 size={18} className="animate-spin" />} Add landlord
        </button>
      </div>
    </form>
  )
}