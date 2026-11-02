// Import the React tools we need
import { useCallback, useEffect, useState } from 'react'
// Import the icons we use
import { Loader2, Trash2, TriangleAlert } from 'lucide-react'
// Import our own files
import { cancelAdminClosing, deleteAdminAccount, getAdminClosing, startAdminClosing } from '../api'
import { formatDate } from '../format'
import { Field, inputClass } from './Field'
import Modal from './Modal'

// Friendly names for the kinds of records (any other kind is shown by its own name)
const LABELS = {
  properties: 'Properties',
  units: 'Units',
  tenants: 'Tenants',
  leases: 'Leases',
  charges: 'Charges',
  payments: 'Payments',
  maintenance_requests: 'Repairs',
  documents: 'Documents',
  inspections: 'Checklists',
  inspection_items: 'Checklist areas',
  inspection_photos: 'Checklist photos',
  listings: 'Vacancy listings',
  listing_photos: 'Listing photos',
  notices: 'Notices',
  expenses: 'Expenses',
  tasks: 'Tasks',
  users: 'Caretaker and tenant logins',
  audit_logs: 'Activity log lines',
}

// The part of a landlord's panel for closing and deleting their account
export default function AdminClosingSection({ account, onChanged }) {
  // Where closing stands (nothing until it arrives)
  const [state, setState] = useState(null)
  // The error message, and which action is busy
  const [error, setError] = useState('')
  const [busy, setBusy] = useState('')
  // An extra sentence for the landlord
  const [note, setNote] = useState('')
  // The delete window, and what is typed in it
  const [deleting, setDeleting] = useState(false)
  const [confirmEmail, setConfirmEmail] = useState('')
  const [force, setForce] = useState(false)

  // Load where closing stands
  const load = useCallback(() => {
    getAdminClosing(account.owner_id)
      .then(setState)
      .catch((err) => setError(err.message))
  }, [account.owner_id])

  // Load it when the section opens, and again when the account's status changes
  useEffect(() => {
    load()
  }, [load, account.status])

  // Run an action, then refresh
  async function run(name, action) {
    setError('')
    setBusy(name)
    try {
      await action()
      await load()
      onChanged()
      return true
    } catch (err) {
      setError(err.message)
      return false
    } finally {
      setBusy('')
    }
  }

  // Delete for good
  async function handleDelete() {
    const ok = await run('delete', () => deleteAdminAccount(account.owner_id, { confirm_email: confirmEmail.trim(), force }))
    if (ok) setDeleting(false)
  }

  // The kinds of records to list in the delete window (the ones with a friendly name first)
  const lines = state
    ? Object.entries(state.counts)
        .filter(([name]) => LABELS[name])
        .map(([name, count]) => [LABELS[name], count])
    : []
  const others = state ? Object.entries(state.counts).filter(([name]) => !LABELS[name]).reduce((sum, [, count]) => sum + count, 0) : 0
  const emailMatches = state && confirmEmail.trim().toLowerCase() === state.email.toLowerCase()
  const allowed = state && (state.can_delete || force)

  return (
    <div className="mt-5 rounded-2xl bg-cream p-4">
      <h3 className="font-display text-base font-bold text-forest-900">Closing and deleting this account</h3>
      {!state && !error && <div className="mt-3 h-10 animate-pulse rounded-xl bg-forest-100" />}
      {error && (
        <div role="alert" className="mt-3 rounded-xl bg-terracotta/10 px-4 py-3 text-sm font-medium text-terracotta">
          {error}
        </div>
      )}

      {state && !state.closing && (
        <div className="mt-3">
          <p className="text-sm text-muted">
            Closing makes the account read-only for 30 days. The landlord can still look at everything and download a full copy of their data. After that you can delete it for good.
          </p>
          <div className="mt-3">
            <Field label="Extra sentence for the landlord (optional)">
              <input className={inputClass} value={note} onChange={(e) => setNote(e.target.value)} maxLength={200} />
            </Field>
          </div>
          <button
            onClick={() => run('start', () => startAdminClosing(account.owner_id, note.trim() || null))}
            disabled={busy === 'start'}
            className="mt-3 flex items-center gap-2 rounded-xl bg-terracotta/10 px-4 py-2.5 text-sm font-semibold text-terracotta hover:bg-terracotta hover:text-white disabled:opacity-70"
          >
            {busy === 'start' && <Loader2 size={15} className="animate-spin" />} Start closing (30 days)
          </button>
        </div>
      )}

      {state && state.closing && (
        <div className="mt-3">
          <p className="rounded-xl bg-amber/15 px-4 py-3 text-sm font-medium text-amber">
            Closing started on {formatDate(state.closing_started_at.slice(0, 10))}.{' '}
            {state.can_delete ? 'The 30 days are over, so you can delete the account.' : `You can delete it from ${formatDate(state.delete_allowed_on)} (${state.days_left} day${state.days_left === 1 ? '' : 's'} left).`}
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            <button onClick={() => run('cancel', () => cancelAdminClosing(account.owner_id))} disabled={busy === 'cancel'} className="flex items-center gap-2 rounded-xl bg-forest-100 px-4 py-2.5 text-sm font-semibold text-forest-700 hover:bg-forest-200 disabled:opacity-70">
              {busy === 'cancel' && <Loader2 size={15} className="animate-spin" />} Cancel closing
            </button>
            <button
              onClick={() => {
                setConfirmEmail('')
                setForce(false)
                setDeleting(true)
              }}
              className="flex items-center gap-2 rounded-xl bg-terracotta px-4 py-2.5 text-sm font-semibold text-white hover:opacity-90"
            >
              <Trash2 size={15} /> Delete permanently...
            </button>
          </div>
        </div>
      )}

      {/* The delete window */}
      <Modal open={deleting} title="Delete this account for good" onClose={() => setDeleting(false)}>
        {state && (
          <div>
            <div className="flex items-start gap-3 rounded-2xl bg-terracotta/10 p-4 text-terracotta">
              <TriangleAlert size={20} className="mt-0.5 shrink-0" />
              <p className="text-sm font-medium">This cannot be undone. Everything {state.full_name} entered is deleted, including their files. Only the record of what they paid you, and your admin log, are kept.</p>
            </div>
            <p className="mt-4 text-sm font-semibold text-forest-900">What will be deleted</p>
            <ul className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-sm text-ink/80">
              {lines.map(([label, count]) => (
                <li key={label} className="flex justify-between">
                  <span>{label}</span>
                  <span className="font-semibold text-forest-900">{count}</span>
                </li>
              ))}
              <li className="flex justify-between">
                <span>Files</span>
                <span className="font-semibold text-forest-900">{state.files}</span>
              </li>
              {others > 0 && (
                <li className="flex justify-between">
                  <span>Other records</span>
                  <span className="font-semibold text-forest-900">{others}</span>
                </li>
              )}
            </ul>
            <p className="mt-3 text-xs text-muted">Make sure you have a recent database backup before deleting. Render’s backups keep deleted information until they expire.</p>

            {!state.can_delete && (
              <button type="button" onClick={() => setForce(!force)} className="mt-4 flex w-full items-center justify-between gap-3 rounded-xl bg-cream px-4 py-3 text-left">
                <span>
                  <span className="block text-sm font-semibold text-forest-900">Delete before the 30 days are over</span>
                  <span className="block text-xs text-muted">Only if the landlord asked for it.</span>
                </span>
                <span className={`relative h-6 w-11 shrink-0 rounded-full transition ${force ? 'bg-terracotta' : 'bg-forest-200'}`}>
                  <span className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-all ${force ? 'left-[22px]' : 'left-0.5'}`} />
                </span>
              </button>
            )}

            <div className="mt-4">
              <Field label={`Type ${state.email} to confirm`}>
                <input className={inputClass} value={confirmEmail} onChange={(e) => setConfirmEmail(e.target.value)} autoComplete="off" />
              </Field>
            </div>
            {error && (
              <div role="alert" className="mt-3 rounded-xl bg-terracotta/10 px-4 py-3 text-sm font-medium text-terracotta">
                {error}
              </div>
            )}
            <div className="mt-4 flex gap-3">
              <button onClick={() => setDeleting(false)} className="flex-1 rounded-xl bg-forest-100 py-3 font-semibold text-forest-700 hover:bg-forest-200">
                Cancel
              </button>
              <button
                onClick={handleDelete}
                disabled={!emailMatches || !allowed || busy === 'delete'}
                className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-terracotta py-3 font-semibold text-white hover:opacity-90 disabled:opacity-40"
              >
                {busy === 'delete' && <Loader2 size={18} className="animate-spin" />} Delete for good
              </button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}