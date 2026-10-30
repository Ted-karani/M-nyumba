// Import the React tools we need
import { useEffect, useRef, useState } from 'react'
// Import the page-switching tool
import { Link } from 'react-router-dom'
// Import the animation tools
import { AnimatePresence, motion } from 'framer-motion'
// Import the icons we use
import { AlertCircle, ArrowLeft, ArrowRight, Building2, CheckCircle2, Loader2, Plus, Sparkles, Trash2, Users } from 'lucide-react'
// Import our own files
import { createBuilding, getDashboard, previewBuilding } from '../api'
import { Field, inputClass } from '../components/Field'
import { money } from '../format'

// The kinds of unit we suggest
const UNIT_TYPES = ['Bedsitter', 'Single room', '1 Bedroom', '2 Bedroom', '3 Bedroom', 'Shop', 'Other']
// The three steps
const STEPS = ['The building', 'The units', 'Done']
// The most groups of units in one go
const MAX_GROUPS = 10

// Each group of units gets its own number, so the screen can tell them apart
let nextGroupId = 1
const newGroup = () => ({ id: nextGroupId++, labels: '', type: '', otherType: '', rent: '', deposit: '' })

// The little numbered steps at the top
function Stepper({ step }) {
  return (
    <div className="mt-6 flex items-center gap-2">
      {STEPS.map((label, index) => {
        const number = index + 1
        const reached = step >= number
        return (
          <div key={label} className="flex flex-1 items-center gap-2">
            <span className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm font-bold transition ${reached ? 'bg-forest-900 text-white' : 'bg-forest-100 text-forest-700'}`}>
              {step > number ? <CheckCircle2 size={16} /> : number}
            </span>
            <span className={`hidden text-sm font-semibold sm:block ${reached ? 'text-forest-900' : 'text-muted'}`}>{label}</span>
            {number < STEPS.length && <span className={`h-0.5 flex-1 rounded-full ${step > number ? 'bg-forest-900' : 'bg-forest-100'}`} />}
          </div>
        )
      })}
    </div>
  )
}

// The page for setting up a whole building and its units
export default function QuickSetup() {
  // Which step we are on: 1, 2 or 3
  const [step, setStep] = useState(1)
  // Whether the building is new or already exists
  const [mode, setMode] = useState('new')
  // The landlord's existing buildings (nothing until they arrive)
  const [properties, setProperties] = useState([])
  const [propertyId, setPropertyId] = useState('')
  // The details of a new building
  const [name, setName] = useState('')
  const [town, setTown] = useState('')
  const [county, setCounty] = useState('')
  const [address, setAddress] = useState('')
  // The groups of units
  const [groups, setGroups] = useState([newGroup()])
  const [skipExisting, setSkipExisting] = useState(true)
  // What the preview says (nothing until it arrives)
  const [preview, setPreview] = useState(null)
  const [previewBusy, setPreviewBusy] = useState(false)
  // The error message, and whether we are saving
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  // What was created (shown in step 3)
  const [done, setDone] = useState(null)
  // A counter, so an old preview can never replace a newer one
  const requestNumber = useRef(0)

  // Load the landlord's buildings when the page opens
  useEffect(() => {
    getDashboard()
      .then((data) => setProperties(data.properties || []))
      .catch(() => setProperties([]))
  }, [])

  // Put everything typed so far into the shape the backend wants
  function buildBody() {
    return {
      property_id: mode === 'existing' ? Number(propertyId) : null,
      new_property:
        mode === 'new'
          ? { name: name.trim(), town: town.trim() || null, county: county.trim() || null, address: address.trim() || null }
          : null,
      groups: groups
        .filter((group) => group.labels.trim() !== '')
        .map((group) => ({
          labels: group.labels,
          unit_type: (group.type === 'Other' ? group.otherType.trim() : group.type) || null,
          rent_amount: Number(group.rent) || 0,
          deposit_amount: Number(group.deposit) || 0,
        })),
      skip_existing: skipExisting,
    }
  }

  // In step 2, ask for a fresh preview half a second after the person stops typing
  useEffect(() => {
    if (step !== 2) return undefined
    if (!groups.some((group) => group.labels.trim() !== '')) {
      setPreview(null)
      return undefined
    }
    const timer = setTimeout(async () => {
      const mine = ++requestNumber.current
      setPreviewBusy(true)
      try {
        const result = await previewBuilding(buildBody())
        if (mine === requestNumber.current) {
          setPreview(result)
          setError('')
        }
      } catch (err) {
        if (mine === requestNumber.current) setError(err.message)
      } finally {
        if (mine === requestNumber.current) setPreviewBusy(false)
      }
    }, 500)
    return () => clearTimeout(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step, groups, skipExisting, mode, propertyId, name])

  // Change one box of one group
  function changeGroup(id, changes) {
    setGroups(groups.map((group) => (group.id === id ? { ...group, ...changes } : group)))
  }

  // Can we leave step 1?
  const step1Ready = mode === 'new' ? name.trim().length >= 2 : propertyId !== ''

  // Save the building and its units
  async function save() {
    setError('')
    setSaving(true)
    try {
      const result = await createBuilding(buildBody())
      if (result.ok) {
        setDone(result)
        setStep(3)
      } else {
        // Something changed since the preview, so show what is wrong now
        setPreview(result)
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  // Start again with another building
  function reset() {
    setStep(1)
    setMode('new')
    setPropertyId('')
    setName('')
    setTown('')
    setCounty('')
    setAddress('')
    setGroups([newGroup()])
    setPreview(null)
    setDone(null)
    setError('')
  }

  return (
    <div className="mx-auto max-w-3xl">
      <div className="flex items-center gap-3">
        <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gold/25 text-forest-900">
          <Sparkles size={22} />
        </div>
        <div>
          <h1 className="text-3xl font-extrabold text-forest-900">Quick setup</h1>
          <p className="text-muted">Add a whole building and all its units in a minute.</p>
        </div>
      </div>

      <Stepper step={step} />

      <AnimatePresence mode="wait">
        {/* Step 1: the building */}
        {step === 1 && (
          <motion.div key="step1" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="mt-6 rounded-3xl bg-paper p-6 shadow-sm">
            <h2 className="font-display text-xl font-bold text-forest-900">Which building?</h2>
            <div className="mt-4 grid grid-cols-2 gap-3">
              <button
                onClick={() => setMode('new')}
                className={`rounded-2xl p-4 text-left transition ${mode === 'new' ? 'bg-forest-900 text-white' : 'bg-cream text-forest-900 hover:bg-forest-100'}`}
              >
                <Building2 size={20} />
                <p className="mt-2 font-semibold">A new building</p>
                <p className={`text-xs ${mode === 'new' ? 'text-forest-200' : 'text-muted'}`}>Add it and its units together</p>
              </button>
              <button
                onClick={() => setMode('existing')}
                disabled={properties.length === 0}
                className={`rounded-2xl p-4 text-left transition disabled:opacity-50 ${mode === 'existing' ? 'bg-forest-900 text-white' : 'bg-cream text-forest-900 hover:bg-forest-100'}`}
              >
                <Plus size={20} />
                <p className="mt-2 font-semibold">One I already have</p>
                <p className={`text-xs ${mode === 'existing' ? 'text-forest-200' : 'text-muted'}`}>Add more units to it</p>
              </button>
            </div>

            {mode === 'new' ? (
              <div className="mt-5 space-y-4">
                <Field label="Name of the building">
                  <input className={inputClass} value={name} onChange={(e) => setName(e.target.value)} placeholder="Kinoru Apartments" maxLength={80} autoFocus />
                </Field>
                <div className="grid grid-cols-2 gap-3">
                  <Field label="Town or estate (optional)">
                    <input className={inputClass} value={town} onChange={(e) => setTown(e.target.value)} placeholder="Makutano" maxLength={60} />
                  </Field>
                  <Field label="County (optional)">
                    <input className={inputClass} value={county} onChange={(e) => setCounty(e.target.value)} placeholder="Meru" maxLength={60} />
                  </Field>
                </div>
                <Field label="Directions or address (optional)">
                  <input className={inputClass} value={address} onChange={(e) => setAddress(e.target.value)} placeholder="Opposite the main stage" maxLength={200} />
                </Field>
              </div>
            ) : (
              <div className="mt-5">
                <Field label="Choose the building">
                  <select className={inputClass} value={propertyId} onChange={(e) => setPropertyId(e.target.value)}>
                    <option value="">Choose...</option>
                    {properties.map((prop) => (
                      <option key={prop.property_id} value={prop.property_id}>
                        {prop.name}
                      </option>
                    ))}
                  </select>
                </Field>
              </div>
            )}

            <button
              onClick={() => setStep(2)}
              disabled={!step1Ready}
              className="mt-6 flex w-full items-center justify-center gap-2 rounded-xl bg-forest-900 py-3.5 font-semibold text-white hover:bg-forest-700 disabled:opacity-50"
            >
              Next: the units <ArrowRight size={18} />
            </button>
          </motion.div>
        )}

        {/* Step 2: the units */}
        {step === 2 && (
          <motion.div key="step2" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="mt-6">
            <div className="rounded-3xl bg-paper p-6 shadow-sm">
              <h2 className="font-display text-xl font-bold text-forest-900">What units does it have?</h2>
              <p className="mt-1 text-sm text-muted">
                Type the unit numbers as <span className="font-semibold text-forest-900">ranges</span>, like <span className="font-mono">A1-A12, B1-B6, Shop 1-4</span>. If the building has different kinds of units, add another group for each kind.
              </p>

              <div className="mt-5 space-y-4">
                {groups.map((group, index) => (
                  <div key={group.id} className="rounded-2xl bg-cream p-4">
                    <div className="flex items-center justify-between">
                      <p className="text-sm font-bold text-forest-900">Kind of unit {index + 1}</p>
                      {groups.length > 1 && (
                        <button onClick={() => setGroups(groups.filter((item) => item.id !== group.id))} aria-label="Remove this group" className="rounded-lg p-1.5 text-muted hover:bg-terracotta/10 hover:text-terracotta">
                          <Trash2 size={16} />
                        </button>
                      )}
                    </div>
                    <div className="mt-3 space-y-3">
                      <Field label="Unit numbers">
                        <input className={inputClass} value={group.labels} onChange={(e) => changeGroup(group.id, { labels: e.target.value })} placeholder="A1-A12, B1-B6" autoComplete="off" />
                      </Field>
                      <div className="grid grid-cols-2 gap-3">
                        <Field label="Type">
                          <select className={inputClass} value={group.type} onChange={(e) => changeGroup(group.id, { type: e.target.value })}>
                            <option value="">Not set</option>
                            {UNIT_TYPES.map((type) => (
                              <option key={type} value={type}>
                                {type}
                              </option>
                            ))}
                          </select>
                        </Field>
                        {group.type === 'Other' ? (
                          <Field label="Type name">
                            <input className={inputClass} value={group.otherType} onChange={(e) => changeGroup(group.id, { otherType: e.target.value })} maxLength={40} />
                          </Field>
                        ) : (
                          <div />
                        )}
                        <Field label="Rent per month (KSh)">
                          <input className={inputClass} type="number" min="0" step="1" inputMode="numeric" value={group.rent} onChange={(e) => changeGroup(group.id, { rent: e.target.value })} placeholder="6000" />
                        </Field>
                        <Field label="Deposit (KSh)">
                          <input className={inputClass} type="number" min="0" step="1" inputMode="numeric" value={group.deposit} onChange={(e) => changeGroup(group.id, { deposit: e.target.value })} placeholder="6000" />
                        </Field>
                      </div>
                      <button type="button" onClick={() => changeGroup(group.id, { deposit: group.rent })} className="text-sm font-semibold text-forest-700 hover:underline">
                        Deposit is the same as the rent
                      </button>
                    </div>
                  </div>
                ))}
              </div>

              {groups.length < MAX_GROUPS && (
                <button onClick={() => setGroups([...groups, newGroup()])} className="mt-4 flex items-center gap-2 rounded-xl bg-forest-100 px-4 py-2.5 text-sm font-semibold text-forest-700 hover:bg-forest-200">
                  <Plus size={16} /> Add another kind of unit
                </button>
              )}

              {mode === 'existing' && (
                <button onClick={() => setSkipExisting(!skipExisting)} className="mt-4 flex w-full items-center justify-between gap-3 rounded-xl bg-cream px-4 py-3 text-left">
                  <span>
                    <span className="block text-sm font-semibold text-forest-900">Skip unit numbers that already exist</span>
                    <span className="block text-xs text-muted">{skipExisting ? 'Existing ones are left alone.' : 'An existing number will be reported as a problem.'}</span>
                  </span>
                  <span className={`relative h-6 w-11 shrink-0 rounded-full transition ${skipExisting ? 'bg-forest-500' : 'bg-forest-200'}`}>
                    <span className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-all ${skipExisting ? 'left-[22px]' : 'left-0.5'}`} />
                  </span>
                </button>
              )}
            </div>

            {/* The live preview */}
            <div className="mt-4 rounded-3xl bg-forest-900 p-6 text-white shadow-xl">
              <div className="flex items-center justify-between">
                <h3 className="font-display text-lg font-bold">What will be made</h3>
                {previewBusy && <Loader2 size={18} className="animate-spin text-forest-200" />}
              </div>
              {!preview && <p className="mt-2 text-sm text-forest-200">Type some unit numbers above, and you will see them here.</p>}
              {preview && (
                <>
                  <p className="mt-2 text-sm text-forest-200">
                    {preview.new_property ? `New building “${preview.property_name}”` : preview.property_name}
                  </p>
                  <p className="font-display text-4xl font-extrabold text-gold">
                    {preview.will_add} <span className="text-lg font-semibold text-white">unit{preview.will_add === 1 ? '' : 's'}</span>
                  </p>
                  {preview.potential_rent > 0 && <p className="text-sm text-forest-200">{money(preview.potential_rent)} a month when every unit is let</p>}
                  {preview.skipped > 0 && <p className="mt-1 text-sm text-forest-200">{preview.skipped} skipped because they already exist.</p>}
                  <div className="mt-4 space-y-3">
                    {preview.groups.map((group, index) => (
                      <div key={index} className="rounded-2xl bg-white/10 p-3">
                        <p className="text-xs text-forest-200">
                          {group.unit_type || 'Units'} · {group.rent_amount ? money(group.rent_amount) : 'no rent set'}
                        </p>
                        <div className="mt-2 flex flex-wrap gap-1.5">
                          {group.labels.slice(0, 60).map((label) => (
                            <span key={label} className="rounded-lg bg-white/15 px-2 py-0.5 text-xs font-semibold">
                              {label}
                            </span>
                          ))}
                          {group.labels.length > 60 && <span className="px-1 text-xs text-forest-200">+{group.labels.length - 60} more</span>}
                        </div>
                      </div>
                    ))}
                  </div>
                  {preview.problems.length > 0 && (
                    <ul className="mt-4 space-y-1.5 rounded-2xl bg-terracotta/30 p-3 text-sm">
                      {preview.problems.map((problem) => (
                        <li key={problem} className="flex items-start gap-2">
                          <AlertCircle size={16} className="mt-0.5 shrink-0" /> {problem}
                        </li>
                      ))}
                    </ul>
                  )}
                </>
              )}
            </div>

            {error && (
              <div role="alert" className="mt-4 rounded-xl bg-terracotta/10 px-4 py-3 text-sm font-medium text-terracotta">
                {error}
              </div>
            )}

            <div className="mt-4 flex gap-3">
              <button onClick={() => setStep(1)} className="flex items-center justify-center gap-2 rounded-xl bg-forest-100 px-5 py-3.5 font-semibold text-forest-700 hover:bg-forest-200">
                <ArrowLeft size={18} /> Back
              </button>
              <button
                onClick={save}
                disabled={!preview || !preview.ok || previewBusy || saving}
                className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-forest-500 py-3.5 font-semibold text-white shadow-lg hover:bg-forest-700 disabled:opacity-50"
              >
                {saving && <Loader2 size={18} className="animate-spin" />}
                {preview && preview.ok ? `Create ${preview.will_add} unit${preview.will_add === 1 ? '' : 's'}` : 'Create'}
              </button>
            </div>
          </motion.div>
        )}

        {/* Step 3: done */}
        {step === 3 && done && (
          <motion.div key="step3" initial={{ opacity: 0, scale: 0.96 }} animate={{ opacity: 1, scale: 1 }} className="mt-6 rounded-3xl bg-paper p-8 text-center shadow-sm">
            <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-3xl bg-forest-100 text-forest-500">
              <CheckCircle2 size={34} />
            </div>
            <h2 className="mt-4 font-display text-2xl font-bold text-forest-900">
              {done.created} unit{done.created === 1 ? '' : 's'} added to {done.property_name}
            </h2>
            <p className="mt-1 text-sm text-muted">They are all empty for now. Next, add the tenants who live there.</p>
            <div className="mt-6 grid gap-3 sm:grid-cols-2">
              <Link to="/setup" className="flex items-center justify-center gap-2 rounded-xl bg-forest-900 px-5 py-3.5 text-sm font-semibold text-white hover:bg-forest-700">
                <Users size={16} /> Add the tenants
              </Link>
              <Link to={`/properties/${done.property_id}`} className="flex items-center justify-center gap-2 rounded-xl bg-forest-100 px-5 py-3.5 text-sm font-semibold text-forest-700 hover:bg-forest-200">
                <Building2 size={16} /> See the building
              </Link>
            </div>
            <p className="mt-4 text-xs text-muted">
              Tip: in your tenant list, you can leave the rent empty. It is filled in from the unit.
            </p>
            <button onClick={reset} className="mt-5 text-sm font-semibold text-forest-700 hover:underline">
              Add another building
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}