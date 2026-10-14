// Import the React tools we need
import { useCallback, useEffect, useMemo, useState } from 'react'
// Import the page-switching tools
import { Link, useNavigate } from 'react-router-dom'
// Import the animation tool
import { motion } from 'framer-motion'
// Import the icons we use
import { ChevronRight, RefreshCw, Search, UserPlus, Users } from 'lucide-react'
// Import our own files
import { createTenant, getLeases, getTenants, getUnitDirectory } from '../api'
import { initials, phoneLocal } from '../format'
import BalanceBadge from '../components/BalanceBadge'
import Modal from '../components/Modal'
import TenantForm from '../components/TenantForm'

// How the list appears: the cards come in one after another
const listAnimation = { hidden: {}, show: { transition: { staggerChildren: 0.04 } } }
// How each card appears: fade in while sliding up
const itemAnimation = { hidden: { opacity: 0, y: 12 }, show: { opacity: 1, y: 0 } }

// The filter buttons above the list
const FILTERS = [
  { key: 'all', label: 'All' },
  { key: 'owing', label: 'Owing' },
  { key: 'nounit', label: 'No unit' },
]

// The page that lists all the tenants
export default function Tenants() {
  // Lets us jump to another page
  const navigate = useNavigate()
  // The data from the backend (nothing until it arrives)
  const [data, setData] = useState(null)
  // The error message, if loading failed
  const [error, setError] = useState('')
  // What is typed in the search box
  const [search, setSearch] = useState('')
  // Which filter button is chosen
  const [filter, setFilter] = useState('all')
  // Whether the "add tenant" pop-up is open
  const [adding, setAdding] = useState(false)

  // Load the tenants, all their leases, and the unit names
  const load = useCallback(() => {
    setError('')
    Promise.all([getTenants(), getLeases(), getUnitDirectory()])
      .then(([tenants, leases, directory]) => {
        // Make a quick lookup from a unit's id to its details
        const unitById = Object.fromEntries(directory.units.map((unit) => [unit.id, unit]))
        setData({ tenants, leases, unitById })
      })
      .catch((err) => setError(err.message))
  }, [])

  // Load them when the page first opens
  useEffect(() => {
    load()
  }, [load])

  // Put each tenant together with their current unit and what they owe
  const rows = useMemo(() => {
    if (!data) return []
    return data.tenants.map((tenant) => {
      // All the leases this tenant has ever had
      const mine = data.leases.filter((lease) => lease.tenant_id === tenant.id)
      // The lease they are living under now (if any)
      const active = mine.find((lease) => lease.status === 'active') || null
      // Everything they owe across all their leases
      const balance = mine.reduce((sum, lease) => sum + lease.balance, 0)
      // The unit they live in
      const info = active ? data.unitById[active.unit_id] : null
      return { tenant, active, balance, info }
    })
  }, [data])

  // Apply the search and the filter
  const visible = rows.filter((row) => {
    // Prepare what was typed: letters for names, digits for phone numbers
    const query = search.trim().toLowerCase()
    const digits = query.replace(/\D/g, '')
    const phoneQuery = digits.startsWith('0') ? `254${digits.slice(1)}` : digits
    // Does the search match the name, the phone number, or the unit number?
    const matchesSearch =
      !query ||
      row.tenant.full_name.toLowerCase().includes(query) ||
      (phoneQuery.length >= 3 && row.tenant.phone.includes(phoneQuery)) ||
      (row.info && row.info.unit_number.toLowerCase().includes(query))
    // Does the tenant pass the chosen filter?
    const matchesFilter =
      filter === 'all' || (filter === 'owing' && row.balance > 0) || (filter === 'nounit' && !row.active)
    return matchesSearch && matchesFilter
  })

  // Save a new tenant, then open their page with the move-in pop-up ready
  async function handleCreate(body) {
    const created = await createTenant(body)
    setAdding(false)
    navigate(`/tenants/${created.id}`, { state: { moveIn: true } })
  }

  return (
    <div>
      {/* The title and the add button */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-extrabold text-forest-900">Tenants</h1>
          <p className="text-muted">Everyone renting from you.</p>
        </div>
        <motion.button
          whileTap={{ scale: 0.96 }}
          onClick={() => setAdding(true)}
          className="flex shrink-0 items-center gap-2 rounded-xl bg-forest-900 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-forest-900/20 hover:bg-forest-700"
        >
          <UserPlus size={18} /> Add tenant
        </motion.button>
      </div>

      {/* If loading failed, show the message and a retry button */}
      {error && (
        <div className="mt-6 rounded-3xl bg-terracotta/10 p-6 text-terracotta">
          <p className="font-semibold">Could not load your tenants</p>
          <p className="mt-1 text-sm">{error}</p>
          <button onClick={load} className="mt-4 flex items-center gap-2 rounded-xl bg-terracotta px-4 py-2 text-sm font-semibold text-white">
            <RefreshCw size={16} /> Try again
          </button>
        </div>
      )}

      {/* While waiting, show grey placeholder boxes */}
      {!error && !data && (
        <div className="mt-6 space-y-3">
          <div className="h-12 animate-pulse rounded-xl bg-forest-100" />
          <div className="h-20 animate-pulse rounded-2xl bg-forest-100" />
          <div className="h-20 animate-pulse rounded-2xl bg-forest-100" />
        </div>
      )}

      {/* If there are no tenants yet, invite the person to add one */}
      {data && data.tenants.length === 0 && (
        <div className="mt-10 flex flex-col items-center rounded-3xl bg-paper p-10 text-center shadow-sm">
          <div className="flex h-16 w-16 items-center justify-center rounded-3xl bg-forest-100 text-forest-700">
            <Users size={28} />
          </div>
          <h2 className="mt-5 text-xl font-bold text-forest-900">No tenants yet</h2>
          <p className="mt-1 max-w-xs text-muted">Add a tenant, then move them into a vacant unit.</p>
          <button
            onClick={() => setAdding(true)}
            className="mt-5 flex items-center gap-2 rounded-xl bg-forest-900 px-5 py-3 text-sm font-semibold text-white hover:bg-forest-700"
          >
            <UserPlus size={18} /> Add tenant
          </button>
        </div>
      )}

      {data && data.tenants.length > 0 && (
        <>
          {/* The search box and the filter buttons */}
          <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:items-center">
            <div className="relative flex-1">
              <Search size={18} className="absolute left-4 top-1/2 -translate-y-1/2 text-muted" />
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search by name, phone, or unit"
                className="w-full rounded-xl border border-forest-200 bg-paper py-3 pl-11 pr-4 outline-none transition focus:border-forest-500 focus:ring-4 focus:ring-forest-100"
              />
            </div>
            <div className="flex gap-2">
              {FILTERS.map((item) => (
                <button
                  key={item.key}
                  onClick={() => setFilter(item.key)}
                  className={`rounded-full px-4 py-2 text-sm font-semibold transition ${
                    filter === item.key ? 'bg-forest-900 text-white' : 'bg-paper text-forest-700 hover:bg-forest-100'
                  }`}
                >
                  {item.label}
                </button>
              ))}
            </div>
          </div>

          {/* The list of tenants */}
          {visible.length === 0 ? (
            <p className="mt-8 text-center text-muted">No tenants match that.</p>
          ) : (
            <motion.div
              key={`${filter}-${search}`}
              variants={listAnimation}
              initial="hidden"
              animate="show"
              className="mt-4 grid gap-3 md:grid-cols-2"
            >
              {visible.map(({ tenant, active, balance, info }) => (
                <motion.div key={tenant.id} variants={itemAnimation}>
                  <Link
                    to={`/tenants/${tenant.id}`}
                    className="flex items-center gap-4 rounded-2xl bg-paper p-4 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md"
                  >
                    {/* The circle with the tenant's initials */}
                    <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-forest-100 font-display font-bold text-forest-700">
                      {initials(tenant.full_name)}
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="truncate font-semibold text-forest-900">{tenant.full_name}</p>
                      <p className="truncate text-sm text-muted">{phoneLocal(tenant.phone)}</p>
                      <p className="truncate text-xs text-muted">
                        {active ? `${active.unit_number}${info ? ` · ${info.property_name}` : ''}` : 'No unit'}
                      </p>
                    </div>
                    <div className="flex shrink-0 flex-col items-end gap-2">
                      <BalanceBadge amount={balance} />
                      <ChevronRight size={18} className="text-muted" />
                    </div>
                  </Link>
                </motion.div>
              ))}
            </motion.div>
          )}
        </>
      )}

      {/* The "add tenant" pop-up */}
      <Modal open={adding} title="Add tenant" onClose={() => setAdding(false)}>
        <TenantForm submitLabel="Add tenant" onCancel={() => setAdding(false)} onSubmit={handleCreate} />
      </Modal>
    </div>
  )
}