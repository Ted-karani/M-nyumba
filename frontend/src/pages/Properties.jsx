// Import the React tools we need
import { useCallback, useEffect, useState } from 'react'
// Import the page-switching tools
import { Link, useNavigate } from 'react-router-dom'
// Import the animation tool
import { motion } from 'framer-motion'
// Import the icons we use
import { Building2, ChevronRight, MapPin, Plus, RefreshCw } from 'lucide-react'
// Import our own files
import { createProperty, getDashboard } from '../api'
import Modal from '../components/Modal'
import PropertyForm from '../components/PropertyForm'

// How the list appears: the cards come in one after another
const listAnimation = { hidden: {}, show: { transition: { staggerChildren: 0.07 } } }
// How each card appears: fade in while sliding up
const itemAnimation = { hidden: { opacity: 0, y: 16 }, show: { opacity: 1, y: 0 } }

// The page that lists all the properties
export default function Properties() {
  // Lets us jump to another page
  const navigate = useNavigate()
  // The list of properties (nothing until it arrives)
  const [properties, setProperties] = useState(null)
  // The error message, if loading failed
  const [error, setError] = useState('')
  // Whether the "add property" pop-up is open
  const [adding, setAdding] = useState(false)

  // Load the properties. The dashboard already counts the units in each one, so we reuse it.
  const load = useCallback(() => {
    setError('')
    getDashboard()
      .then((data) => setProperties(data.properties))
      .catch((err) => setError(err.message))
  }, [])

  // Load them when the page first opens
  useEffect(() => {
    load()
  }, [load])

  // Save a new property, then open its page so units can be added right away
  async function handleCreate(body) {
    const created = await createProperty(body)
    setAdding(false)
    navigate(`/properties/${created.id}`)
  }

  return (
    <div>
      {/* The title and the add button */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-extrabold text-forest-900">Properties</h1>
          <p className="text-muted">Every place you manage, in one list.</p>
        </div>
        <motion.button
          whileTap={{ scale: 0.96 }}
          onClick={() => setAdding(true)}
          className="flex shrink-0 items-center gap-2 rounded-xl bg-forest-900 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-forest-900/20 hover:bg-forest-700"
        >
          <Plus size={18} /> Add property
        </motion.button>
      </div>

      {/* If loading failed, show the message and a retry button */}
      {error && (
        <div className="mt-6 rounded-3xl bg-terracotta/10 p-6 text-terracotta">
          <p className="font-semibold">Could not load your properties</p>
          <p className="mt-1 text-sm">{error}</p>
          <button onClick={load} className="mt-4 flex items-center gap-2 rounded-xl bg-terracotta px-4 py-2 text-sm font-semibold text-white">
            <RefreshCw size={16} /> Try again
          </button>
        </div>
      )}

      {/* While waiting, show grey placeholder boxes */}
      {!error && !properties && (
        <div className="mt-6 grid gap-3 md:grid-cols-2">
          <div className="h-32 animate-pulse rounded-2xl bg-forest-100" />
          <div className="h-32 animate-pulse rounded-2xl bg-forest-100" />
        </div>
      )}

      {/* If there are no properties yet, invite the person to add one */}
      {properties && properties.length === 0 && (
        <div className="mt-10 flex flex-col items-center rounded-3xl bg-paper p-10 text-center shadow-sm">
          <div className="flex h-16 w-16 items-center justify-center rounded-3xl bg-forest-100 text-forest-700">
            <Building2 size={28} />
          </div>
          <h2 className="mt-5 text-xl font-bold text-forest-900">No properties yet</h2>
          <p className="mt-1 max-w-xs text-muted">Add your first property, then add the houses inside it.</p>
          <button
            onClick={() => setAdding(true)}
            className="mt-5 flex items-center gap-2 rounded-xl bg-forest-900 px-5 py-3 text-sm font-semibold text-white hover:bg-forest-700"
          >
            <Plus size={18} /> Add property
          </button>
        </div>
      )}

      {/* The list of properties */}
      {properties && properties.length > 0 && (
        <motion.div variants={listAnimation} initial="hidden" animate="show" className="mt-6 grid gap-3 md:grid-cols-2">
          {properties.map((prop) => (
            <motion.div key={prop.property_id} variants={itemAnimation}>
              <Link
                to={`/properties/${prop.property_id}`}
                className="block rounded-2xl bg-paper p-5 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate font-display text-lg font-bold text-forest-900">{prop.name}</p>
                    <p className="mt-0.5 flex items-center gap-1 truncate text-sm text-muted">
                      <MapPin size={14} className="shrink-0" />
                      {[prop.town, prop.county].filter(Boolean).join(', ') || 'No location yet'}
                    </p>
                  </div>
                  <ChevronRight className="shrink-0 text-muted" size={20} />
                </div>
                {/* A bar showing how full the property is */}
                <div className="mt-4 h-2 overflow-hidden rounded-full bg-forest-100">
                  <div className="h-full rounded-full bg-forest-500" style={{ width: `${prop.units.occupancy_percent}%` }} />
                </div>
                <p className="mt-2 text-sm text-muted">
                  <span className="font-semibold text-forest-700">
                    {prop.units.occupied}/{prop.units.total}
                  </span>{' '}
                  occupied · {prop.units.vacant} vacant
                </p>
              </Link>
            </motion.div>
          ))}
        </motion.div>
      )}

      {/* The "add property" pop-up */}
      <Modal open={adding} title="Add property" onClose={() => setAdding(false)}>
        <PropertyForm submitLabel="Add property" onCancel={() => setAdding(false)} onSubmit={handleCreate} />
      </Modal>
    </div>
  )
}