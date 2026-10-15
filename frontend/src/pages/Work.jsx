// Import the React tools we need
import { useCallback, useEffect, useState } from 'react'
// Import the page-switching tools
import { Link, useNavigate } from 'react-router-dom'
// Import the animation tool
import { motion } from 'framer-motion'
// Import the icons we use
import { Building2, Loader2, MessageCircle, Phone, Plus, RefreshCw, Wrench } from 'lucide-react'
// Import our own files
import { useAuth } from '../AuthContext'
import { getWorkProperties, setUnitStatus } from '../api'
import { phoneLocal } from '../format'

// How the list appears: the cards come in one after another
const listAnimation = { hidden: {}, show: { transition: { staggerChildren: 0.07 } } }
// How each card appears: fade in while sliding up
const itemAnimation = { hidden: { opacity: 0, y: 16 }, show: { opacity: 1, y: 0 } }

// The colors and words for each unit status
const STATUS_STYLES = {
  occupied: { label: 'Occupied', style: 'bg-forest-100 text-forest-700' },
  vacant: { label: 'Vacant', style: 'bg-amber/20 text-amber' },
  maintenance: { label: 'Under repair', style: 'bg-ink/10 text-muted' },
}

// Pick a greeting based on the time of day
function greeting() {
  // The current hour, from 0 to 23
  const hour = new Date().getHours()
  if (hour < 12) return 'Good morning'
  if (hour < 17) return 'Good afternoon'
  return 'Good evening'
}

// One unit: its status, its tenant, and the buttons a caretaker needs
function UnitRow({ unit, onChanged }) {
  // True while we wait for the backend, and any error message
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  // The label and colors for this unit's status
  const info = STATUS_STYLES[unit.status]

  // Switch an empty unit between vacant and under repair
  async function toggle() {
    setError('')
    setBusy(true)
    try {
      await setUnitStatus(unit.unit_id, unit.status === 'vacant' ? 'maintenance' : 'vacant')
      onChanged()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <p className="font-display text-lg font-bold text-forest-900">{unit.unit_number}</p>
            <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${info.style}`}>{info.label}</span>
          </div>
          <p className="text-sm text-muted">{unit.unit_type || 'No type set'}</p>
        </div>
        {/* Open problems in this unit link to the repairs page */}
        {unit.open_repairs > 0 && (
          <Link to="/repairs" className="flex shrink-0 items-center gap-1 rounded-full bg-terracotta/15 px-2.5 py-1 text-xs font-semibold text-terracotta">
            <Wrench size={12} /> {unit.open_repairs} open
          </Link>
        )}
      </div>

      {/* The tenant, with call and WhatsApp buttons */}
      {unit.tenant_name && (
        <div className="mt-3 flex items-center justify-between gap-3 rounded-xl bg-cream p-3">
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-forest-900">{unit.tenant_name}</p>
            <p className="text-xs text-muted">{phoneLocal(unit.tenant_phone)}</p>
          </div>
          <div className="flex shrink-0 gap-2">
            <a href={`tel:+${unit.tenant_phone}`} aria-label={`Call ${unit.tenant_name}`} className="rounded-lg bg-forest-100 p-2.5 text-forest-700 hover:bg-forest-200">
              <Phone size={16} />
            </a>
            <a
              href={`https://wa.me/${unit.tenant_phone}`}
              target="_blank"
              rel="noopener noreferrer"
              aria-label={`WhatsApp ${unit.tenant_name}`}
              className="rounded-lg bg-forest-500 p-2.5 text-white hover:bg-forest-700"
            >
              <MessageCircle size={16} />
            </a>
          </div>
        </div>
      )}

      {/* Empty units can be switched between vacant and under repair */}
      {unit.status !== 'occupied' && (
        <button
          onClick={toggle}
          disabled={busy}
          className="mt-3 flex items-center gap-2 rounded-xl bg-forest-100 px-4 py-2 text-sm font-semibold text-forest-700 hover:bg-forest-200 disabled:opacity-60"
        >
          {busy && <Loader2 size={14} className="animate-spin" />}
          {unit.status === 'vacant' ? 'Mark under repair' : 'Mark vacant'}
        </button>
      )}
      {error && <p className="mt-2 text-sm font-medium text-terracotta">{error}</p>}
    </div>
  )
}

// The caretaker's home screen
export default function Work() {
  // Get the logged-in user and the tool for jumping to another page
  const { user } = useAuth()
  const navigate = useNavigate()
  // The properties from the backend (nothing until they arrive)
  const [properties, setProperties] = useState(null)
  // The error message, if loading failed
  const [error, setError] = useState('')

  // Load the properties (a quiet reload keeps the old list on screen)
  const load = useCallback((quiet = false) => {
    setError('')
    if (!quiet) setProperties(null)
    getWorkProperties()
      .then(setProperties)
      .catch((err) => setError(err.message))
  }, [])

  // Load them when the page opens
  useEffect(() => {
    load()
  }, [load])

  // Use only the first name in the greeting
  const firstName = user.full_name.split(' ')[0]

  return (
    <div>
      {/* The greeting and the report button */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-muted">{greeting()}</p>
          <h1 className="text-3xl font-extrabold text-forest-900">{firstName}</h1>
        </div>
        <motion.button
          whileTap={{ scale: 0.96 }}
          onClick={() => navigate('/repairs', { state: { add: true } })}
          className="flex shrink-0 items-center gap-2 rounded-xl bg-forest-900 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-forest-900/20 hover:bg-forest-700"
        >
          <Plus size={18} /> Report a problem
        </motion.button>
      </div>

      {/* If loading failed, show the message and a retry button */}
      {error && (
        <div className="mt-6 rounded-3xl bg-terracotta/10 p-6 text-terracotta">
          <p className="font-semibold">Could not load your properties</p>
          <p className="mt-1 text-sm">{error}</p>
          <button onClick={() => load()} className="mt-4 flex items-center gap-2 rounded-xl bg-terracotta px-4 py-2 text-sm font-semibold text-white">
            <RefreshCw size={16} /> Try again
          </button>
        </div>
      )}

      {/* While waiting, show grey placeholder boxes */}
      {!error && !properties && (
        <div className="mt-6 space-y-3">
          <div className="h-32 animate-pulse rounded-3xl bg-forest-100" />
          <div className="h-32 animate-pulse rounded-3xl bg-forest-100" />
        </div>
      )}

      {/* If no properties were assigned yet, say so */}
      {properties && properties.length === 0 && (
        <div className="mt-8 flex flex-col items-center rounded-3xl bg-paper p-10 text-center shadow-sm">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-forest-100 text-forest-700">
            <Building2 size={26} />
          </div>
          <p className="mt-4 font-semibold text-forest-900">No properties assigned yet</p>
          <p className="mt-1 max-w-xs text-sm text-muted">Ask the owner to assign you to the properties you look after.</p>
        </div>
      )}

      {/* One card for each property, with its units */}
      {properties && properties.length > 0 && (
        <motion.div variants={listAnimation} initial="hidden" animate="show" className="mt-6 space-y-6">
          {properties.map((prop) => {
            // Count the units by status
            const vacant = prop.units.filter((u) => u.status === 'vacant').length
            const repairs = prop.units.filter((u) => u.status === 'maintenance').length
            return (
              <motion.div key={prop.property_id} variants={itemAnimation}>
                {/* The green header */}
                <div className="rounded-t-3xl bg-forest-900 p-5 text-white">
                  <p className="font-display text-2xl font-bold">{prop.name}</p>
                  <p className="text-sm text-forest-200">{[prop.town, prop.county].filter(Boolean).join(', ') || 'No location yet'}</p>
                  <p className="mt-3 text-sm text-forest-100">
                    {prop.units.length} units · {vacant} vacant · {repairs} under repair
                    {prop.open_repairs > 0 ? ` · ${prop.open_repairs} open problem${prop.open_repairs === 1 ? '' : 's'}` : ''}
                  </p>
                </div>
                {/* The units */}
                <div className="divide-y divide-forest-100 overflow-hidden rounded-b-3xl bg-paper shadow-sm">
                  {prop.units.length === 0 ? (
                    <p className="p-5 text-sm text-muted">No units in this property yet.</p>
                  ) : (
                    prop.units.map((unit) => <UnitRow key={unit.unit_id} unit={unit} onChanged={() => load(true)} />)
                  )}
                </div>
              </motion.div>
            )
          })}
        </motion.div>
      )}
    </div>
  )
}