// Import the React tools we need
import { useCallback, useEffect, useState } from 'react'
// Import the animation tool
import { motion } from 'framer-motion'
// Import the icons we use
import { AlertTriangle, Check, Copy, Loader2, RefreshCw, Sparkles, Trash2 } from 'lucide-react'
// Import our own files
import { createAdminDemo, deleteAdminDemo, getAdminDemo, resetAdminDemo } from '../api'
import { formatDate } from '../format'

// The numbers shown for the demo
const COUNT_LABELS = [
  ['properties', 'Buildings'],
  ['units', 'Units'],
  ['occupied_units', 'Occupied'],
  ['tenants', 'Tenants'],
  ['payments', 'Payments'],
  ['repairs', 'Repairs'],
  ['listings', 'Listings'],
]

// A button that copies some text
function CopyButton({ text, label }) {
  const [copied, setCopied] = useState(false)
  async function copy() {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      window.prompt('Copy this:', text)
    }
  }
  return (
    <button onClick={copy} aria-label={`Copy the ${label}`} className="flex shrink-0 items-center gap-1.5 rounded-lg bg-white/15 px-3 py-1.5 text-xs font-semibold text-white hover:bg-white/25">
      {copied ? <Check size={14} /> : <Copy size={14} />} {copied ? 'Copied' : 'Copy'}
    </button>
  )
}

// The admin's page for the demo landlord
export default function AdminDemo() {
  // What the server says, the sign-in details (only after building), and the state of the page
  const [status, setStatus] = useState(null)
  const [credentials, setCredentials] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState('')

  // Load the status
  const load = useCallback(() => {
    getAdminDemo()
      .then(setStatus)
      .catch((err) => setError(err.message))
  }, [])
  useEffect(() => {
    load()
  }, [load])

  // Run one of the three actions
  async function run(name, action) {
    setError('')
    setBusy(name)
    try {
      const result = await action()
      setCredentials(name === 'delete' ? null : result)
      load()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy('')
    }
  }

  return (
    <div className="mx-auto max-w-3xl">
      <div className="flex items-center gap-3">
        <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gold/25 text-forest-900">
          <Sparkles size={22} />
        </div>
        <div>
          <h1 className="text-3xl font-extrabold text-forest-900">Demo landlord</h1>
          <p className="text-muted">A separate account full of made-up data, for showing EstateLoom to a landlord.</p>
        </div>
      </div>

      {error && (
        <div role="alert" className="mt-5 flex items-start gap-2 rounded-xl bg-terracotta/10 px-4 py-3 text-sm font-medium text-terracotta">
          <AlertTriangle size={16} className="mt-0.5 shrink-0" /> {error}
        </div>
      )}
      {!status && !error && <div className="mt-5 h-40 animate-pulse rounded-3xl bg-forest-100" />}

      {/* The sign-in details, shown once after building */}
      {credentials && (
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="mt-5 rounded-3xl bg-forest-900 p-6 text-white shadow-xl">
          <p className="text-sm font-semibold text-gold">Sign-in details for the demo</p>
          <p className="mt-1 text-xs text-forest-200">This password is shown only now. If you lose it, press Reset to get a new one.</p>
          <div className="mt-4 space-y-3">
            {[
              ['Email', credentials.email],
              ['Password', credentials.password],
            ].map(([label, value]) => (
              <div key={label} className="flex items-center justify-between gap-3 rounded-xl bg-white/10 px-4 py-3">
                <div className="min-w-0">
                  <p className="text-xs text-forest-200">{label}</p>
                  <p className="truncate font-mono text-sm font-semibold">{value}</p>
                </div>
                <CopyButton text={value} label={label.toLowerCase()} />
              </div>
            ))}
          </div>
          <p className="mt-4 text-xs text-forest-200">Open EstateLoom in a private window (Ctrl+Shift+N in Chrome) and sign in with these. Keep your admin window open next to it.</p>
        </motion.div>
      )}

      {status && status.blocked && (
        <div className="mt-5 rounded-3xl bg-paper p-6 shadow-sm">
          <p className="font-semibold text-terracotta">Demo blocked</p>
          <p className="mt-1 text-sm text-muted">{status.message}</p>
        </div>
      )}

      {status && !status.blocked && !status.exists && (
        <div className="mt-5 rounded-3xl bg-paper p-6 shadow-sm">
          <h2 className="font-display text-lg font-bold text-forest-900">No demo yet</h2>
          <p className="mt-1 text-sm text-muted">Creating it takes a few seconds. You get a sign-in email and password to use in a private window.</p>
          <button onClick={() => run('create', createAdminDemo)} disabled={busy !== ''} className="mt-4 flex items-center gap-2 rounded-xl bg-forest-900 px-5 py-3 text-sm font-semibold text-white hover:bg-forest-700 disabled:opacity-60">
            {busy === 'create' ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />} Create the demo landlord
          </button>
        </div>
      )}

      {status && status.exists && (
        <div className="mt-5 rounded-3xl bg-paper p-6 shadow-sm">
          <h2 className="font-display text-lg font-bold text-forest-900">The demo is ready</h2>
          <p className="text-sm text-muted">
            {status.email}
            {status.created_at ? ` · built ${formatDate(status.created_at.slice(0, 10))}` : ''}
          </p>
          <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
            {COUNT_LABELS.map(([key, label]) => (
              <div key={key} className="rounded-2xl bg-cream px-3 py-3 text-center">
                <p className="font-display text-xl font-extrabold text-forest-900">{status.counts[key] ?? 0}</p>
                <p className="text-xs text-muted">{label}</p>
              </div>
            ))}
          </div>
          <div className="mt-5 flex flex-wrap gap-2">
            <button
              onClick={() => window.confirm('Rebuild the demo with fresh dates? You get a new password, and the old one stops working.') && run('reset', resetAdminDemo)}
              disabled={busy !== ''}
              className="flex items-center gap-2 rounded-xl bg-forest-900 px-5 py-3 text-sm font-semibold text-white hover:bg-forest-700 disabled:opacity-60"
            >
              {busy === 'reset' ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />} Reset with fresh dates
            </button>
            <button
              onClick={() => window.confirm('Delete the demo landlord and all its made-up data?') && run('delete', deleteAdminDemo)}
              disabled={busy !== ''}
              className="flex items-center gap-2 rounded-xl bg-terracotta/10 px-5 py-3 text-sm font-semibold text-terracotta hover:bg-terracotta hover:text-white disabled:opacity-60"
            >
              {busy === 'delete' ? <Loader2 size={16} className="animate-spin" /> : <Trash2 size={16} />} Delete
            </button>
          </div>
        </div>
      )}

      {/* Notes for presenting */}
      <div className="mt-5 rounded-3xl bg-paper p-6 shadow-sm">
        <h2 className="font-display text-lg font-bold text-forest-900">Before you present</h2>
        <ul className="mt-3 list-disc space-y-2 pl-5 text-sm text-ink/80">
          <li>
            <span className="font-semibold">Reset it the day before.</span> All the dates are worked out from today, so a reset keeps the rent history, late tenants and tax months looking current.
          </li>
          <li>
            <span className="font-semibold">Do not press the WhatsApp or text reminder buttons on demo tenants.</span> The phone numbers are made up, but they look real, and a message could reach a stranger.
          </li>
          <li>The demo has three buildings with 60 units, four months of payments, late fees switched on, a rental income tax month already filed, a moved-out tenant with a draft deposit settlement, repairs, notices, tasks and vacancy listings.</li>
          <li>It has no tenant or caretaker logins. If you want to show those, make them from the demo account in the usual screens.</li>
          <li>The demo shows in your landlords list and counts like any landlord, with a note on it. Delete it when you are not presenting.</li>
        </ul>
      </div>
    </div>
  )
}