// Import the React tools we need
import { useCallback, useEffect, useState } from 'react'
// Import the page-switching tool
import { Link } from 'react-router-dom'
// Import the animation tool
import { motion } from 'framer-motion'
// Import the icons we use
import { Building2, Clock, PauseCircle, RefreshCw, Users, Wallet } from 'lucide-react'
// Import our own files
import { getAdminOverview } from '../api'
import { accessText } from '../admin'
import { formatDate, money } from '../format'

// A small number card
function Stat({ icon: Icon, label, value, note }) {
  return (
    <div className="rounded-2xl bg-paper p-4 shadow-sm">
      <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-forest-100 text-forest-700">
        <Icon size={18} />
      </div>
      <p className="mt-3 font-display text-2xl font-bold text-forest-900">{value}</p>
      <p className="text-sm text-muted">{label}</p>
      {note && <p className="mt-0.5 text-xs text-muted">{note}</p>}
    </div>
  )
}

// A short list of landlords that need attention
function Attention({ title, rows, empty }) {
  return (
    <div className="rounded-3xl bg-paper p-5 shadow-sm">
      <h2 className="font-display text-lg font-bold text-forest-900">{title}</h2>
      {rows.length === 0 ? (
        <p className="mt-2 text-sm text-muted">{empty}</p>
      ) : (
        <ul className="mt-2 divide-y divide-forest-100">
          {rows.map((row) => (
            <li key={row.owner_id} className="flex items-center justify-between gap-3 py-2.5">
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-forest-900">{row.full_name}</p>
                <p className="truncate text-xs text-muted">{row.email}</p>
              </div>
              <span className="shrink-0 text-xs font-medium text-ink/80">{accessText(row)}</span>
            </li>
          ))}
        </ul>
      )}
      <Link to="/accounts" className="mt-3 inline-block text-sm font-medium text-forest-700 hover:underline">
        Open the landlords list
      </Link>
    </div>
  )
}

// The admin's home page
export default function AdminOverview() {
  // The numbers (nothing until they arrive)
  const [data, setData] = useState(null)
  // The error message, if loading failed
  const [error, setError] = useState('')

  // Load the numbers
  const load = useCallback(() => {
    setError('')
    getAdminOverview()
      .then(setData)
      .catch((err) => setError(err.message))
  }, [])

  // Load them when the page opens
  useEffect(() => {
    load()
  }, [load])

  return (
    <div>
      <h1 className="text-3xl font-extrabold text-forest-900">Overview</h1>
      <p className="text-muted">How the business is doing.</p>

      {error && (
        <div className="mt-6 rounded-3xl bg-terracotta/10 p-6 text-terracotta">
          <p className="font-semibold">Could not load the overview</p>
          <p className="mt-1 text-sm">{error}</p>
          <button onClick={load} className="mt-4 flex items-center gap-2 rounded-xl bg-terracotta px-4 py-2 text-sm font-semibold text-white">
            <RefreshCw size={16} /> Try again
          </button>
        </div>
      )}
      {!error && !data && <div className="mt-6 h-40 animate-pulse rounded-3xl bg-forest-100" />}

      {data && (
        <>
          {/* The money */}
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="mt-6 rounded-3xl bg-forest-900 p-6 text-white shadow-xl">
            <p className="text-sm text-forest-200">Received this month</p>
            <p className="font-display text-4xl font-extrabold text-gold">{money(data.revenue_this_month)}</p>
            <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
              <div className="rounded-xl bg-white/10 p-3">
                <p className="text-xs text-forest-200">Last month</p>
                <p className="font-bold">{money(data.revenue_last_month)}</p>
              </div>
              <div className="rounded-xl bg-white/10 p-3">
                <p className="text-xs text-forest-200">Since the start</p>
                <p className="font-bold">{money(data.revenue_total)}</p>
              </div>
            </div>
          </motion.div>

          {/* The counts */}
          <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-4">
            <Stat icon={Users} label="Landlords" value={data.landlords} note={`${data.active} active`} />
            <Stat icon={Building2} label="Units" value={data.units} note={`${data.occupied_units} occupied`} />
            <Stat icon={Users} label="Tenants" value={data.tenants} />
            <Stat icon={PauseCircle} label="Limited" value={data.read_only + data.suspended + data.closed} note={`${data.read_only} read-only, ${data.suspended} suspended, ${data.closed} closed`} />
          </div>

          {/* What needs attention */}
          <div className="mt-6 grid gap-4 md:grid-cols-2">
            <Attention title="Ending in the next 14 days" rows={data.expiring} empty="Nobody is about to run out." />
            <Attention title="Read-only right now" rows={data.read_only_accounts} empty="Nobody is read-only." />
          </div>

          {/* The latest payments */}
          <div className="mt-6 rounded-3xl bg-paper p-5 shadow-sm">
            <div className="flex items-center justify-between">
              <h2 className="flex items-center gap-2 font-display text-lg font-bold text-forest-900">
                <Wallet size={18} className="text-gold" /> Latest payments
              </h2>
              <Link to="/records" className="text-sm font-medium text-forest-700 hover:underline">
                See all
              </Link>
            </div>
            {data.recent_payments.length === 0 ? (
              <p className="mt-2 flex items-center gap-2 text-sm text-muted">
                <Clock size={15} /> No payments recorded yet.
              </p>
            ) : (
              <ul className="mt-2 divide-y divide-forest-100">
                {data.recent_payments.map((payment) => (
                  <li key={payment.id} className="flex items-center justify-between gap-3 py-2.5 text-sm">
                    <span className="min-w-0 truncate text-ink/80">
                      {payment.owner_name} · {formatDate(payment.paid_on)} · {payment.months} month{payment.months === 1 ? '' : 's'}
                    </span>
                    <span className="shrink-0 font-semibold text-forest-900">{money(payment.amount)}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </>
      )}
    </div>
  )
}