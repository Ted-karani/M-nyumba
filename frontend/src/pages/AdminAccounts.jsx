// Import the React tools we need
import { useCallback, useEffect, useState } from 'react'
// Import the animation tool
import { motion } from 'framer-motion'
// Import the icons we use
import { Check, Copy, MessageCircle, Plus, RefreshCw, Search, ShieldCheck, ShieldOff, Users } from 'lucide-react'
// Import our own files
import { createAdminAccount, getAdminAccounts } from '../api'
import { PLAN_LABELS, STATE_STYLES, accessText } from '../admin'
import { formatDateTime } from '../inspection'
import AdminAccountForm from '../components/AdminAccountForm'
import AdminAccountPanel from '../components/AdminAccountPanel'
import Modal from '../components/Modal'

// The filters we offer
const FILTERS = [
  { key: 'all', label: 'All' },
  { key: 'active', label: 'Active' },
  { key: 'expiring', label: 'Ending soon' },
  { key: 'read_only', label: 'Read-only' },
  { key: 'suspended', label: 'Suspended' },
  { key: 'closed', label: 'Closed' },
  { key: 'quiet', label: 'Quiet' },
]

// Does a landlord fit a filter?
function fits(account, filter) {
  if (filter === 'all') return true
  if (filter === 'expiring') return account.state === 'active' && account.days_left !== null && account.days_left >= 0 && account.days_left <= 14
  if (filter === 'quiet') return !account.last_sign_in
  return account.state === filter
}

// The page that lists every landlord
export default function AdminAccounts() {
  // The landlords (nothing until they arrive)
  const [accounts, setAccounts] = useState(null)
  // The error message, if loading failed
  const [error, setError] = useState('')
  // What is typed in the search box, and which filter is chosen
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState('all')
  // The landlord whose panel is open (we keep only the id, so the panel shows fresh numbers after each change)
  const [openId, setOpenId] = useState(null)
  // Whether the "add a landlord" window is open, and the login details just made
  const [adding, setAdding] = useState(false)
  const [credentials, setCredentials] = useState(null)
  // True for a moment after the password was copied
  const [copied, setCopied] = useState(false)

  // Load the landlords
  const load = useCallback(() => {
    setError('')
    getAdminAccounts()
      .then(setAccounts)
      .catch((err) => setError(err.message))
  }, [])

  // Load them when the page opens
  useEffect(() => {
    load()
  }, [load])

  // The landlords that match the search and the filter
  const shown = (accounts || []).filter((account) => {
    const words = `${account.full_name} ${account.email}`.toLowerCase()
    return fits(account, filter) && words.includes(search.trim().toLowerCase())
  })
  // The landlord whose panel is open
  const open = accounts ? accounts.find((account) => account.owner_id === openId) : null

  // Copy the temporary password
  async function copyPassword() {
    try {
      await navigator.clipboard.writeText(credentials.temporary_password)
      setCopied(true)
      setTimeout(() => setCopied(false), 1800)
    } catch {
      // If copying is blocked, the password is still on the screen
    }
  }

  // The message sent to the new landlord on WhatsApp
  const whatsapp = credentials
    ? `Hello ${credentials.full_name.split(' ')[0]}, welcome to EstateLoom. Your sign-in:\n\nOpen: ${window.location.origin}\nEmail: ${credentials.email}\nTemporary password: ${credentials.temporary_password}\n\nYou will be asked to choose your own password.`
    : ''

  return (
    <div>
      {/* The title and the add button */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-extrabold text-forest-900">Landlords</h1>
          <p className="text-muted">Everyone who uses EstateLoom. You see counts, never their tenants’ details.</p>
        </div>
        <motion.button whileTap={{ scale: 0.96 }} onClick={() => setAdding(true)} className="flex shrink-0 items-center gap-2 rounded-xl bg-forest-900 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-forest-900/20 hover:bg-forest-700">
          <Plus size={18} /> Add landlord
        </motion.button>
      </div>

      {/* The search box and the filters */}
      <div className="mt-6 space-y-3">
        <div className="relative">
          <Search size={18} className="absolute left-4 top-1/2 -translate-y-1/2 text-muted" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by name or email"
            className="w-full rounded-xl border border-forest-200 bg-paper py-3 pl-11 pr-4 outline-none transition focus:border-forest-500 focus:ring-4 focus:ring-forest-100"
          />
        </div>
        <div className="flex flex-wrap gap-2">
          {FILTERS.map((item) => (
            <button
              key={item.key}
              onClick={() => setFilter(item.key)}
              className={`rounded-full px-3.5 py-1.5 text-sm font-semibold transition ${
                filter === item.key ? 'bg-forest-900 text-white' : 'bg-paper text-forest-700 hover:bg-forest-100'
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      {/* If loading failed, show the message and a retry button */}
      {error && (
        <div className="mt-6 rounded-3xl bg-terracotta/10 p-6 text-terracotta">
          <p className="font-semibold">Could not load the landlords</p>
          <p className="mt-1 text-sm">{error}</p>
          <button onClick={load} className="mt-4 flex items-center gap-2 rounded-xl bg-terracotta px-4 py-2 text-sm font-semibold text-white">
            <RefreshCw size={16} /> Try again
          </button>
        </div>
      )}
      {!error && !accounts && <div className="mt-6 h-28 animate-pulse rounded-2xl bg-forest-100" />}

      {accounts && shown.length === 0 && (
        <div className="mt-6 flex flex-col items-center rounded-3xl bg-paper p-10 text-center shadow-sm">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-forest-100 text-forest-700">
            <Users size={26} />
          </div>
          <p className="mt-4 font-semibold text-forest-900">No landlords match</p>
        </div>
      )}

      {/* The landlords */}
      <div className="mt-6 grid gap-3 md:grid-cols-2">
        {shown.map((account) => {
          const state = STATE_STYLES[account.state]
          // How full their unit limit is
          const fill = account.unit_limit ? Math.min(100, Math.round((account.units / account.unit_limit) * 100)) : 0
          return (
            <motion.button
              key={account.owner_id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              onClick={() => setOpenId(account.owner_id)}
              className="rounded-2xl bg-paper p-4 text-left shadow-sm transition hover:shadow-md"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="truncate font-semibold text-forest-900">{account.full_name}</p>
                  <p className="truncate text-sm text-muted">{account.email}</p>
                </div>
                <span className={`shrink-0 rounded-full px-2.5 py-0.5 text-xs font-semibold ${state.style}`}>{state.label}</span>
              </div>
              <div className="mt-3 flex items-center justify-between text-sm">
                <span className="text-ink/80">
                  {PLAN_LABELS[account.plan]} · {accessText(account)}
                </span>
                <span className="flex items-center gap-1 text-xs text-muted">
                  {account.two_step ? <ShieldCheck size={13} className="text-forest-500" /> : <ShieldOff size={13} />} 2-step {account.two_step ? 'on' : 'off'}
                </span>
              </div>
              <div className="mt-3">
                <div className="flex justify-between text-xs text-muted">
                  <span>
                    {account.units} unit{account.units === 1 ? '' : 's'}
                    {account.unit_limit ? ` of ${account.unit_limit}` : ''} · {account.tenants} tenants
                  </span>
                  <span>{account.last_sign_in ? `seen ${formatDateTime(account.last_sign_in)}` : 'not seen in 30 days'}</span>
                </div>
                {account.unit_limit && (
                  <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-forest-100">
                    <div className={`h-full rounded-full ${fill >= 100 ? 'bg-terracotta' : 'bg-forest-500'}`} style={{ width: `${fill}%` }} />
                  </div>
                )}
              </div>
            </motion.button>
          )
        })}
      </div>

      {/* One landlord's panel */}
      <Modal open={open !== null && open !== undefined} title="Landlord" onClose={() => setOpenId(null)}>
        {open && <AdminAccountPanel key={open.owner_id} account={open} onChanged={load} />}
      </Modal>

      {/* Add a landlord */}
      <Modal open={adding} title="Add a landlord" onClose={() => setAdding(false)}>
        <AdminAccountForm
          onCancel={() => setAdding(false)}
          onSubmit={async (body) => {
            const result = await createAdminAccount(body)
            setAdding(false)
            setCredentials(result)
            load()
          }}
        />
      </Modal>

      {/* The new landlord's login details, shown once */}
      <Modal open={credentials !== null} title="Landlord added" onClose={() => setCredentials(null)}>
        {credentials && (
          <div>
            <p className="text-sm text-muted">
              Send these to <span className="font-semibold text-forest-900">{credentials.full_name}</span>. The password is shown <span className="font-semibold">only this once</span>. If you lose it, make a new one from their panel.
            </p>
            <div className="mt-4 rounded-2xl bg-cream p-4">
              <p className="text-xs text-muted">Sign in with email</p>
              <p className="font-semibold text-forest-900">{credentials.email}</p>
              <p className="mt-3 text-xs text-muted">Temporary password</p>
              <div className="flex items-center justify-between gap-3">
                <p className="font-mono text-2xl font-bold tracking-widest text-forest-900">{credentials.temporary_password}</p>
                <button onClick={copyPassword} className="flex shrink-0 items-center gap-1.5 rounded-lg bg-forest-100 px-3 py-1.5 text-xs font-semibold text-forest-700 hover:bg-forest-200">
                  {copied ? <Check size={13} /> : <Copy size={13} />} {copied ? 'Copied' : 'Copy'}
                </button>
              </div>
            </div>
            <a
              href={`https://wa.me/${credentials.phone || ''}?text=${encodeURIComponent(whatsapp)}`}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-4 flex items-center justify-center gap-2 rounded-xl bg-forest-500 py-3 text-sm font-semibold text-white hover:bg-forest-700"
            >
              <MessageCircle size={16} /> Send on WhatsApp
            </a>
            <p className="mt-3 text-xs text-muted">They will be asked to choose their own password the first time they sign in.</p>
          </div>
        )}
      </Modal>
    </div>
  )
}