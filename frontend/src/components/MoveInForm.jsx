// Import the React tool for remembering values
import { useState } from 'react'
// Import the link tool and the spinner icon
import { Link } from 'react-router-dom'
import { Loader2 } from 'lucide-react'
// Import our shared text box styles and helpers
import { Field, inputClass } from './Field'
import { money, todayISO } from '../format'

// The form for moving a tenant into a vacant unit
export default function MoveInForm({ tenant, directory, onSubmit, onCancel }) {
  // Only vacant units can be rented out
  const vacantUnits = directory.units.filter((unit) => unit.status === 'vacant')
  // Start on the first property that has a vacant unit
  const [propertyId, setPropertyId] = useState(() => {
    const first = directory.properties.find((prop) => vacantUnits.some((unit) => unit.property_id === prop.property_id))
    return String((first || directory.properties[0] || {}).property_id ?? '')
  })
  // The unit chosen by hand (empty means "use the first one")
  const [unitId, setUnitId] = useState('')
  // The other boxes
  const [startDate, setStartDate] = useState(todayISO())
  const [endDate, setEndDate] = useState('')
  const [rent, setRent] = useState('')
  const [deposit, setDeposit] = useState('')
  const [notes, setNotes] = useState('')
  // The error message to show (empty means none)
  const [error, setError] = useState('')
  // True while we wait for the backend
  const [busy, setBusy] = useState(false)

  // The vacant units inside the chosen property
  const unitsHere = vacantUnits.filter((unit) => String(unit.property_id) === propertyId)
  // The unit that is selected right now
  const selectedUnit = unitsHere.find((unit) => String(unit.id) === unitId) || unitsHere[0] || null
  // The amounts we will charge: the typed ones, or the unit's own amounts
  const rentAmount = rent !== '' ? Math.round(Number(rent)) : selectedUnit ? selectedUnit.rent_amount : 0
  const depositAmount = deposit !== '' ? Math.round(Number(deposit)) : selectedUnit ? selectedUnit.deposit_amount : 0

  // If there is nowhere to move the tenant, say so instead of showing an empty form
  if (vacantUnits.length === 0) {
    return (
      <div>
        <p className="text-muted">
          There are no vacant units right now. Add a unit to one of your properties, or end a lease to free one up.
        </p>
        <div className="mt-6 flex gap-3">
          <button onClick={onCancel} className="flex-1 rounded-xl bg-forest-100 py-3 font-semibold text-forest-700 hover:bg-forest-200">
            Close
          </button>
          <Link
            to="/properties"
            onClick={onCancel}
            className="flex-1 rounded-xl bg-forest-900 py-3 text-center font-semibold text-white hover:bg-forest-700"
          >
            Go to properties
          </Link>
        </div>
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
      // Send the move-in details (blank amounts mean "use the unit's amounts")
      await onSubmit({
        unit_id: selectedUnit.id,
        start_date: startDate,
        end_date: endDate || null,
        rent_amount: rent !== '' ? Math.round(Number(rent)) : null,
        deposit_amount: deposit !== '' ? Math.round(Number(deposit)) : null,
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
      <p className="text-sm text-muted">
        Moving <span className="font-semibold text-forest-900">{tenant.full_name}</span> into a unit.
      </p>

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
          {directory.properties.map((prop) => {
            // Count the vacant units in this property
            const count = vacantUnits.filter((unit) => unit.property_id === prop.property_id).length
            return (
              <option key={prop.property_id} value={prop.property_id}>
                {prop.name} ({count} vacant)
              </option>
            )
          })}
        </select>
      </Field>

      <Field label="Vacant unit">
        {unitsHere.length === 0 ? (
          <p className="rounded-xl bg-amber/15 px-4 py-3 text-sm text-amber">No vacant units in this property.</p>
        ) : (
          <select className={inputClass} value={selectedUnit ? selectedUnit.id : ''} onChange={(e) => setUnitId(e.target.value)}>
            {unitsHere.map((unit) => (
              <option key={unit.id} value={unit.id}>
                {unit.unit_number}
                {unit.unit_type ? ` · ${unit.unit_type}` : ''} · {money(unit.rent_amount)}
              </option>
            ))}
          </select>
        )}
      </Field>

      <div className="grid grid-cols-2 gap-3">
        <Field label="Move-in date">
          <input className={inputClass} type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} required />
        </Field>
        <Field label="Leaving date (optional)">
          <input className={inputClass} type="date" value={endDate} min={startDate} onChange={(e) => setEndDate(e.target.value)} />
        </Field>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <Field label="Rent (KSh)" hint="Leave blank to use the unit's rent.">
          <input
            className={inputClass}
            type="number"
            inputMode="numeric"
            min="0"
            step="1"
            value={rent}
            onChange={(e) => setRent(e.target.value)}
            placeholder={selectedUnit ? String(selectedUnit.rent_amount) : ''}
          />
        </Field>
        <Field label="Deposit (KSh)" hint="Leave blank to use the unit's deposit.">
          <input
            className={inputClass}
            type="number"
            inputMode="numeric"
            min="0"
            step="1"
            value={deposit}
            onChange={(e) => setDeposit(e.target.value)}
            placeholder={selectedUnit ? String(selectedUnit.deposit_amount) : ''}
          />
        </Field>
      </div>

      <Field label="Notes (optional)">
        <textarea className={`${inputClass} min-h-16`} value={notes} onChange={(e) => setNotes(e.target.value)} />
      </Field>

      {/* A summary of what will be charged when the tenant moves in */}
      {selectedUnit && (
        <div className="rounded-2xl bg-forest-100 p-4 text-sm text-forest-900">
          <p className="font-semibold">On move-in we will charge:</p>
          <div className="mt-2 flex justify-between"><span>Deposit</span><span>{money(depositAmount)}</span></div>
          <div className="flex justify-between"><span>First month's rent</span><span>{money(rentAmount)}</span></div>
          <div className="mt-2 flex justify-between border-t border-forest-200 pt-2 font-bold">
            <span>Total due</span>
            <span>{money(depositAmount + rentAmount)}</span>
          </div>
        </div>
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
          disabled={busy || !selectedUnit}
          className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-forest-900 py-3 font-semibold text-white hover:bg-forest-700 disabled:opacity-60"
        >
          {busy && <Loader2 size={18} className="animate-spin" />}
          Move in
        </button>
      </div>
    </form>
  )
}