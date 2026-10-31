// Import the React tools we need
import { useCallback, useEffect, useState } from 'react'
// Import the animation tool
import { motion } from 'framer-motion'
// Import the icons we use
import { Check, CheckCircle2, Copy, KeyRound, Loader2, MessageCircle, RefreshCw, Smartphone } from 'lucide-react'
// Import our own files
import { getPaymentDetails, getPortalAccess, givePortalAccess, savePaymentDetails, setPortalActive } from '../api'
import { phoneLocal } from '../format'
import ConfirmDialog from '../components/ConfirmDialog'
import { Field, inputClass } from '../components/Field'
import Modal from '../components/Modal'

// The page where owners give tenants access to the portal
export default function PortalAccess() {
  // The list of tenants (nothing until it arrives)
  const [rows, setRows] = useState(null)
  // The error message, if loading failed
  const [error, setError] = useState('')
  // The payment details form
  const [paybill, setPaybill] = useState('')
  const [hint, setHint] = useState('')
  const [instructions, setInstructions] = useState('')
  const [detailsBusy, setDetailsBusy] = useState(false)
  const [detailsError, setDetailsError] = useState('')
  const [detailsSaved, setDetailsSaved] = useState(false)
  // The login details just made (shown only once)
  const [granted, setGranted] = useState(null)
  // The tenant a "new password" question is about
  const [resetting, setResetting] = useState(null)
  // The tenant id that is busy
  const [busyId, setBusyId] = useState(null)
  // True for a moment after the password was copied
  const [copied, setCopied] = useState(false)

  // Load the list and the payment details
  const load = useCallback(async () => {
    setError('')
    try {
      const [list, details] = await Promise.all([getPortalAccess(), getPaymentDetails()])
      setRows(list)
      setPaybill(details.paybill_number || '')
      setHint(details.account_hint || '')
      setInstructions(details.instructions || '')
    } catch (err) {
      setError(err.message)
    }
  }, [])

  // Load them when the page opens
  useEffect(() => {
    load()
  }, [load])

  // Save the payment details
  async function saveDetails(event) {
    // Stop the page from reloading
    event.preventDefault()
    setDetailsError('')
    setDetailsSaved(false)
    setDetailsBusy(true)
    try {
      await savePaymentDetails({ paybill_number: paybill.trim() || null, account_hint: hint.trim() || null, instructions: instructions.trim() || null })
      setDetailsSaved(true)
    } catch (err) {
      setDetailsError(err.message)
    } finally {
      setDetailsBusy(false)
    }
  }

  // Give a tenant access (or make a new temporary password)
  async function give(row) {
    setError('')
    setBusyId(row.tenant_id)
    try {
      setGranted(await givePortalAccess(row.tenant_id))
      load()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusyId(null)
    }
  }

  // Switch a tenant's access on or off
  async function toggle(row) {
    setError('')
    setBusyId(row.tenant_id)
    try {
      await setPortalActive(row.tenant_id, !row.is_active)
      load()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusyId(null)
    }
  }

  // Copy the temporary password
  async function copyPassword() {
    try {
      await navigator.clipboard.writeText(granted.temporary_password)
      setCopied(true)
      setTimeout(() => setCopied(false), 1800)
    } catch {
      // If copying is blocked, the password is still on the screen
    }
  }

  // The message sent to the tenant on WhatsApp
  const message = granted
    ? `Hello ${granted.tenant_name.split(' ')[0]}, you can now see your rent balance, your payment history and notices on EstateLoom.\n\nOpen: ${window.location.origin}\nSign in with your phone number ${phoneLocal(granted.phone)} and this temporary password: ${granted.temporary_password}\n\nYou will be asked to choose your own password.`
    : ''

  return (
    <div>
      <h1 className="text-3xl font-extrabold text-forest-900">Tenant portal</h1>
      <p className="text-muted">Let tenants see their balance, report problems, and read your notices.</p>

      {/* If loading failed, show the message and a retry button */}
      {error && (
        <div className="mt-6 rounded-3xl bg-terracotta/10 p-6 text-terracotta">
          <p className="font-semibold">Something went wrong</p>
          <p className="mt-1 text-sm">{error}</p>
          <button onClick={load} className="mt-4 flex items-center gap-2 rounded-xl bg-terracotta px-4 py-2 text-sm font-semibold text-white">
            <RefreshCw size={16} /> Try again
          </button>
        </div>
      )}

      {/* The payment details */}
      <form onSubmit={saveDetails} className="mt-6 space-y-4 rounded-3xl bg-paper p-5 shadow-sm">
        <h2 className="font-display text-lg font-bold text-forest-900">How tenants should pay</h2>
        <p className="text-sm text-muted">Shown on every tenant's home screen, with a button to copy the number.</p>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Paybill or Till number">
            <input className={inputClass} value={paybill} onChange={(e) => setPaybill(e.target.value)} inputMode="numeric" placeholder="247247" maxLength={9} />
          </Field>
          <Field label="What to type as the account">
            <input className={inputClass} value={hint} onChange={(e) => setHint(e.target.value)} placeholder="Your unit number, like A12" maxLength={80} />
          </Field>
        </div>
        <Field label="Other words about paying (optional)">
          <textarea className={`${inputClass} min-h-16`} value={instructions} onChange={(e) => setInstructions(e.target.value)} maxLength={500} placeholder="Rent is due by the 5th of every month." />
        </Field>
        {detailsError && (
          <div role="alert" className="rounded-xl bg-terracotta/10 px-4 py-3 text-sm font-medium text-terracotta">
            {detailsError}
          </div>
        )}
        {detailsSaved && (
          <div role="status" className="flex items-center gap-2 rounded-xl bg-forest-100 px-4 py-3 text-sm font-medium text-forest-700">
            <CheckCircle2 size={18} /> Saved. Tenants see this now.
          </div>
        )}
        <button type="submit" disabled={detailsBusy} className="flex items-center justify-center gap-2 rounded-xl bg-forest-900 px-6 py-3 text-sm font-semibold text-white hover:bg-forest-700 disabled:opacity-70">
          {detailsBusy && <Loader2 size={16} className="animate-spin" />} Save payment details
        </button>
      </form>

      {/* The tenants */}
      <h2 className="mb-3 mt-8 text-xl font-bold text-forest-900">Your tenants</h2>
      {!rows && !error && <div className="h-24 animate-pulse rounded-2xl bg-forest-100" />}
      {rows && rows.length === 0 && (
        <div className="flex flex-col items-center rounded-3xl bg-paper p-10 text-center shadow-sm">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-forest-100 text-forest-700">
            <Smartphone size={26} />
          </div>
          <p className="mt-4 font-semibold text-forest-900">No tenants yet</p>
          <p className="mt-1 text-sm text-muted">Move a tenant into a unit and they will appear here.</p>
        </div>
      )}
      <div className="grid gap-3 md:grid-cols-2">
        {rows &&
          rows.map((row) => (
            <motion.div key={row.tenant_id} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="rounded-2xl bg-paper p-4 shadow-sm">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="truncate font-semibold text-forest-900">{row.tenant_name}</p>
                  <p className="truncate text-sm text-muted">
                    {row.unit_number ? `Unit ${row.unit_number} · ${row.property_name}` : 'No active tenancy'} · {phoneLocal(row.phone)}
                  </p>
                </div>
                <span
                  className={`shrink-0 rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                    !row.has_access ? 'bg-ink/10 text-muted' : !row.is_active ? 'bg-terracotta/15 text-terracotta' : row.must_change_password ? 'bg-amber/20 text-amber' : 'bg-forest-100 text-forest-700'
                  }`}
                >
                  {!row.has_access ? 'No access' : !row.is_active ? 'Switched off' : row.must_change_password ? 'Not signed in yet' : 'Active'}
                </span>
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                {!row.has_access ? (
                  <button onClick={() => give(row)} disabled={busyId === row.tenant_id} className="flex items-center gap-2 rounded-xl bg-forest-900 px-4 py-2 text-sm font-semibold text-white hover:bg-forest-700 disabled:opacity-70">
                    {busyId === row.tenant_id ? <Loader2 size={15} className="animate-spin" /> : <KeyRound size={15} />} Give access
                  </button>
                ) : (
                  <>
                    <button onClick={() => setResetting(row)} className="rounded-xl bg-forest-100 px-4 py-2 text-sm font-semibold text-forest-700 hover:bg-forest-200">
                      New password
                    </button>
                    <button onClick={() => toggle(row)} disabled={busyId === row.tenant_id} className="rounded-xl px-4 py-2 text-sm font-semibold text-terracotta hover:bg-terracotta/10 disabled:opacity-70">
                      {row.is_active ? 'Switch off' : 'Switch on'}
                    </button>
                  </>
                )}
              </div>
            </motion.div>
          ))}
      </div>

      {/* The login details, shown once */}
      <Modal open={granted !== null} title="Portal access ready" onClose={() => setGranted(null)}>
        {granted && (
          <div>
            <p className="text-sm text-muted">
              Send these to <span className="font-semibold text-forest-900">{granted.tenant_name}</span>. The password is shown <span className="font-semibold">only this once</span>. If you lose it, make a new one.
            </p>
            <div className="mt-4 rounded-2xl bg-cream p-4">
              <p className="text-xs text-muted">Sign in with phone number</p>
              <p className="font-semibold text-forest-900">{phoneLocal(granted.phone)}</p>
              <p className="mt-3 text-xs text-muted">Temporary password</p>
              <div className="flex items-center justify-between gap-3">
                <p className="font-mono text-2xl font-bold tracking-widest text-forest-900">{granted.temporary_password}</p>
                <button onClick={copyPassword} className="flex shrink-0 items-center gap-1.5 rounded-lg bg-forest-100 px-3 py-1.5 text-xs font-semibold text-forest-700 hover:bg-forest-200">
                  {copied ? <Check size={13} /> : <Copy size={13} />} {copied ? 'Copied' : 'Copy'}
                </button>
              </div>
            </div>
            <a
              href={`https://wa.me/${granted.phone}?text=${encodeURIComponent(message)}`}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-4 flex items-center justify-center gap-2 rounded-xl bg-forest-500 py-3 text-sm font-semibold text-white hover:bg-forest-700"
            >
              <MessageCircle size={16} /> Send on WhatsApp
            </a>
            <p className="mt-3 text-xs text-muted">The tenant will be asked to choose their own password the first time they sign in.</p>
          </div>
        )}
      </Modal>

      {/* Make a new password */}
      <ConfirmDialog
        open={resetting !== null}
        title="Make a new password?"
        message={resetting ? `${resetting.tenant_name} will be signed out everywhere, and the old password stops working. You will get a new temporary password to send.` : ''}
        confirmLabel="Make new password"
        onClose={() => setResetting(null)}
        onConfirm={async () => {
          const row = resetting
          setResetting(null)
          await give(row)
        }}
      />
    </div>
  )
}