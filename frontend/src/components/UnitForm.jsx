// Import the React tool for remembering values
import { useState } from 'react'
// Import the spinner icon
import { Loader2 } from 'lucide-react'
// Import our shared text box styles
import { Field, inputClass } from './Field'

// The form for adding or editing a unit (a house or room)
export default function UnitForm({ initial, submitLabel, onSubmit, onCancel }) {
  // What the person has typed so far (starting from the saved values when editing)
  const [unitNumber, setUnitNumber] = useState(initial?.unit_number ?? '')
  const [unitType, setUnitType] = useState(initial?.unit_type ?? '')
  const [rent, setRent] = useState(initial ? String(initial.rent_amount) : '')
  const [deposit, setDeposit] = useState(initial ? String(initial.deposit_amount) : '')
  const [status, setStatus] = useState(initial?.status === 'maintenance' ? 'maintenance' : 'vacant')
  const [electricity, setElectricity] = useState(initial?.electricity_meter_no ?? '')
  const [water, setWater] = useState(initial?.water_meter_no ?? '')
  const [notes, setNotes] = useState(initial?.notes ?? '')
  // The error message to show (empty means none)
  const [error, setError] = useState('')
  // True while we wait for the backend
  const [busy, setBusy] = useState(false)
  // An occupied unit's status is controlled by its lease, so we hide that box
  const isOccupied = initial?.status === 'occupied'

  // Run when the form is sent
  async function handleSubmit(event) {
    // Stop the page from reloading
    event.preventDefault()
    // Clear any old error and show the loading state
    setError('')
    setBusy(true)
    try {
      // Build what we send (money is turned into whole numbers)
      const body = {
        unit_number: unitNumber.trim(),
        unit_type: unitType.trim() || null,
        rent_amount: Math.round(Number(rent)) || 0,
        deposit_amount: Math.round(Number(deposit)) || 0,
        electricity_meter_no: electricity.trim() || null,
        water_meter_no: water.trim() || null,
        notes: notes.trim() || null,
      }
      // Only send the status when it is allowed to be changed by hand
      if (!isOccupied) body.status = status
      // Send it
      await onSubmit(body)
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
      <div className="grid grid-cols-2 gap-3">
        <Field label="Unit number">
          <input
            className={inputClass}
            value={unitNumber}
            onChange={(e) => setUnitNumber(e.target.value)}
            placeholder="A1"
            required
            maxLength={20}
          />
        </Field>
        <Field label="Type">
          {/* The list gives suggestions, but you can still type your own */}
          <input
            className={inputClass}
            list="unit-types"
            value={unitType}
            onChange={(e) => setUnitType(e.target.value)}
            placeholder="Bedsitter"
          />
          <datalist id="unit-types">
            <option value="Single room" />
            <option value="Bedsitter" />
            <option value="Studio" />
            <option value="1 Bedroom" />
            <option value="2 Bedroom" />
            <option value="3 Bedroom" />
          </datalist>
        </Field>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Monthly rent (KSh)">
          <input
            className={inputClass}
            type="number"
            inputMode="numeric"
            min="0"
            step="1"
            value={rent}
            onChange={(e) => setRent(e.target.value)}
            placeholder="8000"
          />
        </Field>
        <Field label="Deposit (KSh)">
          <input
            className={inputClass}
            type="number"
            inputMode="numeric"
            min="0"
            step="1"
            value={deposit}
            onChange={(e) => setDeposit(e.target.value)}
            placeholder="8000"
          />
        </Field>
      </div>

      {/* The status box, or a note when the unit is occupied */}
      {isOccupied ? (
        <p className="rounded-xl bg-forest-100 px-4 py-3 text-sm text-forest-700">
          This unit is occupied. To change its status, end the tenant's lease first.
        </p>
      ) : (
        <Field label="Status">
          <select className={inputClass} value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="vacant">Vacant</option>
            <option value="maintenance">Under repair</option>
          </select>
        </Field>
      )}

      <div className="grid grid-cols-2 gap-3">
        <Field label="Electricity meter no.">
          <input className={inputClass} value={electricity} onChange={(e) => setElectricity(e.target.value)} />
        </Field>
        <Field label="Water meter no.">
          <input className={inputClass} value={water} onChange={(e) => setWater(e.target.value)} />
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