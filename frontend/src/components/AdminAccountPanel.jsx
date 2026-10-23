// Import the React tools we need
import { useEffect, useState } from 'react'
// Import the icons we use
import { Check, Copy, KeyRound, Loader2, LogOut, MessageCircle, ShieldOff } from 'lucide-react'
// Import our own files
import { getAdminAccountPayments, recordAdminPayment, resetAdminPassword, resetAdminTwoStep, signOutAdminAccount, updateAdminAccount } from '../api'
import { METHOD_OPTIONS, PLAN_LABELS, STATE_STYLES, accessText } from '../admin'
import { formatDateTime } from '../inspection'
import { formatDate, money, phoneLocal, todayISO } from '../format'
import ConfirmDialog from './ConfirmDialog'
import { Field, inputClass } from './Field'

// A box with a title, used to group things
function Section({ title, children }) {
  return (
    <div className="mt-5 rounded-2xl bg-cream p-4">
      <h3 className="font-display text-base font-bold text-forest-900">{title}</h3>
      <div className="mt-3">{children}</div>
    </div>
  )
}

// Everything you can do to one landlord's account
export default function AdminAccountPanel({ account, onChanged }) {
  // What has been typed in the plan and access section
  const [plan, setPlan] = useState(account.plan)
  const [status, setStatus] = useState(account.status)
  const [paidUntil, setPaidUntil] = useState(account.paid_until || '')
  const [unitLimit, setUnitLimit] = useState(account.unit_limit ? String(account.unit_limit) : '')
  const [notes, setNotes] = useState(account.notes || '')
  const [statusNote, setStatusNote] = useState(account.status_note || '')
  // What has been typed in the payment section
  const [amount, setAmount] = useState('')
  const [months, setMonths] = useState('1')
  const [method, setMethod] = useState('mpesa')
  const [reference, setReference] = useState('')
  const [paidOn, setPaidOn] = useState(todayISO())
  // The payments this landlord made
  const [payments, setPayments] = useState(null)
  // Messages, and which action is busy
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState('')
  // The new login details just made (shown only once)
  const [credentials, setCredentials] = useState(null)
  // Which "are you sure" question is open
  const [asking, setAsking] = useState('')
  // True for a moment after the password was copied
  const [copied, setCopied] = useState(false)

  // Load this landlord's payments
  function loadPayments() {
    getAdminAccountPayments(account.owner_id)
      .then(setPayments)
      .catch((err) => setError(err.message))
  }
  useEffect(() => {
    loadPayments()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [account.owner_id])

  // Run an action: show that it is busy, show the result, and refresh the list behind
  async function run(name, action, done) {
    setError('')
    setMessage('')
    setBusy(name)
    try {
      const result = await action()
      if (done) setMessage(done)
      onChanged()
      return result
    } catch (err) {
      setError(err.message)
      return null
    } finally {
      setBusy('')
    }
  }

  // Save the plan and access section
  function savePlan(event) {
    event.preventDefault()
    return run(
      'plan',
      () =>
        updateAdminAccount(account.owner_id, {
          plan,
          status,
          paid_until: paidUntil || null,
          unit_limit: unitLimit ? Number(unitLimit) : null,
          notes: notes.trim() || null,
          status_note: statusNote.trim() || null,
        }),
      'Saved.'
    )
  }

  // Record a payment
  async function savePayment(event) {
    event.preventDefault()
    const result = await run(
      'payment',
      () =>
        recordAdminPayment(account.owner_id, {
          amount: Number(amount),
          months: Number(months),
          method,
          reference: reference.trim() || null,
          paid_on: paidOn || null,
        }),
      'Payment recorded. Their access was extended.'
    )
    if (result) {
      setAmount('')
      setReference('')
      loadPayments()
    }
  }

  // Make a new temporary password
  async function newPassword() {
    setAsking('')
    const result = await run('password', () => resetAdminPassword(account.owner_id))
    if (result) setCredentials(result)
  }

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

  const state = STATE_STYLES[account.state]
  // The message sent to the landlord on WhatsApp after a new password
  const whatsapp = credentials
    ? `Hello ${credentials.full_name.split(' ')[0]}, your M-nyumba sign-in:\n\nOpen: ${window.location.origin}\nEmail: ${credentials.email}\nTemporary password: ${credentials.temporary_password}\n\nYou will be asked to choose your own password.`
    : ''

  return (
    <div>
      {/* The summary */}
      <div className="rounded-2xl bg-forest-900 p-4 text-white">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="truncate font-display text-xl font-bold">{account.full_name}</p>
            <p className="truncate text-sm text-forest-200">{account.email}</p>
            {account.phone && <p className="text-sm text-forest-200">{phoneLocal(account.phone)}</p>}
          </div>
          <span className={`shrink-0 rounded-full px-2.5 py-0.5 text-xs font-semibold ${state.style}`}>{state.label}</span>
        </div>
        <div className="mt-4 grid grid-cols-3 gap-2 text-center">
          <div className="rounded-xl bg-white/10 p-2">
            <p className="text-[11px] text-forest-200">Plan</p>
            <p className="text-sm font-bold">{PLAN_LABELS[account.plan]}</p>
          </div>
          <div className="rounded-xl bg-white/10 p-2">
            <p className="text-[11px] text-forest-200">Access</p>
            <p className="text-sm font-bold">{accessText(account)}</p>
          </div>
          <div className="rounded-xl bg-white/10 p-2">
            <p className="text-[11px] text-forest-200">Units</p>
            <p className="text-sm font-bold">
              {account.units}
              {account.unit_limit ? ` / ${account.unit_limit}` : ''}
            </p>
          </div>
        </div>
        <p className="mt-3 text-xs text-forest-200">
          {account.properties} properties · {account.occupied_units} occupied units · {account.tenants} tenants · {account.caretakers} caretakers · {account.portal_users} tenants with portal
        </p>
        <p className="mt-1 text-xs text-forest-200">
          {account.last_sign_in ? `Last sign-in ${formatDateTime(account.last_sign_in)}` : 'Not signed in during the last 30 days'} · 2-step login {account.two_step ? 'on' : 'off'}
          {account.must_change_password ? ' · still on the temporary password' : ''}
        </p>
      </div>

      {error && (
        <div role="alert" className="mt-4 rounded-xl bg-terracotta/10 px-4 py-3 text-sm font-medium text-terracotta">
          {error}
        </div>
      )}
      {message && (
        <div role="status" className="mt-4 rounded-xl bg-forest-100 px-4 py-3 text-sm font-medium text-forest-700">
          {message}
        </div>
      )}

      {/* Plan and access */}
      <Section title="Plan and access">
        <form onSubmit={savePlan} className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <Field label="Plan">
              <select className={inputClass} value={plan} onChange={(e) => setPlan(e.target.value)}>
                <option value="pilot">Pilot (free trial)</option>
                <option value="paid">Paid</option>
              </select>
            </Field>
            <Field label="Status">
              <select className={inputClass} value={status} onChange={(e) => setStatus(e.target.value)}>
                <option value="active">Active</option>
                <option value="read_only">Read-only</option>
                <option value="suspended">Suspended</option>
                <option value="closed">Closed</option>
              </select>
            </Field>
            <Field label="Access until">
              <input className={inputClass} type="date" value={paidUntil} onChange={(e) => setPaidUntil(e.target.value)} />
            </Field>
            <Field label="Unit limit">
              <input className={inputClass} type="number" min="1" step="1" inputMode="numeric" value={unitLimit} onChange={(e) => setUnitLimit(e.target.value)} placeholder="No limit" />
            </Field>
          </div>
          <Field label="Message the landlord sees" hint="Shown when the account is read-only, suspended or closed.">
            <input className={inputClass} value={statusNote} onChange={(e) => setStatusNote(e.target.value)} maxLength={300} placeholder="Your payment is overdue. Please contact us." />
          </Field>
          <Field label="Private notes (only you see these)">
            <textarea className={`${inputClass} min-h-16`} value={notes} onChange={(e) => setNotes(e.target.value)} maxLength={1000} />
          </Field>
          <button type="submit" disabled={busy === 'plan'} className="flex items-center justify-center gap-2 rounded-xl bg-forest-900 px-5 py-2.5 text-sm font-semibold text-white hover:bg-forest-700 disabled:opacity-70">
            {busy === 'plan' && <Loader2 size={15} className="animate-spin" />} Save changes
          </button>
        </form>
      </Section>

      {/* Record a payment */}
      <Section title="Record a payment from them">
        <form onSubmit={savePayment} className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <Field label="Amount (KSh)">
              <input className={inputClass} type="number" min="1" step="1" inputMode="numeric" value={amount} onChange={(e) => setAmount(e.target.value)} required />
            </Field>
            <Field label="Months it pays for">
              <select className={inputClass} value={months} onChange={(e) => setMonths(e.target.value)}>
                {[1, 2, 3, 6, 12].map((number) => (
                  <option key={number} value={number}>
                    {number}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Paid by">
              <select className={inputClass} value={method} onChange={(e) => setMethod(e.target.value)}>
                {METHOD_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Date received">
              <input className={inputClass} type="date" value={paidOn} max={todayISO()} onChange={(e) => setPaidOn(e.target.value)} />
            </Field>
          </div>
          <Field label="M-Pesa code or reference (optional)">
            <input className={inputClass} value={reference} onChange={(e) => setReference(e.target.value)} maxLength={40} />
          </Field>
          <button type="submit" disabled={busy === 'payment'} className="flex items-center justify-center gap-2 rounded-xl bg-forest-500 px-5 py-2.5 text-sm font-semibold text-white hover:bg-forest-700 disabled:opacity-70">
            {busy === 'payment' && <Loader2 size={15} className="animate-spin" />} Record payment
          </button>
        </form>
        {payments && payments.length > 0 && (
          <ul className="mt-4 divide-y divide-forest-100 border-t border-forest-100">
            {payments.map((payment) => (
              <li key={payment.id} className="flex items-center justify-between gap-3 py-2 text-sm">
                <span className="min-w-0 truncate text-ink/80">
                  {formatDate(payment.paid_on)} · {payment.months} month{payment.months === 1 ? '' : 's'}
                  {payment.reference ? ` · ${payment.reference}` : ''}
                </span>
                <span className="shrink-0 font-semibold text-forest-900">{money(payment.amount)}</span>
              </li>
            ))}
          </ul>
        )}
      </Section>

      {/* Help with signing in */}
      <Section title="Help them sign in">
        <div className="flex flex-wrap gap-2">
          <button onClick={() => setAsking('password')} className="flex items-center gap-2 rounded-xl bg-forest-100 px-4 py-2.5 text-sm font-semibold text-forest-700 hover:bg-forest-200">
            <KeyRound size={15} /> New password
          </button>
          <button onClick={() => setAsking('signout')} className="flex items-center gap-2 rounded-xl bg-forest-100 px-4 py-2.5 text-sm font-semibold text-forest-700 hover:bg-forest-200">
            <LogOut size={15} /> Sign out everywhere
          </button>
          <button onClick={() => setAsking('twostep')} disabled={!account.two_step} className="flex items-center gap-2 rounded-xl bg-forest-100 px-4 py-2.5 text-sm font-semibold text-forest-700 hover:bg-forest-200 disabled:opacity-50">
            <ShieldOff size={15} /> Reset 2-step login
          </button>
        </div>
        {credentials && (
          <div className="mt-4 rounded-2xl bg-paper p-4">
            <p className="text-xs text-muted">Temporary password (shown only this once)</p>
            <div className="mt-1 flex items-center justify-between gap-3">
              <p className="font-mono text-2xl font-bold tracking-widest text-forest-900">{credentials.temporary_password}</p>
              <button onClick={copyPassword} className="flex shrink-0 items-center gap-1.5 rounded-lg bg-forest-100 px-3 py-1.5 text-xs font-semibold text-forest-700 hover:bg-forest-200">
                {copied ? <Check size={13} /> : <Copy size={13} />} {copied ? 'Copied' : 'Copy'}
              </button>
            </div>
            <a
              href={`https://wa.me/${credentials.phone || ''}?text=${encodeURIComponent(whatsapp)}`}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-3 flex items-center justify-center gap-2 rounded-xl bg-forest-500 py-2.5 text-sm font-semibold text-white hover:bg-forest-700"
            >
              <MessageCircle size={15} /> Send on WhatsApp
            </a>
          </div>
        )}
      </Section>

      <ConfirmDialog
        open={asking === 'password'}
        title="Make a new password?"
        message={`${account.full_name} will be signed out everywhere, and the old password stops working. You will get a new temporary password to send.`}
        confirmLabel="Make new password"
        onClose={() => setAsking('')}
        onConfirm={newPassword}
      />
      <ConfirmDialog
        open={asking === 'signout'}
        title="Sign out everywhere?"
        message={`${account.full_name} will have to sign in again on every device.`}
        confirmLabel="Sign out"
        onClose={() => setAsking('')}
        onConfirm={async () => {
          setAsking('')
          await run('signout', () => signOutAdminAccount(account.owner_id), 'Signed out everywhere.')
        }}
      />
      <ConfirmDialog
        open={asking === 'twostep'}
        title="Reset their 2-step login?"
        message={`Only do this after you are sure it really is ${account.full_name}, for example by phone. 2-step login will be turned off and they will be signed out. They should turn it on again straight away.`}
        confirmLabel="Reset 2-step login"
        onClose={() => setAsking('')}
        onConfirm={async () => {
          setAsking('')
          await run('twostep', () => resetAdminTwoStep(account.owner_id), '2-step login was reset.')
        }}
      />
    </div>
  )
}