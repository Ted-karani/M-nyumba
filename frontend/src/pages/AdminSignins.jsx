// Import the React tools we need
import { useCallback, useEffect, useState } from 'react'
// Import the animation tool
import { motion } from 'framer-motion'
// Import the icons we use
import { Lock, RefreshCw, ShieldAlert, ShieldCheck, UserPlus } from 'lucide-react'
// Import our own files
import { getAdminSecurity, getAdminSignins, getAdminSignups } from '../api'
import { STATE_STYLES } from '../admin'
import { inputClass } from '../components/Field'
import { formatDate } from '../format'
import { formatDateTime } from '../inspection'

// Load some data from the backend, with a way to try again
function useLoader(fetcher, deps) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const load = useCallback(() => {
    setError('')
    setData(null)
    fetcher()
      .then(setData)
      .catch((err) => setError(err.message))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)
  useEffect(() => {
    load()
  }, [load])
  return { data, error, load }
}

// The message and retry button shown when loading failed
function LoadError({ error, onRetry }) {
  return (
    <div className="mt-6 rounded-3xl bg-terracotta/10 p-6 text-terracotta">
      <p className="font-semibold">Could not load this</p>
      <p className="mt-1 text-sm">{error}</p>
      <button onClick={onRetry} className="mt-4 flex items-center gap-2 rounded-xl bg-terracotta px-4 py-2 text-sm font-semibold text-white">
        <RefreshCw size={16} /> Try again
      </button>
    </div>
  )
}

// The sign-ups tab
function SignupsTab() {
  const { data, error, load } = useLoader(getAdminSignups, [])
  if (error) return <LoadError error={error} onRetry={load} />
  if (!data) return <div className="mt-6 h-28 animate-pulse rounded-2xl bg-forest-100" />
  if (data.length === 0) return <p className="mt-6 rounded-2xl bg-paper p-6 text-sm text-muted shadow-sm">No landlords yet.</p>
  return (
    <div className="mt-6 grid gap-3 md:grid-cols-2">
      {data.map((row) => {
        const state = STATE_STYLES[row.state]
        return (
          <motion.div key={row.owner_id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="rounded-2xl bg-paper p-4 shadow-sm">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="truncate font-semibold text-forest-900">{row.full_name}</p>
                <p className="truncate text-sm text-muted">{row.email}</p>
              </div>
              <span className={`shrink-0 rounded-full px-2.5 py-0.5 text-xs font-semibold ${state.style}`}>{state.label}</span>
            </div>
            <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
              <span className="flex items-center gap-1 rounded-full bg-forest-100 px-2.5 py-1 font-semibold text-forest-700">
                <UserPlus size={12} /> {row.source === 'admin' ? 'Added by you' : 'Signed up themselves'}
              </span>
              {row.never_signed_in && <span className="rounded-full bg-amber/20 px-2.5 py-1 font-semibold text-amber">Never signed in</span>}
            </div>
            <p className="mt-3 text-xs text-muted">
              Joined {formatDate(row.created_at.slice(0, 10))}
              {row.first_sign_in ? ` · first sign-in ${formatDateTime(row.first_sign_in)}` : ''}
            </p>
            <p className="mt-1 text-xs text-muted">
              {row.sign_ins_30d} sign-in{row.sign_ins_30d === 1 ? '' : 's'} in the last 30 days
            </p>
          </motion.div>
        )
      })}
    </div>
  )
}

// The sign-ins tab
function SigninsTab() {
  const [days, setDays] = useState(7)
  const [ownerId, setOwnerId] = useState('')
  const { data, error, load } = useLoader(() => getAdminSignins({ days, owner_id: ownerId }), [days, ownerId])

  // The time ranges we offer
  const ranges = [
    { days: 1, label: 'Today' },
    { days: 7, label: '7 days' },
    { days: 30, label: '30 days' },
  ]

  // Put the sign-ins into groups, one for each day
  const groups = []
  if (data) {
    data.items.forEach((item) => {
      const time = new Date(item.created_at.endsWith('Z') ? item.created_at : `${item.created_at}Z`)
      const label = time.toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long' })
      const last = groups[groups.length - 1]
      if (last && last.label === label) last.items.push(item)
      else groups.push({ label, items: [item] })
    })
  }

  return (
    <div>
      <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="flex gap-2">
          {ranges.map((range) => (
            <button
              key={range.days}
              onClick={() => setDays(range.days)}
              className={`rounded-full px-4 py-2 text-sm font-semibold transition ${days === range.days ? 'bg-forest-900 text-white' : 'bg-paper text-forest-700 hover:bg-forest-100'}`}
            >
              {range.label}
            </button>
          ))}
        </div>
        {data && data.people.length > 0 && (
          <select value={ownerId} onChange={(e) => setOwnerId(e.target.value)} className={`${inputClass} sm:w-60`} aria-label="Filter by landlord">
            <option value="">All landlords</option>
            {data.people.map((person) => (
              <option key={person.owner_id} value={person.owner_id}>
                {person.name}
              </option>
            ))}
          </select>
        )}
      </div>

      {error && <LoadError error={error} onRetry={load} />}
      {!error && !data && <div className="mt-6 h-24 animate-pulse rounded-2xl bg-forest-100" />}
      {data && (
        <>
          <p className="mt-4 text-sm text-muted">
            {data.landlord_total} landlord sign-in{data.landlord_total === 1 ? '' : 's'} and {data.caretaker_total} by caretakers in this time.
          </p>
          {data.items.length === 0 && <p className="mt-4 rounded-2xl bg-paper p-6 text-sm text-muted shadow-sm">No sign-ins in this time.</p>}
          {groups.map((group) => (
            <div key={group.label} className="mt-5">
              <p className="mb-2 px-1 text-sm font-bold text-forest-900">{group.label}</p>
              <div className="divide-y divide-forest-100 overflow-hidden rounded-2xl bg-paper shadow-sm">
                {group.items.map((item) => (
                  <div key={item.id} className="flex items-center justify-between gap-3 p-4">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold text-forest-900">{item.landlord_name}</p>
                      <p className="text-xs text-muted">{item.who === 'caretaker' ? 'A caretaker signed in' : 'The landlord signed in'}</p>
                    </div>
                    <p className="shrink-0 text-xs text-muted">
                      {new Date(item.created_at.endsWith('Z') ? item.created_at : `${item.created_at}Z`).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          ))}
          {data.items.length === 300 && <p className="mt-4 text-center text-xs text-muted">Showing the latest 300. Choose a shorter time or a landlord to see fewer.</p>}
        </>
      )}
    </div>
  )
}

// The security tab
function SecurityTab() {
  const { data, error, load } = useLoader(getAdminSecurity, [])
  if (error) return <LoadError error={error} onRetry={load} />
  if (!data) return <div className="mt-6 h-40 animate-pulse rounded-3xl bg-forest-100" />
  const adminTrouble = data.admin_failed_7d > 0 || data.admin_locked_minutes > 0
  return (
    <div className="mt-6 space-y-4">
      {/* The admin's own account */}
      <div className={`rounded-3xl p-6 text-white shadow-xl ${adminTrouble ? 'bg-terracotta' : 'bg-forest-900'}`}>
        <p className="flex items-center gap-2 text-sm font-semibold">
          {adminTrouble ? <ShieldAlert size={18} /> : <ShieldCheck size={18} />} Your admin account
        </p>
        <p className="mt-2 font-display text-3xl font-extrabold">
          {data.admin_failed_7d === 0 ? 'No wrong attempts' : `${data.admin_failed_7d} wrong attempt${data.admin_failed_7d === 1 ? '' : 's'}`}
        </p>
        <p className="text-sm opacity-90">in the last 7 days ({data.admin_failed_24h} in the last 24 hours)</p>
        {data.admin_locked_minutes > 0 && <p className="mt-2 text-sm font-semibold">Locked for {data.admin_locked_minutes} more minute{data.admin_locked_minutes === 1 ? '' : 's'}.</p>}
        {data.admin_last_failed && <p className="mt-2 text-xs opacity-80">Last wrong attempt: {formatDateTime(data.admin_last_failed)}</p>}
        <p className="mt-1 text-xs opacity-80">
          {data.admin_sign_ins_7d} admin sign-in{data.admin_sign_ins_7d === 1 ? '' : 's'} in the last 7 days
          {data.admin_last_sign_in ? ` · last ${formatDateTime(data.admin_last_sign_in)}` : ''}. If you did not sign in at those times, change your password and tell me.
        </p>
      </div>

      {/* Landlords with failed sign-ins */}
      <div className="rounded-3xl bg-paper p-5 shadow-sm">
        <h2 className="font-display text-lg font-bold text-forest-900">Landlords with wrong passwords</h2>
        <p className="text-xs text-muted">The last 7 days. A few mistakes are normal. Many in a row can mean someone is guessing.</p>
        {data.accounts.length === 0 ? (
          <p className="mt-3 text-sm text-muted">No wrong attempts on any landlord account.</p>
        ) : (
          <ul className="mt-3 divide-y divide-forest-100">
            {data.accounts.map((row) => (
              <li key={row.owner_id} className="flex items-center justify-between gap-3 py-3">
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold text-forest-900">{row.full_name}</p>
                  <p className="truncate text-xs text-muted">
                    {row.email}
                    {row.last_failed ? ` · last ${formatDateTime(row.last_failed)}` : ''}
                  </p>
                </div>
                <div className="shrink-0 text-right">
                  {row.locked_minutes > 0 && (
                    <span className="mb-1 flex items-center justify-end gap-1 rounded-full bg-terracotta/15 px-2 py-0.5 text-xs font-semibold text-terracotta">
                      <Lock size={11} /> Locked {row.locked_minutes} min
                    </span>
                  )}
                  <p className="text-sm font-semibold text-forest-900">{row.failed_24h} today</p>
                  <p className="text-xs text-muted">{row.failed_7d} this week</p>
                </div>
              </li>
            ))}
          </ul>
        )}
        {data.locked_now > 0 && <p className="mt-3 text-xs text-muted">A locked landlord can sign in again after the minutes pass, or sooner if you make them a new password from their panel.</p>}
      </div>

      {/* Attempts on emails that do not exist */}
      <div className="rounded-3xl bg-paper p-5 shadow-sm">
        <h2 className="font-display text-lg font-bold text-forest-900">Attempts on emails that do not exist</h2>
        <p className="mt-1 text-sm text-muted">
          {data.unknown_failed_24h} in the last 24 hours, {data.unknown_failed_7d} in the last 7 days. Only counts are kept here, because these may be typing mistakes that contain someone’s private details.
        </p>
      </div>
      <p className="text-center text-xs text-muted">Internet addresses are not shown, because on the live host every visitor appears to come from the same address.</p>
    </div>
  )
}

// The admin's page for sign-ups, sign-ins and security
export default function AdminSignins() {
  // Which tab is showing
  const [tab, setTab] = useState('signups')
  const tabs = [
    { key: 'signups', label: 'Sign-ups' },
    { key: 'signins', label: 'Sign-ins' },
    { key: 'security', label: 'Security' },
  ]
  return (
    <div>
      <h1 className="text-3xl font-extrabold text-forest-900">Sign-ups and sign-ins</h1>
      <p className="text-muted">Who joined, who comes back, and who is failing to get in. Landlords only: never their tenants.</p>
      <div className="mt-6 flex gap-2">
        {tabs.map((item) => (
          <button
            key={item.key}
            onClick={() => setTab(item.key)}
            className={`rounded-full px-4 py-2 text-sm font-semibold transition ${tab === item.key ? 'bg-forest-900 text-white' : 'bg-paper text-forest-700 hover:bg-forest-100'}`}
          >
            {item.label}
          </button>
        ))}
      </div>
      {tab === 'signups' && <SignupsTab />}
      {tab === 'signins' && <SigninsTab />}
      {tab === 'security' && <SecurityTab />}
    </div>
  )
}