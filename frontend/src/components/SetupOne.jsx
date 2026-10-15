// Import the React tool for remembering values
import { useState } from 'react'
// Import the link tool and the icons we use
import { Link } from 'react-router-dom'
import { CheckCircle2, Loader2 } from 'lucide-react'
// Import our own files
import { importExistingTenants } from '../api'
import { Field, inputClass } from './Field'
import { currentPeriod } from '../format'

// The form for adding one tenant who is already living in a unit
export default function SetupOne({ properties }) {
  // What the person has typed so far
  const [propertyName, setPropertyName] = useState(properties.length > 0 ? properties[0].name : '')
  const [unitNumber, setUnitNumber] = useState('')
  const [unitType, setUnitType] = useState('')
  const [tenantName, setTenantName] = useState('')
  const [phone, setPhone] = useState('')
  const [idNumber, setIdNumber] = useState('')
  const [rent, setRent] = useState('')
  const [deposit, setDeposit] = useState('')
  const [owes, setOwes] = useState('')
  const [billingFrom, setBillingFrom] = useState(currentPeriod())
  const [dueDay, setDueDay] = useState('5')
  const [since, setSince] = useState('')
  // The error and success messages
  const [error, setError] = useState('')
  const [added, setAdded] = useState('')
  // True while we wait for the backend
  const [busy, setBusy] = useState(false)

  // Run when the form is sent
  async function handleSubmit(event) {
    // Stop the page from reloading
    event.preventDefault()
    // Clear old messages and show the loading state
    setError('')
    setAdded('')
    setBusy(true)
    try {
      // Send the tenant as a list of one (the backend checks it in the same way as an imported list)
      const result = await importExistingTenants(
        [
          {
            property_name: propertyName,
            unit_number: unitNumber,
            unit_type: unitType,
            tenant_name: tenantName,
            phone,
            id_number: idNumber,
            rent_amount: rent,
            deposit_amount: deposit,
            balance: owes,
            billing_from: billingFrom,
            due_day: dueDay,
            tenant_since: since,
          },
        ],
        false
      )
      // If the backend found a problem, show it
      if (!result.ok) {
        setError(result.results[0].message)
        return
      }
      // Success: remember who was added, and clear the boxes for the next tenant
      setAdded(`${tenantName.trim()} was added to unit ${unitNumber.trim()}.`)
      setUnitNumber('')
      setUnitType('')
      setTenantName('')
      setPhone('')
      setIdNumber('')
      setRent('')
      setDeposit('')
      setOwes('')
      setSince('')
    } catch (err) {
      // Show the error under the form
      setError(err.message)
    } finally {
      // Stop the loading state
      setBusy(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="mt-6 space-y-5">
      {/* The unit */}
      <div className="rounded-3xl bg-paper p-5 shadow-sm">
        <h2 className="font-display text-lg font-bold text-forest-900">Where do they live?</h2>
        <div className="mt-4 space-y-4">
          <Field label="Property">
            <select className={inputClass} value={propertyName} onChange={(e) => setPropertyName(e.target.value)}>
              {properties.map((prop) => (
                <option key={prop.property_id} value={prop.name}>
                  {prop.name}
                </option>
              ))}
            </select>
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Unit number" hint="Created for you if it is new.">
              <input className={inputClass} value={unitNumber} onChange={(e) => setUnitNumber(e.target.value)} placeholder="E1" required maxLength={20} autoComplete="off" />
            </Field>
            <Field label="Type (optional)">
              <input className={inputClass} list="setup-unit-types" value={unitType} onChange={(e) => setUnitType(e.target.value)} placeholder="Bedsitter" />
              <datalist id="setup-unit-types">
                <option value="Single room" />
                <option value="Bedsitter" />
                <option value="Studio" />
                <option value="1 Bedroom" />
                <option value="2 Bedroom" />
                <option value="3 Bedroom" />
              </datalist>
            </Field>
          </div>
        </div>
      </div>

      {/* The tenant */}
      <div className="rounded-3xl bg-paper p-5 shadow-sm">
        <h2 className="font-display text-lg font-bold text-forest-900">Who is the tenant?</h2>
        <div className="mt-4 space-y-4">
          <Field label="Full name">
            <input className={inputClass} value={tenantName} onChange={(e) => setTenantName(e.target.value)} placeholder="Mercy Wambui" required minLength={2} autoComplete="off" />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Phone number">
              <input className={inputClass} type="tel" inputMode="tel" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="0711 000 111" required autoComplete="off" />
            </Field>
            <Field label="ID number (optional)">
              <input className={inputClass} inputMode="numeric" value={idNumber} onChange={(e) => setIdNumber(e.target.value)} autoComplete="off" />
            </Field>
          </div>
          <Field label="Living here since (optional)" hint="Only kept as a note.">
            <input className={inputClass} type="date" value={since} onChange={(e) => setSince(e.target.value)} />
          </Field>
        </div>
      </div>

      {/* The money */}
      <div className="rounded-3xl bg-paper p-5 shadow-sm">
        <h2 className="font-display text-lg font-bold text-forest-900">Rent and what they owe</h2>
        <div className="mt-4 space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <Field label="Monthly rent (KSh)">
              <input className={inputClass} type="number" inputMode="numeric" min="1" step="1" value={rent} onChange={(e) => setRent(e.target.value)} placeholder="6000" required />
            </Field>
            <Field label="Deposit paid (KSh)" hint="Kept on record, never charged again.">
              <input className={inputClass} type="number" inputMode="numeric" min="0" step="1" value={deposit} onChange={(e) => setDeposit(e.target.value)} placeholder="6000" />
            </Field>
          </div>
          <Field label="They owe right now (KSh)" hint="What your notebook says. Leave empty if they are paid up.">
            <input className={inputClass} type="number" inputMode="numeric" min="0" step="1" value={owes} onChange={(e) => setOwes(e.target.value)} placeholder="0" />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Start billing rent from" hint="If they already paid this month, choose next month.">
              <input className={inputClass} type="month" value={billingFrom} onChange={(e) => setBillingFrom(e.target.value)} required />
            </Field>
            <Field label="Rent is due on day" hint="Day of the month, 1 to 28.">
              <input className={inputClass} type="number" inputMode="numeric" min="1" max="28" step="1" value={dueDay} onChange={(e) => setDueDay(e.target.value)} required />
            </Field>
          </div>
        </div>
      </div>

      {/* The messages */}
      {added && (
        <div role="status" className="flex items-start gap-3 rounded-2xl bg-forest-100 px-4 py-3 text-sm font-medium text-forest-700">
          <CheckCircle2 size={20} className="mt-0.5 shrink-0" />
          <p>
            {added} <Link to="/tenants" className="underline">See tenants</Link>, or add the next one below.
          </p>
        </div>
      )}
      {error && (
        <div role="alert" className="rounded-2xl bg-terracotta/10 px-4 py-3 text-sm font-medium text-terracotta">
          {error}
        </div>
      )}

      <button
        type="submit"
        disabled={busy}
        className="flex w-full items-center justify-center gap-2 rounded-xl bg-forest-900 py-3.5 font-semibold text-white shadow-lg shadow-forest-900/20 hover:bg-forest-700 disabled:opacity-70"
      >
        {busy && <Loader2 size={18} className="animate-spin" />}
        Add tenant
      </button>
    </form>
  )
}