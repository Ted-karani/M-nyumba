// Import the React tools we need
import { useEffect, useState } from 'react'
// Import the page-switching tool
import { Link } from 'react-router-dom'
// Import the animation tool
import { motion } from 'framer-motion'
// Import the icons we use
import { ChevronRight, FileSignature } from 'lucide-react'
// Import our own files
import { getSettlements } from '../api'
import { formatDate, money } from '../format'

// What each state looks like
const STATES = {
  refund_pending: { label: 'Refund to pay', tone: 'bg-gold/30 text-forest-900' },
  to_settle: { label: 'Not settled yet', tone: 'bg-amber/20 text-amber' },
  draft: { label: 'Draft', tone: 'bg-forest-100 text-forest-700' },
  tenant_owes: { label: 'Tenant owes you', tone: 'bg-terracotta/15 text-terracotta' },
  part_refunded: { label: 'Part refunded', tone: 'bg-gold/30 text-forest-900' },
  refunded: { label: 'Refunded', tone: 'bg-forest-100 text-forest-700' },
  nothing_to_refund: { label: 'Settled', tone: 'bg-forest-100 text-forest-700' },
}

// The page that lists tenants who moved out, and their deposit settlements
export default function Settlements() {
  const [rows, setRows] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    getSettlements()
      .then(setRows)
      .catch((err) => setError(err.message))
  }, [])

  return (
    <div className="mx-auto max-w-3xl">
      <div className="flex items-center gap-3">
        <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gold/25 text-forest-900">
          <FileSignature size={22} />
        </div>
        <div>
          <h1 className="text-3xl font-extrabold text-forest-900">Move-out settlements</h1>
          <p className="text-muted">Work out the deposit refund when a tenant leaves, and print a statement.</p>
        </div>
      </div>

      {error && (
        <div role="alert" className="mt-5 rounded-xl bg-terracotta/10 px-4 py-3 text-sm font-medium text-terracotta">
          {error}
        </div>
      )}
      {!rows && !error && <div className="mt-5 h-32 animate-pulse rounded-3xl bg-forest-100" />}
      {rows && rows.length === 0 && (
        <p className="mt-5 rounded-3xl bg-paper p-6 text-sm text-muted shadow-sm">
          No tenant has moved out yet. When you end a tenancy, the tenant appears here so you can settle their deposit.
        </p>
      )}

      {rows && rows.length > 0 && (
        <ul className="mt-5 space-y-3">
          {rows.map((row) => {
            const state = STATES[row.state]
            return (
              <motion.li key={row.lease_id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
                <Link to={`/settlements/${row.lease_id}`} className="flex items-center justify-between gap-3 rounded-2xl bg-paper p-4 shadow-sm transition hover:shadow-md">
                  <div className="min-w-0">
                    <p className="truncate font-semibold text-forest-900">{row.tenant_name}</p>
                    <p className="truncate text-sm text-muted">
                      {row.unit_number}, {row.property_name}
                      {row.ended_on ? ` · moved out ${formatDate(row.ended_on)}` : ''}
                    </p>
                  </div>
                  <div className="flex shrink-0 items-center gap-3">
                    <div className="text-right">
                      <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${state.tone}`}>{state.label}</span>
                      {row.refund_due > 0 && <p className="mt-1 text-xs font-semibold text-forest-900">{money(row.refund_due)}</p>}
                      {row.tenant_owes > 0 && <p className="mt-1 text-xs font-semibold text-terracotta">{money(row.tenant_owes)}</p>}
                    </div>
                    <ChevronRight size={18} className="text-muted" />
                  </div>
                </Link>
              </motion.li>
            )
          })}
        </ul>
      )}
    </div>
  )
}