// Import the React tools we need
import { useEffect, useState } from 'react'
// Import our own files
import { getAdminEvents, getAdminPayments } from '../api'
import { formatDateTime } from '../inspection'
import { formatDate, money } from '../format'

// The page with the list of all payments, and the log of what the admin did
export default function AdminRecords() {
  // Which tab is showing: "payments" or "log"
  const [tab, setTab] = useState('payments')
  // The lists (nothing until they arrive)
  const [payments, setPayments] = useState(null)
  const [events, setEvents] = useState(null)
  // The error message, if loading failed
  const [error, setError] = useState('')

  // Load both lists when the page opens
  useEffect(() => {
    Promise.all([getAdminPayments(), getAdminEvents()])
      .then(([paymentList, eventList]) => {
        setPayments(paymentList)
        setEvents(eventList)
      })
      .catch((err) => setError(err.message))
  }, [])

  return (
    <div>
      <h1 className="text-3xl font-extrabold text-forest-900">Payments and log</h1>
      <p className="text-muted">What landlords paid you, and everything you did to their accounts.</p>

      {/* The two tabs */}
      <div className="mt-6 flex gap-2">
        {[
          { key: 'payments', label: 'Payments' },
          { key: 'log', label: 'Admin log' },
        ].map((item) => (
          <button
            key={item.key}
            onClick={() => setTab(item.key)}
            className={`rounded-full px-4 py-2 text-sm font-semibold transition ${tab === item.key ? 'bg-forest-900 text-white' : 'bg-paper text-forest-700 hover:bg-forest-100'}`}
          >
            {item.label}
          </button>
        ))}
      </div>

      {error && <p className="mt-6 rounded-2xl bg-terracotta/10 p-4 text-terracotta">{error}</p>}
      {!error && !payments && <div className="mt-6 h-24 animate-pulse rounded-2xl bg-forest-100" />}

      {/* The payments */}
      {tab === 'payments' && payments && (
        <div className="mt-6 divide-y divide-forest-100 overflow-hidden rounded-2xl bg-paper shadow-sm">
          {payments.length === 0 && <p className="p-5 text-sm text-muted">No payments recorded yet.</p>}
          {payments.map((payment) => (
            <div key={payment.id} className="flex items-center justify-between gap-3 p-4">
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-forest-900">{payment.owner_name}</p>
                <p className="truncate text-xs text-muted">
                  {formatDate(payment.paid_on)} · {payment.method} · {payment.months} month{payment.months === 1 ? '' : 's'} · access until {formatDate(payment.covers_until)}
                  {payment.reference ? ` · ${payment.reference}` : ''}
                </p>
              </div>
              <p className="shrink-0 font-semibold text-forest-900">{money(payment.amount)}</p>
            </div>
          ))}
        </div>
      )}

      {/* The log */}
      {tab === 'log' && events && (
        <div className="mt-6 divide-y divide-forest-100 overflow-hidden rounded-2xl bg-paper shadow-sm">
          {events.length === 0 && <p className="p-5 text-sm text-muted">Nothing here yet.</p>}
          {events.map((event) => (
            <div key={event.id} className="p-4">
              <p className="text-sm font-semibold text-forest-900">
                {event.action}
                {event.owner_name ? ` · ${event.owner_name}` : ''}
              </p>
              {event.detail && <p className="mt-0.5 text-sm text-ink/80">{event.detail}</p>}
              <p className="mt-1 text-xs text-muted">{formatDateTime(event.created_at)}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}