// Import the React tools we need
import { useEffect, useState } from 'react'
// Import the page-switching tool
import { Link } from 'react-router-dom'
// Import the animation tool
import { motion } from 'framer-motion'
// Import the icons we use
import { Banknote, ChevronLeft, ChevronRight, Landmark, RefreshCw, Search, Smartphone, Wallet } from 'lucide-react'
// Import our own files
import { getDashboard, getPaymentsReport } from '../api'
import { METHOD_LABELS, currentPeriod, formatDate, money, monthLabel, shiftPeriod } from '../format'
import CountUp from '../components/CountUp'
import { inputClass } from '../components/Field'

// The icon for each way of paying
const METHOD_ICONS = { mpesa: Smartphone, cash: Banknote, bank: Landmark }

// The filter buttons for the way of paying
const METHOD_FILTERS = [
  { key: '', label: 'All' },
  { key: 'mpesa', label: 'M-Pesa' },
  { key: 'cash', label: 'Cash' },
  { key: 'bank', label: 'Bank' },
]

// The page that lists every payment received
export default function Payments() {
  // The filters: which month ("" means all time), which property, which way of paying, and a search word
  const [month, setMonth] = useState(currentPeriod())
  const [propertyId, setPropertyId] = useState('')
  const [method, setMethod] = useState('')
  const [search, setSearch] = useState('')
  // The list of properties for the dropdown
  const [properties, setProperties] = useState([])
  // The payments from the backend (nothing until they arrive)
  const [report, setReport] = useState(null)
  // True while we are fetching (we keep showing the old list, slightly faded)
  const [loading, setLoading] = useState(true)
  // The error message, if loading failed
  const [error, setError] = useState('')
  // Changing this number makes the list load again (used by the "try again" button)
  const [reloadKey, setReloadKey] = useState(0)

  // Load the properties once, for the dropdown
  useEffect(() => {
    getDashboard()
      .then((data) => setProperties(data.properties))
      .catch(() => setProperties([]))
  }, [])

  // Load the payments whenever a filter changes (searching waits a moment for the typing to stop)
  useEffect(() => {
    // Set to true if the filters change again before this request finishes
    let cancelled = false
    setLoading(true)
    const timer = setTimeout(() => {
      getPaymentsReport({ month, property_id: propertyId, method, search: search.trim() })
        .then((data) => {
          if (cancelled) return
          setReport(data)
          setError('')
        })
        .catch((err) => {
          if (!cancelled) setError(err.message)
        })
        .finally(() => {
          if (!cancelled) setLoading(false)
        })
    }, 250)
    // Clean up if the filters change or the page closes
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [month, propertyId, method, search, reloadKey])

  // Put the payments into groups, one group for each day
  const groups = []
  if (report) {
    report.items.forEach((item) => {
      // The last group is the day we are currently filling
      const last = groups[groups.length - 1]
      if (last && last.date === item.paid_on) {
        last.items.push(item)
        last.total += item.amount
      } else {
        groups.push({ date: item.paid_on, items: [item], total: item.amount })
      }
    })
  }

  return (
    <div>
      {/* The title */}
      <h1 className="text-3xl font-extrabold text-forest-900">Payments</h1>
      <p className="text-muted">Everything you have received, in one place.</p>

      {/* The month controls */}
      <div className="mt-6 flex flex-wrap items-center gap-2">
        <div className="flex items-center rounded-xl bg-paper shadow-sm">
          <button
            onClick={() => setMonth(shiftPeriod(month || currentPeriod(), -1))}
            aria-label="Previous month"
            className="rounded-l-xl p-3 text-forest-700 hover:bg-forest-100"
          >
            <ChevronLeft size={18} />
          </button>
          <span className="min-w-36 px-2 text-center text-sm font-semibold text-forest-900">
            {month ? monthLabel(month) : 'All time'}
          </span>
          <button
            onClick={() => setMonth(shiftPeriod(month || currentPeriod(), 1))}
            aria-label="Next month"
            className="rounded-r-xl p-3 text-forest-700 hover:bg-forest-100"
          >
            <ChevronRight size={18} />
          </button>
        </div>
        <button
          onClick={() => setMonth(currentPeriod())}
          className={`rounded-full px-4 py-2 text-sm font-semibold transition ${
            month === currentPeriod() ? 'bg-forest-900 text-white' : 'bg-paper text-forest-700 hover:bg-forest-100'
          }`}
        >
          This month
        </button>
        <button
          onClick={() => setMonth('')}
          className={`rounded-full px-4 py-2 text-sm font-semibold transition ${
            month === '' ? 'bg-forest-900 text-white' : 'bg-paper text-forest-700 hover:bg-forest-100'
          }`}
        >
          All time
        </button>
      </div>

      {/* The green summary card */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        className="mt-4 rounded-3xl bg-forest-900 p-6 text-white shadow-xl"
      >
        <div className="flex items-center gap-2 text-forest-200">
          <Wallet size={18} />
          <span className="text-sm">{month ? `Received in ${monthLabel(month)}` : 'Received, all time'}</span>
        </div>
        <div className="mt-2 font-display text-5xl font-bold">
          <CountUp value={report ? report.total : 0} format={money} />
        </div>
        <p className="mt-1 text-sm text-forest-200">
          {report ? `${report.count} payment${report.count === 1 ? '' : 's'}` : 'Loading...'}
        </p>
        {/* The total split by way of paying */}
        <div className="mt-5 grid grid-cols-3 gap-3">
          {Object.keys(METHOD_LABELS).map((key) => (
            <div key={key} className="rounded-2xl bg-white/10 p-3">
              <p className="text-xs text-forest-200">{METHOD_LABELS[key]}</p>
              <p className="mt-0.5 text-sm font-bold sm:text-base">{money(report ? report.by_method[key] : 0)}</p>
            </div>
          ))}
        </div>
      </motion.div>

      {/* The search, property, and method filters */}
      <div className="mt-5 flex flex-col gap-3 md:flex-row md:items-center">
        <div className="relative flex-1">
          <Search size={18} className="absolute left-4 top-1/2 -translate-y-1/2 text-muted" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by tenant, unit, or M-Pesa code"
            className={`${inputClass} pl-11`}
          />
        </div>
        {properties.length > 1 && (
          <select
            value={propertyId}
            onChange={(e) => setPropertyId(e.target.value)}
            className={`${inputClass} md:w-56`}
            aria-label="Filter by property"
          >
            <option value="">All properties</option>
            {properties.map((prop) => (
              <option key={prop.property_id} value={prop.property_id}>
                {prop.name}
              </option>
            ))}
          </select>
        )}
      </div>
      <div className="mt-3 flex gap-2">
        {METHOD_FILTERS.map((item) => (
          <button
            key={item.key}
            onClick={() => setMethod(item.key)}
            className={`rounded-full px-4 py-2 text-sm font-semibold transition ${
              method === item.key ? 'bg-forest-900 text-white' : 'bg-paper text-forest-700 hover:bg-forest-100'
            }`}
          >
            {item.label}
          </button>
        ))}
      </div>

      {/* If loading failed, show the message and a retry button */}
      {error && (
        <div className="mt-6 rounded-3xl bg-terracotta/10 p-6 text-terracotta">
          <p className="font-semibold">Could not load your payments</p>
          <p className="mt-1 text-sm">{error}</p>
          <button
            onClick={() => setReloadKey(reloadKey + 1)}
            className="mt-4 flex items-center gap-2 rounded-xl bg-terracotta px-4 py-2 text-sm font-semibold text-white"
          >
            <RefreshCw size={16} /> Try again
          </button>
        </div>
      )}

      {/* While the very first load is running, show grey placeholder boxes */}
      {!error && !report && (
        <div className="mt-6 space-y-3">
          <div className="h-16 animate-pulse rounded-2xl bg-forest-100" />
          <div className="h-16 animate-pulse rounded-2xl bg-forest-100" />
        </div>
      )}

      {/* The list of payments, grouped by day */}
      {report && !error && (
        <div className={`mt-6 transition-opacity ${loading ? 'opacity-50' : 'opacity-100'}`}>
          {groups.length === 0 ? (
            <div className="rounded-3xl bg-paper p-10 text-center shadow-sm">
              <p className="font-semibold text-forest-900">No payments found</p>
              <p className="mt-1 text-sm text-muted">Try another month, or clear the filters.</p>
            </div>
          ) : (
            <div className="space-y-6">
              {groups.map((group) => (
                <div key={group.date}>
                  {/* The day's heading and its total */}
                  <div className="mb-2 flex items-baseline justify-between px-1">
                    <p className="text-sm font-semibold text-forest-900">{formatDate(group.date)}</p>
                    <p className="text-sm text-muted">{money(group.total)}</p>
                  </div>
                  <div className="divide-y divide-forest-100 overflow-hidden rounded-2xl bg-paper shadow-sm">
                    {group.items.map((item) => {
                      // The icon for this way of paying
                      const Icon = METHOD_ICONS[item.method] || Wallet
                      return (
                        <Link
                          key={item.id}
                          to={`/tenants/${item.tenant_id}`}
                          className="flex items-center gap-3 p-4 transition hover:bg-forest-100/50"
                        >
                          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-forest-100 text-forest-700">
                            <Icon size={18} />
                          </span>
                          <div className="min-w-0 flex-1">
                            <p className="truncate font-semibold text-forest-900">{item.tenant_name}</p>
                            <p className="truncate text-xs text-muted">
                              {item.unit_number} · {item.property_name}
                            </p>
                            <p className="truncate text-xs text-muted">
                              {METHOD_LABELS[item.method]}
                              {item.reference ? ` · ${item.reference}` : ''}
                              {item.recorded_by_name ? ` · by ${item.recorded_by_name}` : ''}
                            </p>
                          </div>
                          <p className="font-display text-lg font-bold text-forest-500">{money(item.amount)}</p>
                        </Link>
                      )
                    })}
                  </div>
                </div>
              ))}
              {/* If there are more payments than we can show, say so */}
              {report.count > report.items.length && (
                <p className="text-center text-sm text-muted">
                  Showing the latest {report.items.length} of {report.count} payments. Choose a month to see fewer.
                </p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}