// Import the React tool for remembering values
import { useState } from 'react'
// Import the icons we use
import { Check, Dices, Loader2 } from 'lucide-react'
// Import our own files
import { Field, inputClass } from './Field'
import { phoneLocal } from '../format'

// Make a random 10-character password (no confusing letters like O, 0, l, or 1)
function generatePassword() {
  const characters = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789'
  // Ask the browser for 10 random numbers and turn each into a character
  const numbers = new Uint32Array(10)
  crypto.getRandomValues(numbers)
  return Array.from(numbers, (n) => characters[n % characters.length]).join('')
}

// The form for adding a caretaker, or editing one
export default function CaretakerForm({ properties, initial, submitLabel, onSubmit, onCancel }) {
  // Are we editing an existing caretaker?
  const isEdit = Boolean(initial)
  // What the person has typed so far (starting from the saved values when editing)
  const [fullName, setFullName] = useState(initial?.full_name ?? '')
  const [email, setEmail] = useState(initial?.email ?? '')
  const [phone, setPhone] = useState(initial ? phoneLocal(initial.phone) : '')
  const [password, setPassword] = useState('')
  const [active, setActive] = useState(initial ? initial.is_active : true)
  // The ids of the properties that are ticked
  const [chosen, setChosen] = useState(() => new Set(initial ? initial.properties.map((p) => p.id) : []))
  // The error message to show (empty means none)
  const [error, setError] = useState('')
  // True while we wait for the backend
  const [busy, setBusy] = useState(false)

  // Tick or untick a property
  function toggleProperty(id) {
    const next = new Set(chosen)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    setChosen(next)
  }

  // Run when the form is sent
  async function handleSubmit(event) {
    // Stop the page from reloading
    event.preventDefault()
    // Clear any old error
    setError('')
    // A caretaker with no properties could not do anything
    if (chosen.size === 0) {
      setError('Tick at least one property for this caretaker to look after.')
      return
    }
    // Show the loading state
    setBusy(true)
    try {
      if (isEdit) {
        // Send the changes (a new password is only sent when one was typed)
        const body = {
          full_name: fullName.trim(),
          phone: phone.trim() || null,
          is_active: active,
          property_ids: [...chosen],
        }
        if (password) body.password = password
        await onSubmit(body)
      } else {
        // Send the new caretaker
        await onSubmit({
          full_name: fullName.trim(),
          email: email.trim(),
          phone: phone.trim() || null,
          password,
          property_ids: [...chosen],
        })
      }
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
        <input className={inputClass} value={fullName} onChange={(e) => setFullName(e.target.value)} placeholder="John Mutua" required minLength={2} autoComplete="off" />
      </Field>

      {/* The email is how they log in, so it cannot be changed after it is created */}
      <Field label="Login email" hint={isEdit ? 'The email cannot be changed.' : 'They will use this to sign in.'}>
        <input
          className={inputClass}
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="john@example.com"
          required
          disabled={isEdit}
          autoComplete="off"
        />
      </Field>

      <Field label="Phone (optional)">
        <input className={inputClass} type="tel" inputMode="tel" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="0722 333 444" autoComplete="off" />
      </Field>

      {/* The password: required when adding, optional when editing (typing one resets it) */}
      <Field
        label={isEdit ? 'New password (leave empty to keep the old one)' : 'Password'}
        hint="At least 8 characters. You can send it to them after saving."
      >
        <div className="flex gap-2">
          <input
            className={`${inputClass} font-mono`}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required={!isEdit}
            minLength={8}
            maxLength={64}
            autoComplete="new-password"
          />
          <button
            type="button"
            onClick={() => setPassword(generatePassword())}
            className="flex shrink-0 items-center gap-2 rounded-xl bg-forest-100 px-4 text-sm font-semibold text-forest-700 hover:bg-forest-200"
          >
            <Dices size={16} /> Generate
          </button>
        </div>
      </Field>

      {/* The properties this caretaker looks after */}
      <div>
        <span className="mb-1 block text-sm font-medium">Properties they look after</span>
        {properties.length === 0 ? (
          <p className="rounded-xl bg-amber/15 px-4 py-3 text-sm text-amber">Add a property first.</p>
        ) : (
          <div className="divide-y divide-forest-100 overflow-hidden rounded-xl border border-forest-200 bg-paper">
            {properties.map((prop) => {
              const ticked = chosen.has(prop.property_id)
              return (
                <button
                  key={prop.property_id}
                  type="button"
                  onClick={() => toggleProperty(prop.property_id)}
                  className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-forest-100/50"
                >
                  <span
                    className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-lg border-2 transition ${
                      ticked ? 'border-forest-900 bg-forest-900 text-white' : 'border-forest-200 bg-paper'
                    }`}
                  >
                    {ticked && <Check size={14} />}
                  </span>
                  <span className="font-medium text-forest-900">{prop.name}</span>
                </button>
              )
            })}
          </div>
        )}
      </div>

      {/* Switch the account on or off (editing only) */}
      {isEdit && (
        <button
          type="button"
          onClick={() => setActive(!active)}
          className="flex w-full items-center justify-between rounded-xl bg-cream px-4 py-3 text-left"
        >
          <span>
            <span className="block text-sm font-semibold text-forest-900">{active ? 'Access is on' : 'Access is off'}</span>
            <span className="block text-xs text-muted">
              {active ? 'They can sign in and work.' : 'They cannot sign in until you turn it back on.'}
            </span>
          </span>
          <span className={`relative h-6 w-11 rounded-full transition ${active ? 'bg-forest-500' : 'bg-forest-200'}`}>
            <span className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-all ${active ? 'left-[22px]' : 'left-0.5'}`} />
          </span>
        </button>
      )}

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