// Import the React tools we need
import { useCallback, useEffect, useState } from 'react'
// Import the page-switching tools
import { Link, useNavigate, useParams } from 'react-router-dom'
// Import the animation tool
import { motion } from 'framer-motion'
// Import the icons we use
import { ArrowLeft, DoorOpen, MapPin, Pencil, Plus, RefreshCw, Trash2, User } from 'lucide-react'
// Import our own files
import {
  createUnit,
  deleteProperty,
  deleteUnit,
  getLeases,
  getProperty,
  getUnits,
  updateProperty,
  updateUnit,
} from '../api'
import { money } from '../format'
import ConfirmDialog from '../components/ConfirmDialog'
import Modal from '../components/Modal'
import PropertyForm from '../components/PropertyForm'
import UnitForm from '../components/UnitForm'

// How the unit cards appear: one after another
const listAnimation = { hidden: {}, show: { transition: { staggerChildren: 0.05 } } }
// How each card appears: fade in while sliding up
const itemAnimation = { hidden: { opacity: 0, y: 14 }, show: { opacity: 1, y: 0 } }

// The colors and words for each unit status
const STATUS_STYLES = {
  occupied: 'bg-forest-100 text-forest-700',
  vacant: 'bg-amber/20 text-amber',
  maintenance: 'bg-ink/10 text-muted',
}
const STATUS_LABELS = { occupied: 'Occupied', vacant: 'Vacant', maintenance: 'Under repair' }

// A small colored label showing a unit's status
function StatusPill({ status }) {
  return (
    <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${STATUS_STYLES[status]}`}>
      {STATUS_LABELS[status]}
    </span>
  )
}

// The page for one property and the units inside it
export default function PropertyDetail() {
  // Read the property id from the address, like /properties/1
  const { id } = useParams()
  // Lets us jump to another page
  const navigate = useNavigate()
  // The property, its units, and its current leases (nothing until they arrive)
  const [property, setProperty] = useState(null)
  const [units, setUnits] = useState(null)
  const [leases, setLeases] = useState([])
  // The error message, if loading failed
  const [error, setError] = useState('')
  // Which pop-ups are open
  const [editingProperty, setEditingProperty] = useState(false)
  const [deletingProperty, setDeletingProperty] = useState(false)
  const [addingUnit, setAddingUnit] = useState(false)
  const [editingUnit, setEditingUnit] = useState(null)
  const [deletingUnit, setDeletingUnit] = useState(null)

  // Load the property, its units, and who is living in them
  const load = useCallback(() => {
    setError('')
    Promise.all([getProperty(id), getUnits(id), getLeases({ property_id: id, status: 'active' })])
      .then(([prop, unitList, leaseList]) => {
        setProperty(prop)
        setUnits(unitList)
        setLeases(leaseList)
      })
      .catch((err) => setError(err.message))
  }, [id])

  // Load everything when the page opens
  useEffect(() => {
    load()
  }, [load])

  // If loading failed (for example, this property is not yours), show the message
  if (error && !property) {
    return (
      <div>
        <Link to="/properties" className="flex items-center gap-1 text-sm font-medium text-forest-700">
          <ArrowLeft size={16} /> Properties
        </Link>
        <div className="mt-6 rounded-3xl bg-terracotta/10 p-6 text-terracotta">
          <p className="font-semibold">{error}</p>
          <button onClick={load} className="mt-4 flex items-center gap-2 rounded-xl bg-terracotta px-4 py-2 text-sm font-semibold text-white">
            <RefreshCw size={16} /> Try again
          </button>
        </div>
      </div>
    )
  }

  // While waiting, show grey placeholder boxes
  if (!property || !units) {
    return (
      <div className="space-y-4">
        <div className="h-40 animate-pulse rounded-3xl bg-forest-100" />
        <div className="h-28 animate-pulse rounded-2xl bg-forest-100" />
      </div>
    )
  }

  // Match each occupied unit with its tenant's lease
  const leaseByUnit = {}
  leases.forEach((lease) => {
    leaseByUnit[lease.unit_id] = lease
  })
  // Count the units by status
  const occupied = units.filter((u) => u.status === 'occupied').length
  const vacant = units.filter((u) => u.status === 'vacant').length
  const repairs = units.filter((u) => u.status === 'maintenance').length

  return (
    <div>
      {/* The link back to the list */}
      <Link to="/properties" className="inline-flex items-center gap-1 text-sm font-medium text-forest-700 hover:underline">
        <ArrowLeft size={16} /> Properties
      </Link>

      {/* The green header card */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        className="mt-3 rounded-3xl bg-forest-900 p-6 text-white shadow-xl"
      >
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <h1 className="text-3xl font-extrabold">{property.name}</h1>
            <p className="mt-1 flex items-center gap-1 text-forest-200">
              <MapPin size={15} className="shrink-0" />
              {[property.town, property.county].filter(Boolean).join(', ') || 'No location yet'}
            </p>
            {property.address && <p className="mt-1 text-sm text-forest-200">{property.address}</p>}
          </div>
          <div className="flex shrink-0 gap-2">
            <button
              onClick={() => setEditingProperty(true)}
              aria-label="Edit property"
              className="rounded-xl bg-white/10 p-2.5 hover:bg-white/20"
            >
              <Pencil size={18} />
            </button>
            <button
              onClick={() => setDeletingProperty(true)}
              aria-label="Delete property"
              className="rounded-xl bg-white/10 p-2.5 hover:bg-terracotta"
            >
              <Trash2 size={18} />
            </button>
          </div>
        </div>
        {/* The unit counts */}
        <div className="mt-5 grid grid-cols-3 gap-3 text-center">
          <div className="rounded-2xl bg-white/10 p-3">
            <p className="font-display text-2xl font-bold">{occupied}</p>
            <p className="text-xs text-forest-200">Occupied</p>
          </div>
          <div className="rounded-2xl bg-white/10 p-3">
            <p className="font-display text-2xl font-bold">{vacant}</p>
            <p className="text-xs text-forest-200">Vacant</p>
          </div>
          <div className="rounded-2xl bg-white/10 p-3">
            <p className="font-display text-2xl font-bold">{repairs}</p>
            <p className="text-xs text-forest-200">Under repair</p>
          </div>
        </div>
        {property.notes && <p className="mt-4 text-sm text-forest-200">{property.notes}</p>}
      </motion.div>

      {/* The units section */}
      <div className="mt-8 flex items-center justify-between">
        <h2 className="text-xl font-bold text-forest-900">Units ({units.length})</h2>
        <motion.button
          whileTap={{ scale: 0.96 }}
          onClick={() => setAddingUnit(true)}
          className="flex items-center gap-2 rounded-xl bg-forest-900 px-4 py-2.5 text-sm font-semibold text-white hover:bg-forest-700"
        >
          <Plus size={18} /> Add unit
        </motion.button>
      </div>

      {units.length === 0 ? (
        // No units yet
        <div className="mt-4 flex flex-col items-center rounded-3xl bg-paper p-10 text-center shadow-sm">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-forest-100 text-forest-700">
            <DoorOpen size={26} />
          </div>
          <p className="mt-4 font-semibold text-forest-900">No units yet</p>
          <p className="mt-1 text-sm text-muted">Add the houses or rooms inside this property.</p>
        </div>
      ) : (
        // One card for each unit
        <motion.div variants={listAnimation} initial="hidden" animate="show" className="mt-4 grid gap-3 md:grid-cols-2">
          {units.map((unit) => {
            // The tenant living here, if any
            const lease = leaseByUnit[unit.id]
            return (
              <motion.div key={unit.id} variants={itemAnimation} className="rounded-2xl bg-paper p-4 shadow-sm">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <p className="font-display text-xl font-bold text-forest-900">{unit.unit_number}</p>
                      <StatusPill status={unit.status} />
                    </div>
                    <p className="mt-0.5 text-sm text-muted">{unit.unit_type || 'No type set'}</p>
                  </div>
                  <div className="flex shrink-0 gap-1">
                    <button
                      onClick={() => setEditingUnit(unit)}
                      aria-label={`Edit unit ${unit.unit_number}`}
                      className="rounded-lg p-2 text-muted hover:bg-forest-100 hover:text-forest-900"
                    >
                      <Pencil size={16} />
                    </button>
                    <button
                      onClick={() => setDeletingUnit(unit)}
                      aria-label={`Delete unit ${unit.unit_number}`}
                      className="rounded-lg p-2 text-muted hover:bg-terracotta/10 hover:text-terracotta"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                </div>
                <div className="mt-3 flex items-end justify-between gap-3">
                  <div className="min-w-0">
                    <p className="font-semibold text-forest-900">
                      {money(unit.rent_amount)} <span className="text-xs font-normal text-muted">/ month</span>
                    </p>
                    <p className="text-xs text-muted">Deposit {money(unit.deposit_amount)}</p>
                  </div>
                  {/* The tenant's name, for occupied units */}
                  {lease && (
                    <p className="flex min-w-0 items-center gap-1 text-sm font-medium text-forest-700">
                      <User size={14} className="shrink-0" />
                      <span className="truncate">{lease.tenant_name}</span>
                    </p>
                  )}
                </div>
              </motion.div>
            )
          })}
        </motion.div>
      )}

      {/* Edit the property */}
      <Modal open={editingProperty} title="Edit property" onClose={() => setEditingProperty(false)}>
        <PropertyForm
          initial={property}
          submitLabel="Save changes"
          onCancel={() => setEditingProperty(false)}
          onSubmit={async (body) => {
            await updateProperty(id, body)
            setEditingProperty(false)
            load()
          }}
        />
      </Modal>

      {/* Delete the property */}
      <ConfirmDialog
        open={deletingProperty}
        title="Delete property?"
        message={`Delete ${property.name}? This cannot be undone. A property can only be deleted once it has no units.`}
        confirmLabel="Delete property"
        onClose={() => setDeletingProperty(false)}
        onConfirm={async () => {
          await deleteProperty(id)
          navigate('/properties')
        }}
      />

      {/* Add a unit */}
      <Modal open={addingUnit} title="Add unit" onClose={() => setAddingUnit(false)}>
        <UnitForm
          submitLabel="Add unit"
          onCancel={() => setAddingUnit(false)}
          onSubmit={async (body) => {
            await createUnit(id, body)
            setAddingUnit(false)
            load()
          }}
        />
      </Modal>

      {/* Edit a unit */}
      <Modal
        open={editingUnit !== null}
        title={editingUnit ? `Edit unit ${editingUnit.unit_number}` : 'Edit unit'}
        onClose={() => setEditingUnit(null)}
      >
        {editingUnit && (
          <UnitForm
            key={editingUnit.id}
            initial={editingUnit}
            submitLabel="Save changes"
            onCancel={() => setEditingUnit(null)}
            onSubmit={async (body) => {
              await updateUnit(editingUnit.id, body)
              setEditingUnit(null)
              load()
            }}
          />
        )}
      </Modal>

      {/* Delete a unit */}
      <ConfirmDialog
        open={deletingUnit !== null}
        title="Delete unit?"
        message={
          deletingUnit
            ? `Delete unit ${deletingUnit.unit_number}? A unit that has ever had a tenant cannot be deleted.`
            : ''
        }
        confirmLabel="Delete unit"
        onClose={() => setDeletingUnit(null)}
        onConfirm={async () => {
          await deleteUnit(deletingUnit.id)
          setDeletingUnit(null)
          load()
        }}
      />
    </div>
  )
}