// Import the React tools we need
import { useCallback, useEffect, useState } from 'react'
// Import the page-switching tool
import { Link } from 'react-router-dom'
// Import the animation tool
import { motion } from 'framer-motion'
// Import the icons we use
import { Bell, Check, Copy, MessageCircle, Phone, Receipt, RefreshCw, Wallet, Wrench } from 'lucide-react'
// Import our own files
import { useAuth } from '../AuthContext'
import { getPortalHome, getPortalStatement } from '../api'
import { formatDate, money, phoneLocal } from '../format'

// Pick a greeting based on the time of day
function greeting() {
  // The current hour, from 0 to 23
  const hour = new Date().getHours()
  if (hour < 12) return 'Good morning'
  if (hour < 17) return 'Good afternoon'
  return 'Good evening'
}

// A small button that copies some text
function CopyButton({ text, label }) {
  // True for a moment after copying
  const [copied, setCopied] = useState(false)
  // Copy the text
  async function copy() {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 1800)
    } catch {
      // If copying is blocked, the text is still on the screen
    }
  }
  return (
    <button onClick={copy} aria-label={label} className="flex shrink-0 items-center gap-1.5 rounded-lg bg-forest-100 px-3 py-1.5 text-xs font-semibold text-forest-700 hover:bg-forest-200">
      {copied ? <Check size={13} /> : <Copy size={13} />} {copied ? 'Copied' : 'Copy'}
    </button>
  )
}

// The list of charges and payments for one home
function Statement({ leaseId }) {
  // The lines (nothing until they arrive)
  const [rows, setRows] = useState(null)
  // The error message
  const [error, setError] = useState('')
  // Whether to show all the lines or only the latest few
  const [showAll, setShowAll] = useState(false)

  // Load the lines when this appears
  useEffect(() => {
    getPortalStatement(leaseId)
      .then(setRows)
      .catch((err) => setError(err.message))
  }, [leaseId])

  if (error) return <p className="text-sm text-terracotta">{error}</p>
  if (!rows) return <div className="h-20 animate-pulse rounded-2xl bg-forest-100" />
  if (rows.length === 0) return <p className="text-sm text-muted">Nothing here yet.</p>
  // Show only the latest 8 unless asked for all
  const shown = showAll ? rows : rows.slice(0, 8)

  return (
    <div>
      <ul className="divide-y divide-forest-100">
        {shown.map((row, index) => (
          <li key={`${row.kind}-${index}`} className="flex items-center gap-3 py-3">
            <span className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ${row.kind === 'payment' ? 'bg-forest-100 text-forest-700' : 'bg-amber/15 text-amber'}`}>
              {row.kind === 'payment' ? <Wallet size={17} /> : <Receipt size={17} />}
            </span>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-semibold text-forest-900">{row.title}</p>
              <p className="truncate text-xs text-muted">
                {formatDate(row.date)}
                {row.reference ? ` · ${row.reference}` : ''}
              </p>
            </div>
            <div className="text-right">
              <p className={`text-sm font-semibold ${row.kind === 'payment' ? 'text-forest-500' : 'text-forest-900'}`}>
                {row.kind === 'payment' ? '−' : '+'} {money(row.amount)}
              </p>
              <p className="text-[11px] text-muted">Balance {money(row.balance_after)}</p>
            </div>
          </li>
        ))}
      </ul>
      {rows.length > 8 && (
        <button onClick={() => setShowAll(!showAll)} className="mt-2 text-sm font-medium text-forest-700 hover:underline">
          {showAll ? 'Show less' : `Show all (${rows.length})`}
        </button>
      )}
    </div>
  )
}

// The tenant's home screen
export default function PortalHome() {
  // The logged-in user
  const { user } = useAuth()
  // The data from the backend (nothing until it arrives)
  const [home, setHome] = useState(null)
  // The error message, if loading failed
  const [error, setError] = useState('')

  // Load the home screen
  const load = useCallback(() => {
    setError('')
    getPortalHome()
      .then(setHome)
      .catch((err) => setError(err.message))
  }, [])

  // Load it when the page opens
  useEffect(() => {
    load()
  }, [load])

  // Use only the first name in the greeting
  const firstName = user.full_name.split(' ')[0]

  return (
    <div className="mx-auto max-w-2xl">
      <p className="text-muted">{greeting()}</p>
      <h1 className="text-3xl font-extrabold text-forest-900">{firstName}</h1>

      {/* If loading failed, show the message and a retry button */}
      {error && (
        <div className="mt-6 rounded-3xl bg-terracotta/10 p-6 text-terracotta">
          <p className="font-semibold">Could not load your page</p>
          <p className="mt-1 text-sm">{error}</p>
          <button onClick={load} className="mt-4 flex items-center gap-2 rounded-xl bg-terracotta px-4 py-2 text-sm font-semibold text-white">
            <RefreshCw size={16} /> Try again
          </button>
        </div>
      )}

      {/* While waiting, show grey placeholder boxes */}
      {!error && !home && (
        <div className="mt-6 space-y-3">
          <div className="h-44 animate-pulse rounded-3xl bg-forest-100" />
          <div className="h-32 animate-pulse rounded-2xl bg-forest-100" />
        </div>
      )}

      {home && (
        <>
          {/* No active home */}
          {home.tenancies.length === 0 && (
            <div className="mt-6 rounded-3xl bg-paper p-8 text-center shadow-sm">
              <p className="font-semibold text-forest-900">You have no current tenancy</p>
              <p className="mt-1 text-sm text-muted">If this looks wrong, please contact your landlord.</p>
            </div>
          )}

          {/* One card for each home */}
          {home.tenancies.map((tenancy) => {
            const owes = tenancy.balance > 0
            const credit = tenancy.balance < 0
            return (
              <div key={tenancy.lease_id} className="mt-6">
                <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} className="rounded-3xl bg-forest-900 p-6 text-white shadow-xl">
                  <p className="text-sm text-forest-200">
                    Unit {tenancy.unit_number} · {tenancy.property_name}
                  </p>
                  <p className="mt-3 text-sm text-forest-200">{owes ? 'You owe' : credit ? 'You are in credit' : 'Your balance'}</p>
                  <p className={`font-display text-5xl font-extrabold ${owes ? 'text-gold' : 'text-white'}`}>{money(Math.abs(tenancy.balance))}</p>
                  <p className="mt-2 text-sm text-forest-200">{owes ? 'Please pay as soon as you can.' : credit ? 'This will count against your next charges.' : 'You are all paid up. Thank you!'}</p>
                  <div className="mt-5 grid grid-cols-3 gap-2 rounded-2xl bg-white/10 p-3 text-center">
                    <div>
                      <p className="text-[11px] text-forest-200">Rent</p>
                      <p className="text-sm font-bold">{money(tenancy.rent_amount)}</p>
                    </div>
                    <div>
                      <p className="text-[11px] text-forest-200">Charged</p>
                      <p className="text-sm font-bold">{money(tenancy.total_charged)}</p>
                    </div>
                    <div>
                      <p className="text-[11px] text-forest-200">Paid</p>
                      <p className="text-sm font-bold">{money(tenancy.total_paid)}</p>
                    </div>
                  </div>
                </motion.div>

                <div className="mt-4 rounded-3xl bg-paper p-5 shadow-sm">
                  <h2 className="font-display text-lg font-bold text-forest-900">Your statement</h2>
                  <div className="mt-2">
                    <Statement leaseId={tenancy.lease_id} />
                  </div>
                </div>
              </div>
            )
          })}

          {/* How to pay */}
          <div className="mt-4 rounded-3xl bg-paper p-5 shadow-sm">
            <h2 className="font-display text-lg font-bold text-forest-900">How to pay</h2>
            {home.payment_info.paybill_number ? (
              <div className="mt-3 space-y-3">
                <div className="flex items-center justify-between gap-3 rounded-2xl bg-cream p-4">
                  <div>
                    <p className="text-xs text-muted">M-Pesa Paybill / Till number</p>
                    <p className="font-display text-2xl font-bold tracking-wide text-forest-900">{home.payment_info.paybill_number}</p>
                  </div>
                  <CopyButton text={home.payment_info.paybill_number} label="Copy the Paybill number" />
                </div>
                {home.payment_info.account_hint && (
                  <div className="rounded-2xl bg-cream p-4">
                    <p className="text-xs text-muted">Account number</p>
                    <p className="font-semibold text-forest-900">{home.payment_info.account_hint}</p>
                  </div>
                )}
                {home.payment_info.instructions && <p className="whitespace-pre-line text-sm text-ink/80">{home.payment_info.instructions}</p>}
              </div>
            ) : (
              <p className="mt-2 text-sm text-muted">Ask {home.payment_info.contact_name} how to pay.</p>
            )}
            {/* Ask the landlord */}
            {home.payment_info.contact_phone && (
              <div className="mt-4 flex gap-2">
                <a href={`tel:+${home.payment_info.contact_phone}`} className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-forest-100 py-2.5 text-sm font-semibold text-forest-700 hover:bg-forest-200">
                  <Phone size={15} /> Call {home.payment_info.contact_name.split(' ')[0]}
                </a>
                <a
                  href={`https://wa.me/${home.payment_info.contact_phone}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-forest-500 py-2.5 text-sm font-semibold text-white hover:bg-forest-700"
                >
                  <MessageCircle size={15} /> WhatsApp
                </a>
              </div>
            )}
            {home.payment_info.contact_phone && <p className="mt-2 text-center text-xs text-muted">{phoneLocal(home.payment_info.contact_phone)}</p>}
          </div>

          {/* The latest notices */}
          {home.notices.length > 0 && (
            <div className="mt-4 rounded-3xl bg-paper p-5 shadow-sm">
              <div className="flex items-center justify-between">
                <h2 className="flex items-center gap-2 font-display text-lg font-bold text-forest-900">
                  <Bell size={18} className="text-gold" /> Notices
                </h2>
                <Link to="/notices" className="text-sm font-medium text-forest-700 hover:underline">
                  See all
                </Link>
              </div>
              <div className="mt-3 space-y-3">
                {home.notices.map((notice) => (
                  <div key={notice.id} className="rounded-2xl bg-cream p-4">
                    <p className="font-semibold text-forest-900">
                      {notice.pinned ? '📌 ' : ''}
                      {notice.title}
                    </p>
                    <p className="mt-1 line-clamp-3 whitespace-pre-line text-sm text-ink/80">{notice.body}</p>
                    <p className="mt-2 text-xs text-muted">{formatDate(notice.posted_on)}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* A shortcut to report a problem */}
          <Link to="/repairs" className="mt-4 flex items-center justify-center gap-2 rounded-2xl bg-forest-100 py-4 font-semibold text-forest-700 hover:bg-forest-200">
            <Wrench size={18} /> Report a problem in my home
          </Link>
        </>
      )}
    </div>
  )
}