// Import the React tools we need
import { useCallback, useEffect, useState } from 'react'
// Import the page-switching tool
import { Link } from 'react-router-dom'
// Import the animation tool
import { motion } from 'framer-motion'
// Import the icons we use
import { BellRing, CheckCircle2, ChevronDown, ChevronUp, MessageCircle, Phone, RefreshCw, Wallet } from 'lucide-react'
// Import our own files
import { getDashboard, getReminderSummary, logReminder } from '../api'
import { money, whatsappLink } from '../format'

// How the list appears: the cards come in one after another
const listAnimation = { hidden: {}, show: { transition: { staggerChildren: 0.05 } } }
// How each card appears: fade in while sliding up
const itemAnimation = { hidden: { opacity: 0, y: 14 }, show: { opacity: 1, y: 0 } }

// The name we save the message under in the browser
const STORAGE_KEY = 'mnyumba_reminder_templates'
// The ready-made messages (English and Kiswahili)
const DEFAULTS = {
  lang: 'en',
  en: 'Hello {name}, a friendly reminder that {amount} for house {unit} at {property} is overdue by {days} days. Kindly clear it as soon as you can. Thank you.',
  sw: 'Habari {name}, huu ni ukumbusho wa kirafiki kwamba {amount} ya nyumba {unit} katika {property} imechelewa kwa siku {days}. Tafadhali lipa haraka iwezekanavyo. Asante.',
}

// Read the saved messages (or the ready-made ones if nothing was saved)
function loadTemplates() {
  try {
    return { ...DEFAULTS, ...(JSON.parse(localStorage.getItem(STORAGE_KEY)) || {}) }
  } catch {
    return DEFAULTS
  }
}

// Save the messages in the browser
function saveTemplates(templates) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(templates))
  } catch {
    // Not being able to save the message is fine
  }
}

// Put a tenant's details into a message
function fillTemplate(template, item) {
  return template
    .replaceAll('{name}', item.tenant_name.split(' ')[0])
    .replaceAll('{amount}', money(item.amount_overdue))
    .replaceAll('{unit}', item.unit_number)
    .replaceAll('{property}', item.property_name)
    .replaceAll('{days}', String(item.days_late))
}

// Read a time from the backend (it saves times in UTC without a "Z" on the end, so we add it)
const parseTime = (value) => new Date(value.endsWith('Z') ? value : `${value}Z`)

// Was this time today?
const isToday = (value) => parseTime(value).toDateString() === new Date().toDateString()

// Say how long ago a reminder was sent
function lastText(value) {
  if (!value) return 'Not reminded yet'
  // How many whole days have passed
  const days = Math.floor((Date.now() - parseTime(value).getTime()) / 86400000)
  if (isToday(value) || days <= 0) return 'Reminded today'
  if (days === 1) return 'Reminded yesterday'
  return `Last reminded ${days} days ago`
}

// The page that helps you remind everyone who is late
export default function Owing() {
  // The dashboard numbers and the reminder history (nothing until they arrive)
  const [data, setData] = useState(null)
  const [summary, setSummary] = useState({})
  // The error message, if something failed
  const [error, setError] = useState('')
  // The messages, and whether the message editor is open
  const [templates, setTemplates] = useState(loadTemplates)
  const [showMessage, setShowMessage] = useState(false)
  // Which tenants to show: "all" or "pending" (not reminded today)
  const [filter, setFilter] = useState('all')

  // Load the overdue tenants and the reminder history
  const load = useCallback(() => {
    setError('')
    Promise.all([getDashboard(), getReminderSummary()])
      .then(([dashboard, list]) => {
        setData(dashboard)
        // Make a quick lookup from a lease's id to its reminder history
        setSummary(Object.fromEntries(list.map((entry) => [entry.lease_id, entry])))
      })
      .catch((err) => setError(err.message))
  }, [])

  // Load them when the page opens
  useEffect(() => {
    load()
  }, [load])

  // Change the messages and save them
  function updateTemplates(next) {
    setTemplates(next)
    saveTemplates(next)
  }

  // The message we are using now
  const current = templates[templates.lang]
  // The tenants who are overdue
  const items = data ? data.overdue : []
  // Has this tenant been reminded today?
  const remindedToday = (item) => Boolean(summary[item.lease_id] && isToday(summary[item.lease_id].last_sent_at))
  // Count how many were reminded today, and who is left
  const doneCount = items.filter(remindedToday).length
  const pending = items.filter((item) => !remindedToday(item))
  const visible = filter === 'pending' ? pending : items

  // Record a reminder in the database and update the screen
  async function log(item, message) {
    try {
      const entry = await logReminder({ lease_id: item.lease_id, message, amount_overdue: item.amount_overdue })
      setSummary((previous) => ({
        ...previous,
        [item.lease_id]: {
          lease_id: item.lease_id,
          last_sent_at: entry.created_at,
          times_30_days: ((previous[item.lease_id] && previous[item.lease_id].times_30_days) || 0) + 1,
        },
      }))
    } catch (err) {
      setError(err.message)
    }
  }

  // Open WhatsApp for the next tenant who has not been reminded today
  function remindNext() {
    const next = pending[0]
    if (!next) return
    const message = fillTemplate(current, next)
    // Open the chat (this must happen right in the click, or the browser blocks it)
    window.open(whatsappLink(next.tenant_phone, message), '_blank', 'noopener')
    // Then record it
    log(next, message)
  }

  // If loading failed, show the message and a retry button
  if (error && !data) {
    return (
      <div>
        <h1 className="text-3xl font-extrabold text-forest-900">Who owes me</h1>
        <div className="mt-6 rounded-3xl bg-terracotta/10 p-6 text-terracotta">
          <p className="font-semibold">Could not load this page</p>
          <p className="mt-1 text-sm">{error}</p>
          <button onClick={load} className="mt-4 flex items-center gap-2 rounded-xl bg-terracotta px-4 py-2 text-sm font-semibold text-white">
            <RefreshCw size={16} /> Try again
          </button>
        </div>
      </div>
    )
  }

  // While waiting, show grey placeholder boxes
  if (!data) {
    return (
      <div>
        <h1 className="text-3xl font-extrabold text-forest-900">Who owes me</h1>
        <div className="mt-6 space-y-3">
          <div className="h-40 animate-pulse rounded-3xl bg-forest-100" />
          <div className="h-24 animate-pulse rounded-2xl bg-forest-100" />
        </div>
      </div>
    )
  }

  return (
    <div>
      {/* The title */}
      <h1 className="text-3xl font-extrabold text-forest-900">Who owes me</h1>
      <p className="text-muted">Everyone who is late, and a quick way to remind them.</p>

      {/* If nobody is late, show good news */}
      {items.length === 0 ? (
        <div className="mt-8 flex flex-col items-center rounded-3xl bg-forest-100 p-10 text-center text-forest-700">
          <CheckCircle2 size={36} />
          <p className="mt-3 font-display text-2xl font-bold text-forest-900">Everyone is up to date</p>
          <p className="mt-1 text-sm">Nobody is overdue right now.</p>
        </div>
      ) : (
        <>
          {/* The green summary card with the main button */}
          <motion.div
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-6 rounded-3xl bg-forest-900 p-6 text-white shadow-xl"
          >
            <div className="flex items-end justify-between gap-4">
              <div>
                <p className="text-sm text-forest-200">Overdue in total</p>
                <p className="font-display text-4xl font-bold">{money(data.total_overdue)}</p>
                <p className="mt-1 text-sm text-forest-200">
                  {items.length} tenant{items.length === 1 ? '' : 's'}
                </p>
              </div>
              <div className="text-right">
                <p className="font-display text-3xl font-bold">
                  {doneCount}/{items.length}
                </p>
                <p className="text-xs text-forest-200">reminded today</p>
              </div>
            </div>
            {/* A bar that fills as tenants are reminded */}
            <div className="mt-4 h-2 overflow-hidden rounded-full bg-white/15">
              <motion.div
                className="h-full rounded-full bg-gold"
                initial={false}
                animate={{ width: `${(doneCount / items.length) * 100}%` }}
                transition={{ duration: 0.5 }}
              />
            </div>
            <motion.button
              whileTap={{ scale: 0.98 }}
              onClick={remindNext}
              disabled={pending.length === 0}
              className="mt-5 flex w-full items-center justify-center gap-2 rounded-xl bg-gold py-3.5 font-semibold text-forest-900 shadow-lg transition hover:brightness-95 disabled:opacity-60"
            >
              {pending.length === 0 ? (
                <>
                  <CheckCircle2 size={18} /> Everyone has been reminded today
                </>
              ) : (
                <>
                  <BellRing size={18} /> Remind next: {pending[0].tenant_name.split(' ')[0]}
                </>
              )}
            </motion.button>
            <p className="mt-2 text-center text-xs text-forest-200">
              Opens WhatsApp with the message ready. Press send there, then come back and tap again.
            </p>
          </motion.div>

          {/* The message editor */}
          <div className="mt-4 rounded-2xl bg-paper shadow-sm">
            <button
              onClick={() => setShowMessage(!showMessage)}
              className="flex w-full items-center justify-between px-5 py-4 text-left"
            >
              <span>
                <span className="block font-semibold text-forest-900">The message</span>
                <span className="block text-xs text-muted">
                  {templates.lang === 'en' ? 'English' : 'Kiswahili'} · tap to see or change it
                </span>
              </span>
              {showMessage ? <ChevronUp size={18} className="text-muted" /> : <ChevronDown size={18} className="text-muted" />}
            </button>
            {showMessage && (
              <div className="border-t border-forest-100 px-5 pb-5 pt-4">
                {/* Choose the language */}
                <div className="grid grid-cols-2 gap-2 rounded-xl bg-forest-100 p-1">
                  {[
                    { key: 'en', label: 'English' },
                    { key: 'sw', label: 'Kiswahili' },
                  ].map((language) => (
                    <button
                      key={language.key}
                      onClick={() => updateTemplates({ ...templates, lang: language.key })}
                      className={`rounded-lg py-2 text-sm font-semibold transition ${
                        templates.lang === language.key ? 'bg-paper text-forest-900 shadow-sm' : 'text-forest-700'
                      }`}
                    >
                      {language.label}
                    </button>
                  ))}
                </div>
                {/* Edit the message */}
                <textarea
                  value={current}
                  onChange={(e) => updateTemplates({ ...templates, [templates.lang]: e.target.value })}
                  className="mt-3 min-h-28 w-full rounded-xl border border-forest-200 bg-paper px-4 py-3 text-sm outline-none transition focus:border-forest-500 focus:ring-4 focus:ring-forest-100"
                />
                <p className="mt-2 text-xs text-muted">
                  {'You can use {name}, {amount}, {unit}, {property} and {days}. They are filled in for each tenant.'}
                </p>
                {/* A preview for the first tenant */}
                <p className="mt-3 text-xs font-semibold text-forest-900">Preview for {items[0].tenant_name.split(' ')[0]}:</p>
                <p className="mt-1 rounded-xl bg-cream p-3 text-sm text-ink/80">{fillTemplate(current, items[0])}</p>
                <button
                  onClick={() => updateTemplates({ ...templates, [templates.lang]: DEFAULTS[templates.lang] })}
                  className="mt-3 text-sm font-medium text-forest-700 hover:underline"
                >
                  Go back to the original message
                </button>
              </div>
            )}
          </div>

          {error && (
            <div role="alert" className="mt-4 rounded-xl bg-terracotta/10 px-4 py-3 text-sm font-medium text-terracotta">
              {error}
            </div>
          )}

          {/* The filter buttons */}
          <div className="mt-6 flex gap-2">
            {[
              { key: 'all', label: `Everyone ${items.length}` },
              { key: 'pending', label: `Not reminded today ${pending.length}` },
            ].map((item) => (
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

          {/* The list of tenants */}
          {visible.length === 0 ? (
            <p className="mt-6 rounded-2xl bg-paper p-6 text-center text-muted shadow-sm">Nobody left to remind today.</p>
          ) : (
            <motion.div
              key={filter}
              variants={listAnimation}
              initial="hidden"
              animate="show"
              className="mt-4 grid gap-3 md:grid-cols-2"
            >
              {visible.map((item) => {
                // The message for this tenant, and when they were last reminded
                const message = fillTemplate(current, item)
                const last = summary[item.lease_id]
                const done = remindedToday(item)
                return (
                  <motion.div key={item.lease_id} variants={itemAnimation} className="rounded-2xl bg-paper p-4 shadow-sm">
                    {/* The top part opens the tenant's page */}
                    <Link to={`/tenants/${item.tenant_id}`} className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="truncate font-semibold text-forest-900">{item.tenant_name}</p>
                        <p className="truncate text-sm text-muted">
                          {item.unit_number} · {item.property_name}
                        </p>
                        {item.lease_status === 'ended' && (
                          <span className="mt-1 inline-block rounded-full bg-amber/20 px-2 py-0.5 text-xs font-semibold text-amber">
                            Moved out
                          </span>
                        )}
                      </div>
                      <div className="text-right">
                        <p className="font-display text-lg font-bold text-terracotta">{money(item.amount_overdue)}</p>
                        <p className="text-xs text-muted">{item.days_late} days late</p>
                      </div>
                    </Link>

                    {/* How recently they were reminded */}
                    <p className={`mt-3 flex items-center gap-1.5 text-xs font-medium ${done ? 'text-forest-500' : 'text-muted'}`}>
                      {done && <CheckCircle2 size={14} />}
                      {lastText(last && last.last_sent_at)}
                      {last && last.times_30_days > 1 ? ` · ${last.times_30_days} times this month` : ''}
                    </p>

                    {/* The buttons */}
                    <div className="mt-3 grid grid-cols-3 gap-2">
                      <a
                        href={whatsappLink(item.tenant_phone, message)}
                        target="_blank"
                        rel="noopener noreferrer"
                        onClick={() => log(item, message)}
                        className={`col-span-2 flex items-center justify-center gap-2 rounded-xl py-2.5 text-sm font-semibold text-white transition ${
                          done ? 'bg-forest-200 text-forest-900 hover:bg-forest-500 hover:text-white' : 'bg-forest-500 hover:bg-forest-700'
                        }`}
                      >
                        <MessageCircle size={16} /> {done ? 'Remind again' : 'WhatsApp'}
                      </a>
                      <a
                        href={`tel:+${item.tenant_phone}`}
                        aria-label={`Call ${item.tenant_name}`}
                        className="flex items-center justify-center rounded-xl bg-forest-100 py-2.5 text-forest-700 hover:bg-forest-200"
                      >
                        <Phone size={16} />
                      </a>
                    </div>
                    <Link
                      to={`/tenants/${item.tenant_id}`}
                      className="mt-2 flex items-center justify-center gap-2 rounded-xl py-2 text-sm font-medium text-forest-700 hover:bg-forest-100"
                    >
                      <Wallet size={15} /> Record a payment
                    </Link>
                  </motion.div>
                )
              })}
            </motion.div>
          )}
        </>
      )}
    </div>
  )
}