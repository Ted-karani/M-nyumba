// Import the React tools we need
import { useCallback, useEffect, useState } from 'react'
// Import the animation tool
import { motion } from 'framer-motion'
// Import the icons we use
import { CheckCircle2, Loader2, RefreshCw, Wrench } from 'lucide-react'
// Import our own files
import { createPortalRepair, getPortalRepairs } from '../api'
import { Field, inputClass } from '../components/Field'
import { formatDate } from '../format'

// The words and colors for each status
const STATUS = {
  open: { label: 'Reported', style: 'bg-amber/20 text-amber' },
  in_progress: { label: 'Being fixed', style: 'bg-gold/25 text-forest-900' },
  fixed: { label: 'Fixed', style: 'bg-forest-100 text-forest-700' },
}

// The page where a tenant reports problems and sees how they are going
export default function PortalRepairs() {
  // The problems reported so far (nothing until they arrive)
  const [repairs, setRepairs] = useState(null)
  // What has been typed so far
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [urgent, setUrgent] = useState(false)
  // The error message, and whether we are waiting for the backend
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  // True for a moment after a problem was sent
  const [sent, setSent] = useState(false)

  // Load the list
  const load = useCallback(() => {
    getPortalRepairs()
      .then(setRepairs)
      .catch((err) => setError(err.message))
  }, [])

  // Load it when the page opens
  useEffect(() => {
    load()
  }, [load])

  // Run when the form is sent
  async function handleSubmit(event) {
    // Stop the page from reloading
    event.preventDefault()
    setError('')
    setSent(false)
    setBusy(true)
    try {
      await createPortalRepair({ title: title.trim(), description: description.trim() || null, priority: urgent ? 'urgent' : 'normal' })
      setTitle('')
      setDescription('')
      setUrgent(false)
      setSent(true)
      load()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="text-3xl font-extrabold text-forest-900">Report a problem</h1>
      <p className="text-muted">Something broken in your home? Tell your landlord here.</p>

      {/* The form */}
      <form onSubmit={handleSubmit} className="mt-6 space-y-4 rounded-3xl bg-paper p-5 shadow-sm">
        <Field label="What is wrong?">
          <input className={inputClass} value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Leaking kitchen tap" required minLength={3} maxLength={100} />
        </Field>
        <Field label="Tell us more (optional)">
          <textarea className={`${inputClass} min-h-20`} value={description} onChange={(e) => setDescription(e.target.value)} maxLength={1000} placeholder="Where it is, since when..." />
        </Field>
        <button type="button" onClick={() => setUrgent(!urgent)} className="flex w-full items-center justify-between gap-3 rounded-xl bg-cream px-4 py-3 text-left">
          <span>
            <span className="block text-sm font-semibold text-forest-900">This is urgent</span>
            <span className="block text-xs text-muted">For example water pouring out, no power, or a broken lock.</span>
          </span>
          <span className={`relative h-6 w-11 shrink-0 rounded-full transition ${urgent ? 'bg-terracotta' : 'bg-forest-200'}`}>
            <span className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-all ${urgent ? 'left-[22px]' : 'left-0.5'}`} />
          </span>
        </button>
        {error && (
          <div role="alert" className="rounded-xl bg-terracotta/10 px-4 py-3 text-sm font-medium text-terracotta">
            {error}
          </div>
        )}
        {sent && (
          <div role="status" className="flex items-center gap-2 rounded-xl bg-forest-100 px-4 py-3 text-sm font-medium text-forest-700">
            <CheckCircle2 size={18} /> Sent. Your landlord can now see it.
          </div>
        )}
        <button type="submit" disabled={busy} className="flex w-full items-center justify-center gap-2 rounded-xl bg-forest-900 py-3.5 font-semibold text-white hover:bg-forest-700 disabled:opacity-70">
          {busy && <Loader2 size={18} className="animate-spin" />} Send to my landlord
        </button>
      </form>

      {/* The problems reported so far */}
      <h2 className="mb-3 mt-8 text-xl font-bold text-forest-900">My reports</h2>
      {!repairs && !error && <div className="h-20 animate-pulse rounded-2xl bg-forest-100" />}
      {!repairs && error && (
        <button onClick={load} className="flex items-center gap-2 rounded-xl bg-forest-100 px-4 py-2 text-sm font-semibold text-forest-700">
          <RefreshCw size={16} /> Try again
        </button>
      )}
      {repairs && repairs.length === 0 && (
        <div className="flex flex-col items-center rounded-3xl bg-paper p-8 text-center shadow-sm">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-forest-100 text-forest-700">
            <Wrench size={22} />
          </div>
          <p className="mt-3 text-sm text-muted">You have not reported anything yet.</p>
        </div>
      )}
      <div className="space-y-3">
        {repairs &&
          repairs.map((repair) => {
            const status = STATUS[repair.status] || STATUS.open
            return (
              <motion.div key={repair.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="rounded-2xl bg-paper p-4 shadow-sm">
                <div className="flex items-start justify-between gap-3">
                  <p className="font-semibold text-forest-900">{repair.title}</p>
                  <span className={`shrink-0 rounded-full px-2.5 py-0.5 text-xs font-semibold ${status.style}`}>{status.label}</span>
                </div>
                {repair.description && <p className="mt-1 text-sm text-ink/80">{repair.description}</p>}
                <p className="mt-2 text-xs text-muted">
                  Reported {formatDate(repair.reported_on)}
                  {repair.priority === 'urgent' ? ' · urgent' : ''}
                  {repair.resolved_on ? ` · fixed ${formatDate(repair.resolved_on)}` : ''}
                </p>
              </motion.div>
            )
          })}
      </div>
    </div>
  )
}