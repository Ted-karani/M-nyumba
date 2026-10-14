// Import the React tools we need
import { useCallback, useEffect, useState } from 'react'
// Import the page-switching tools
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'
// Import the animation tool
import { motion } from 'framer-motion'
// Import the icons we use
import { ArrowLeft, DoorOpen, Mail, MessageCircle, Pencil, Phone, RefreshCw, Trash2 } from 'lucide-react'
// Import our own files
import { createLease, deleteTenant, getLeases, getTenant, getUnitDirectory, updateTenant } from '../api'
import { initials, money, phoneLocal } from '../format'
import BalanceBadge from '../components/BalanceBadge'
import ConfirmDialog from '../components/ConfirmDialog'
import LeaseCard from '../components/LeaseCard'
import Modal from '../components/Modal'
import MoveInForm from '../components/MoveInForm'
import TenantForm from '../components/TenantForm'

// The page for one tenant
export default function TenantDetail() {
  // Read the tenant id from the address, like /tenants/3
  const { id } = useParams()
  // Lets us jump to another page, and read what the last page sent us
  const navigate = useNavigate()
  const location = useLocation()
  // The tenant, their leases, and the list of units (nothing until they arrive)
  const [tenant, setTenant] = useState(null)
  const [leases, setLeases] = useState(null)
  const [directory, setDirectory] = useState(null)
  // The error message, if loading failed
  const [error, setError] = useState('')
  // Which pop-ups are open
  const [editing, setEditing] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [movingIn, setMovingIn] = useState(false)

  // Load the tenant, their leases, and the units
  const load = useCallback(() => {
    setError('')
    Promise.all([getTenant(id), getLeases({ tenant_id: id }), getUnitDirectory()])
      .then(([tenantData, leaseList, dir]) => {
        setTenant(tenantData)
        setLeases(leaseList)
        setDirectory(dir)
      })
      .catch((err) => setError(err.message))
  }, [id])

  // Load everything when the page opens
  useEffect(() => {
    load()
  }, [load])

  // If we just came from "Add tenant", open the move-in pop-up straight away
  useEffect(() => {
    if (location.state && location.state.moveIn && directory) {
      setMovingIn(true)
      // Clear the message so a refresh does not open it again
      navigate(location.pathname, { replace: true, state: null })
    }
  }, [location.state, location.pathname, directory, navigate])

  // If loading failed (for example, this tenant is not yours), show the message
  if (error && !tenant) {
    return (
      <div>
        <Link to="/tenants" className="flex items-center gap-1 text-sm font-medium text-forest-700">
          <ArrowLeft size={16} /> Tenants
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
  if (!tenant || !leases || !directory) {
    return (
      <div className="space-y-4">
        <div className="h-44 animate-pulse rounded-3xl bg-forest-100" />
        <div className="h-56 animate-pulse rounded-3xl bg-forest-100" />
      </div>
    )
  }

  // Make a quick lookup from a unit's id to its details
  const unitById = Object.fromEntries(directory.units.map((unit) => [unit.id, unit]))
  // Active leases first, then the newest
  const sortedLeases = [...leases].sort(
    (a, b) => (a.status === 'active' ? 0 : 1) - (b.status === 'active' ? 0 : 1) || b.id - a.id
  )
  // Everything this tenant owes across all their leases
  const totalBalance = leases.reduce((sum, lease) => sum + lease.balance, 0)

  return (
    <div>
      {/* The link back to the list */}
      <Link to="/tenants" className="inline-flex items-center gap-1 text-sm font-medium text-forest-700 hover:underline">
        <ArrowLeft size={16} /> Tenants
      </Link>

      {/* The green header card */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        className="mt-3 rounded-3xl bg-forest-900 p-6 text-white shadow-xl"
      >
        <div className="flex items-start justify-between gap-4">
          <div className="flex min-w-0 items-center gap-4">
            <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-gold font-display text-lg font-bold text-forest-900">
              {initials(tenant.full_name)}
            </div>
            <div className="min-w-0">
              <h1 className="truncate text-2xl font-extrabold">{tenant.full_name}</h1>
              <p className="text-forest-200">{phoneLocal(tenant.phone)}</p>
            </div>
          </div>
          <div className="flex shrink-0 gap-2">
            <button onClick={() => setEditing(true)} aria-label="Edit tenant" className="rounded-xl bg-white/10 p-2.5 hover:bg-white/20">
              <Pencil size={18} />
            </button>
            <button onClick={() => setDeleting(true)} aria-label="Delete tenant" className="rounded-xl bg-white/10 p-2.5 hover:bg-terracotta">
              <Trash2 size={18} />
            </button>
          </div>
        </div>

        {/* Call and WhatsApp buttons */}
        <div className="mt-5 flex flex-wrap gap-2">
          <a href={`tel:+${tenant.phone}`} className="flex items-center gap-2 rounded-xl bg-white/10 px-4 py-2.5 text-sm font-semibold hover:bg-white/20">
            <Phone size={16} /> Call
          </a>
          <a
            href={`https://wa.me/${tenant.phone}`}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 rounded-xl bg-forest-500 px-4 py-2.5 text-sm font-semibold hover:bg-forest-700"
          >
            <MessageCircle size={16} /> WhatsApp
          </a>
          {tenant.email && (
            <a href={`mailto:${tenant.email}`} className="flex items-center gap-2 rounded-xl bg-white/10 px-4 py-2.5 text-sm font-semibold hover:bg-white/20">
              <Mail size={16} /> Email
            </a>
          )}
        </div>

        {/* The extra details, when there are any */}
        {(tenant.id_number || tenant.emergency_contact_name || tenant.notes) && (
          <div className="mt-5 space-y-1 border-t border-white/10 pt-4 text-sm text-forest-200">
            {tenant.id_number && <p>ID number: <span className="text-white">{tenant.id_number}</span></p>}
            {tenant.emergency_contact_name && (
              <p>
                Emergency contact:{' '}
                <span className="text-white">
                  {tenant.emergency_contact_name}
                  {tenant.emergency_contact_phone ? ` · ${phoneLocal(tenant.emergency_contact_phone)}` : ''}
                </span>
              </p>
            )}
            {tenant.notes && <p className="text-white">{tenant.notes}</p>}
          </div>
        )}
      </motion.div>

      {/* The leases section */}
      <div className="mt-8 flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <h2 className="text-xl font-bold text-forest-900">Leases</h2>
          {leases.length > 0 && <BalanceBadge amount={totalBalance} />}
        </div>
        <motion.button
          whileTap={{ scale: 0.96 }}
          onClick={() => setMovingIn(true)}
          className="flex items-center gap-2 rounded-xl bg-forest-900 px-4 py-2.5 text-sm font-semibold text-white hover:bg-forest-700"
        >
          <DoorOpen size={18} /> Move into a unit
        </motion.button>
      </div>

      {sortedLeases.length === 0 ? (
        // No leases yet
        <div className="mt-4 flex flex-col items-center rounded-3xl bg-paper p-10 text-center shadow-sm">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-forest-100 text-forest-700">
            <DoorOpen size={26} />
          </div>
          <p className="mt-4 font-semibold text-forest-900">Not in a unit yet</p>
          <p className="mt-1 max-w-xs text-sm text-muted">
            Move {tenant.full_name.split(' ')[0]} into a vacant unit. The deposit and first rent are charged automatically.
          </p>
        </div>
      ) : (
        // One card for each lease
        <div className="mt-4 space-y-4">
          {sortedLeases.map((lease) => (
            <LeaseCard key={lease.id} lease={lease} unitInfo={unitById[lease.unit_id]} onChanged={load} />
          ))}
        </div>
      )}

      {/* Edit the tenant */}
      <Modal open={editing} title="Edit tenant" onClose={() => setEditing(false)}>
        <TenantForm
          initial={tenant}
          submitLabel="Save changes"
          onCancel={() => setEditing(false)}
          onSubmit={async (body) => {
            await updateTenant(id, body)
            setEditing(false)
            load()
          }}
        />
      </Modal>

      {/* Move the tenant into a unit */}
      <Modal open={movingIn} title="Move in" onClose={() => setMovingIn(false)}>
        <MoveInForm
          tenant={tenant}
          directory={directory}
          onCancel={() => setMovingIn(false)}
          onSubmit={async (body) => {
            await createLease({ ...body, tenant_id: tenant.id })
            setMovingIn(false)
            load()
          }}
        />
      </Modal>

      {/* Delete the tenant */}
      <ConfirmDialog
        open={deleting}
        title="Delete tenant?"
        message={`Delete ${tenant.full_name}? This cannot be undone. A tenant who has ever had a lease cannot be deleted. (Balance now: ${money(totalBalance)})`}
        confirmLabel="Delete tenant"
        onClose={() => setDeleting(false)}
        onConfirm={async () => {
          await deleteTenant(id)
          navigate('/tenants')
        }}
      />
    </div>
  )
}