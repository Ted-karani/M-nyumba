// Import the React tool for remembering values
import { useState } from 'react'
// Import the icons we use
import { Loader2, Trash2 } from 'lucide-react'
// Import our own files
import { Field, inputClass } from './Field'
import { phoneLocal } from '../format'

// The three levels of urgency
const PRIORITIES = [
  { key: 'low', label: 'Low' },
  { key: 'normal', label: 'Normal' },
  { key: 'urgent', label: 'Urgent' },
]

// The three stages a repair goes through
const STATUSES = [
  { key: 'open', label: 'Open' },
  { key: 'in_progress', label: 'In progress' },
  { key: 'fixed', label: 'Fixed' },
]

// A row of buttons where one can be chosen
function Choice({ options, value, onChange, urgent = false }) {
  return (
    <div className="grid grid-cols-3 gap-2">
      {options.map((option) => (
        <button
          key={option.key}
          type="button"
          onClick={() => onChange(option.key)}
          className={`rounded-xl py-2.5 text-sm font-semibold transition ${
            value === option.key
              ? urgent && option.key === 'urgent'
                ? 'bg-terracotta text-white'
                : 'bg-forest-900 text-white'
              : 'bg-forest-100 text-forest-700 hover:bg-forest-200'
          }`}
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}

// The form for reporting a problem, or for editing one that was already reported
export default function RepairForm({ directory, initial, submitLabel, onSubmit, onCancel, onDelete, canSetCost = true }) {
  // Are we editing an existing repair?
  const isEdit = Boolean(initial)
  // What the person has typed so far (starting from the saved values when editing)
  const [propertyId, setPropertyId] = useState(
    String(directory.properties.length > 0 ? directory.properties[0].property_id : '')
  )
  const [unitId, setUnitId] = useState('')
  const [title, setTitle] = useState(initial?.title ?? '')
  const [description, setDescription] = useState(initial?.description ?? '')
  const [priority, setPriority] = useState(initial?.priority ?? 'normal')
  const [status, setStatus] = useState(initial?.status ?? 'open')
  const [cost, setCost] = useState(initial?.cost != null ? String(initial.cost) : '')
  const [contractorName, setContractorName] = useState(initial?.contractor_name ?? '')
  const [contractorPhone, setContractorPhone] = useState(initial ? phoneLocal(initial.contractor_phone) : '')
  const [notes, setNotes] = useState(initial?.notes ?? '')
  // The error message to show (empty means none)
  const [error, setError] = useState('')
  // True while we wait for the backend
  const [busy, setBusy] = useState(false)

  // The units inside the chosen property
  const unitsHere = directory.units.filter((unit) => String(unit.property_id) === propertyId)

  // If there are no properties yet, say so instead of showing an empty form
  if (!isEdit && directory.properties.length === 0) {
    return (
      <div>
        <p className="text-muted">There are no properties to report a problem in yet.</p>
        <button onClick={onCancel} className="mt-6 w-full rounded-xl bg-forest-100 py-3 font-semibold text-forest-700 hover:bg-forest-200">
          Close
        </button>
      </div>
    )
  }

  // Run when the form is sent
  async function handleSubmit(event) {
    // Stop the page from reloading
    event.preventDefault()
    // Clear any old error and show the loading state
    setError('')
    setBusy(true)
    try {
      if (isEdit) {
        // Build the changes (empty boxes become "nothing")
        const body = {
          title: title.trim(),
          description: description.trim() || null,
          priority,
          status,
          contractor_name: contractorName.trim() || null,
          contractor_phone: contractorPhone.trim() || null,
          notes: notes.trim() || null,
        }
        // Only owners send a cost (the backend refuses it from anyone else)
        if (canSetCost) body.cost = cost === '' ? null : Math.round(Number(cost))
        await onSubmit(body)
      } else {
        // Send the new problem
        await onSubmit({
          property_id: Number(propertyId),
          unit_id: unitId ? Number(unitId) : null,
          title: title.trim(),
          description: description.trim() || null,
          priority,
          contractor_name: contractorName.trim() || null,
          contractor_phone: contractorPhone.trim() || null,
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
      {isEdit ? (
        // When editing, show where the problem is (it cannot be moved)
        <p className="rounded-xl bg-forest-100 px-4 py-3 text-sm text-forest-700">
          {initial.unit_number ? `Unit ${initial.unit_number}` : 'Whole property'} · {initial.property_name}
        </p>
      ) : (
        <>
          <Field label="Property">
            <select
              className={inputClass}
              value={propertyId}
              onChange={(e) => {
                // Changing the property resets the unit choice
                setPropertyId(e.target.value)
                setUnitId('')
              }}
            >
              {directory.properties.map((prop) => (
                <option key={prop.property_id} value={prop.property_id}>
                  {prop.name}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Where is the problem?">
            <select className={inputClass} value={unitId} onChange={(e) => setUnitId(e.target.value)}>
              <option value="">Whole property / common area</option>
              {unitsHere.map((unit) => (
                <option key={unit.id} value={unit.id}>
                  Unit {unit.unit_number}
                </option>
              ))}
            </select>
          </Field>
        </>
      )}

      <Field label="What is the problem?">
        <input
          className={inputClass}
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Leaking kitchen tap"
          required
          minLength={3}
          maxLength={120}
          autoComplete="off"
        />
      </Field>
      <Field label="Details (optional)">
        <textarea className={`${inputClass} min-h-20`} value={description} onChange={(e) => setDescription(e.target.value)} />
      </Field>

      <div>
        <span className="mb-1 block text-sm font-medium">How urgent is it?</span>
        <Choice options={PRIORITIES} value={priority} onChange={setPriority} urgent />
      </div>

      {/* The status only makes sense once the problem exists */}
      {isEdit && (
        <div>
          <span className="mb-1 block text-sm font-medium">Progress</span>
          <Choice options={STATUSES} value={status} onChange={setStatus} />
        </div>
      )}

      {/* The cost is for owners only */}
      {isEdit && canSetCost && (
        <Field
          label="Cost (KSh)"
          hint={status === 'fixed' && cost === '' ? 'Add the cost so your monthly repair total is right.' : undefined}
        >
          <input
            className={inputClass}
            type="number"
            inputMode="numeric"
            min="0"
            step="1"
            value={cost}
            onChange={(e) => setCost(e.target.value)}
            placeholder="1200"
          />
        </Field>
      )}

      <div className="grid grid-cols-2 gap-3">
        <Field label="Who is fixing it?">
          <input className={inputClass} value={contractorName} onChange={(e) => setContractorName(e.target.value)} placeholder="Joseph" autoComplete="off" />
        </Field>
        <Field label="Their phone">
          <input
            className={inputClass}
            type="tel"
            inputMode="tel"
            value={contractorPhone}
            onChange={(e) => setContractorPhone(e.target.value)}
            placeholder="0711 222 333"
            autoComplete="off"
          />
        </Field>
      </div>

      {isEdit && (
        <Field label="Notes (optional)">
          <textarea className={`${inputClass} min-h-16`} value={notes} onChange={(e) => setNotes(e.target.value)} />
        </Field>
      )}

      {/* The error appears here if something goes wrong */}
      {error && (
        <div role="alert" className="rounded-xl bg-terracotta/10 px-4 py-3 text-sm font-medium text-terracotta">
          {error}
        </div>
      )}

      <div className="flex gap-3 pt-2">
        {isEdit && onDelete && (
          <button
            type="button"
            onClick={onDelete}
            aria-label="Delete this repair"
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