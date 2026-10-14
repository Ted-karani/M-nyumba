// Import the React tool for remembering values
import { useState } from 'react'
// Import the spinner icon
import { Loader2 } from 'lucide-react'
// Import our shared text box styles and helpers
import { Field, inputClass } from './Field'
import { METHOD_LABELS, money, todayISO } from '../format'

// The form for recording a payment on a lease
export default function PaymentForm({ lease, onSubmit, onCancel }) {
  // What the person has typed so far (the box starts with the full balance if money is owed)
  const [amount, setAmount] = useState(lease.balance > 0 ? String(lease.balance) : '')
  const [paidOn, setPaidOn] = useState(todayISO())
  const [method, setMethod] = useState('mpesa')
  const [reference, setReference] = useState('')
  const [notes, setNotes] = useState('')
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
      // Send the payment (cash payments have no code)
      await onSubmit({
        amount: Math.round(Number(amount)),
        paid_on: paidOn,
        method,
        reference: method === 'cash' ? null : reference.trim() || null,
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
      {/* What the tenant owes right now */}
      <p className="text-sm text-muted">
        {lease.tenant_name} · {lease.unit_number} ·{' '}
        <span className="font-semibold text-forest-900">
          {lease.balance > 0 ? `owes ${money(lease.balance)}` : 'nothing owed'}
        </span>
      </p>

      <Field label="Amount paid (KSh)">
        <input
          className={inputClass}
          type="number"
          inputMode="numeric"
          min="1"
          step="1"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          required
          autoFocus
        />
      </Field>
      {/* A shortcut to fill in the whole balance */}
      {lease.balance > 0 && (
        <button
          type="button"
          onClick={() => setAmount(String(lease.balance))}
          className="-mt-2 rounded-full bg-forest-100 px-3 py-1 text-xs font-semibold text-forest-700 hover:bg-forest-200"
        >
          Pay full balance ({money(lease.balance)})
        </button>
      )}

      {/* Three buttons to choose how it was paid */}
      <div>
        <span className="mb-1 block text-sm font-medium">How was it paid?</span>
        <div className="grid grid-cols-3 gap-2">
          {Object.entries(METHOD_LABELS).map(([key, label]) => (
            <button
              key={key}
              type="button"
              onClick={() => setMethod(key)}
              className={`rounded-xl py-2.5 text-sm font-semibold transition ${
                method === key ? 'bg-forest-900 text-white' : 'bg-forest-100 text-forest-700 hover:bg-forest-200'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* M-Pesa needs the 10-character code, bank can have a reference, cash needs nothing */}
      {method !== 'cash' && (
        <Field
          label={method === 'mpesa' ? 'M-Pesa code' : 'Bank reference (optional)'}
          hint={method === 'mpesa' ? '10 letters and numbers from the M-Pesa message, like SJK4L2M9QP.' : undefined}
        >
          <input
            className={`${inputClass} font-mono uppercase tracking-wider`}
            value={reference}
            onChange={(e) => setReference(e.target.value.toUpperCase())}
            maxLength={method === 'mpesa' ? 10 : 40}
            required={method === 'mpesa'}
            pattern={method === 'mpesa' ? '[A-Za-z0-9]{10}' : undefined}
            title={method === 'mpesa' ? 'The M-Pesa code is exactly 10 letters and numbers' : undefined}
            placeholder={method === 'mpesa' ? 'SJK4L2M9QP' : ''}
            autoComplete="off"
          />
        </Field>
      )}

      <Field label="Date received">
        <input className={inputClass} type="date" value={paidOn} max={todayISO()} onChange={(e) => setPaidOn(e.target.value)} required />
      </Field>
      <Field label="Notes (optional)">
        <input className={inputClass} value={notes} onChange={(e) => setNotes(e.target.value)} />
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
          Record payment
        </button>
      </div>
    </form>
  )
}