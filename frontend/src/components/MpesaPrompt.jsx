// Import the React tools we need
import { useEffect, useRef, useState } from 'react'
// Import the animation tool
import { motion } from 'framer-motion'
// Import the icons we use
import { CheckCircle2, Loader2, RefreshCw, Smartphone, XCircle } from 'lucide-react'
// Import our own files
import { getMpesaStatus, getPayNowStatus, payNow, requestMpesa } from '../api'
import { money, phoneLocal } from '../format'
import { Field, inputClass } from './Field'

// How long we wait for the PIN before saying "still waiting" (in milliseconds)
const WAIT_MS = 90000

// The panel for asking for an M-Pesa payment (owners) or paying by M-Pesa (tenants)
export default function MpesaPrompt({ mode, leaseId, balance, tenantPhone, onPaid }) {
  // Is this the tenant's version?
  const isTenant = mode === 'tenant'
  // What has been typed so far
  const [amount, setAmount] = useState(balance > 0 ? String(balance) : '')
  const [phone, setPhone] = useState(isTenant ? '' : tenantPhone ? phoneLocal(tenantPhone) : '')
  // Which stage we are in: "form", "waiting", "paid", "cancelled", "failed" or "timeout"
  const [stage, setStage] = useState('form')
  // Safaricom's id for the request, and the answers we got back
  const [requestId, setRequestId] = useState('')
  const [receipt, setReceipt] = useState('')
  const [message, setMessage] = useState('')
  // The error message, and whether we are waiting for the backend
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  // The timer that asks "has it been paid yet?" every few seconds, and when we started waiting
  const timer = useRef(null)
  const startedAt = useRef(0)

  // Stop asking
  function stopPolling() {
    if (timer.current) {
      clearInterval(timer.current)
      timer.current = null
    }
  }

  // Stop asking when this panel closes
  useEffect(() => stopPolling, [])

  // Ask once what happened to the request
  async function check(id) {
    try {
      const result = await (isTenant ? getPayNowStatus(id) : getMpesaStatus(id))
      if (result.status === 'paid') {
        stopPolling()
        setReceipt(result.receipt || '')
        setStage('paid')
        // Let the page behind refresh its numbers
        onPaid()
      } else if (result.status === 'cancelled') {
        stopPolling()
        setStage('cancelled')
      } else if (result.status === 'failed') {
        stopPolling()
        setMessage(result.message || '')
        setStage('failed')
      } else if (Date.now() - startedAt.current > WAIT_MS) {
        stopPolling()
        setStage('timeout')
      }
    } catch {
      // A hiccup in the network: keep waiting
    }
  }

  // Start asking every 3 seconds
  function startPolling(id) {
    stopPolling()
    startedAt.current = Date.now()
    timer.current = setInterval(() => check(id), 3000)
  }

  // Run when the form is sent
  async function handleSend(event) {
    // Stop the page from reloading
    event.preventDefault()
    setError('')
    // The amount must be a whole number of shillings
    const value = Number(amount)
    if (!Number.isInteger(value) || value < 1) {
      setError('Enter a whole number of shillings, like 5000.')
      return
    }
    if (isTenant && balance > 0 && value > balance) {
      setError(`You can pay at most ${money(balance)}.`)
      return
    }
    setBusy(true)
    try {
      const result = isTenant
        ? await payNow({ lease_id: leaseId, amount: value })
        : await requestMpesa({ lease_id: leaseId, amount: value, phone: phone.trim() || null })
      setRequestId(result.checkout_request_id)
      setStage('waiting')
      startPolling(result.checkout_request_id)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  // The tenant did not answer in time: wait a bit longer
  function keepWaiting() {
    setStage('waiting')
    startPolling(requestId)
    check(requestId)
  }

  // Start again from the form
  function tryAgain() {
    setStage('form')
    setError('')
  }

  // The form
  if (stage === 'form') {
    return (
      <form onSubmit={handleSend} className="space-y-4">
        <div className="flex items-start gap-3 rounded-2xl bg-forest-100 p-4 text-forest-700">
          <Smartphone size={22} className="mt-0.5 shrink-0" />
          <p className="text-sm">
            {isTenant
              ? 'A prompt will pop up on your phone. Enter your M-Pesa PIN to pay.'
              : 'A prompt will pop up on the tenant’s phone. They enter their M-Pesa PIN to pay, and the payment is recorded by itself.'}
          </p>
        </div>

        <Field label="Amount (KSh)" hint={balance > 0 ? `${isTenant ? 'You owe' : 'Balance'}: ${money(balance)}` : undefined}>
          <input className={inputClass} type="number" min="1" step="1" inputMode="numeric" value={amount} onChange={(e) => setAmount(e.target.value)} required autoFocus />
        </Field>
        {balance > 0 && (
          <button type="button" onClick={() => setAmount(String(balance))} className="-mt-2 text-sm font-semibold text-forest-700 hover:underline">
            Use the full balance
          </button>
        )}

        {/* Owners can choose which phone gets the prompt, tenants always use their own */}
        {isTenant ? (
          <p className="rounded-xl bg-cream px-4 py-3 text-sm text-muted">The prompt goes to the phone number your landlord has for you.</p>
        ) : (
          <Field label="Phone to ask (optional)" hint="Leave empty to use the tenant’s own phone.">
            <input className={inputClass} type="tel" inputMode="tel" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="0712 345 678" />
          </Field>
        )}

        {error && (
          <div role="alert" className="rounded-xl bg-terracotta/10 px-4 py-3 text-sm font-medium text-terracotta">
            {error}
          </div>
        )}
        <button type="submit" disabled={busy} className="flex w-full items-center justify-center gap-2 rounded-xl bg-forest-900 py-3.5 font-semibold text-white hover:bg-forest-700 disabled:opacity-70">
          {busy && <Loader2 size={18} className="animate-spin" />} {isTenant ? 'Send the prompt to my phone' : 'Send the prompt'}
        </button>
      </form>
    )
  }

  // Waiting for the PIN
  if (stage === 'waiting') {
    return (
      <div className="flex flex-col items-center py-6 text-center">
        <motion.div animate={{ scale: [1, 1.08, 1] }} transition={{ repeat: Infinity, duration: 1.6 }} className="flex h-16 w-16 items-center justify-center rounded-3xl bg-forest-100 text-forest-700">
          <Smartphone size={30} />
        </motion.div>
        <p className="mt-4 font-display text-xl font-bold text-forest-900">{isTenant ? 'Check your phone' : 'Waiting for the tenant'}</p>
        <p className="mt-1 max-w-xs text-sm text-muted">
          {isTenant ? 'Enter your M-Pesa PIN on the prompt. This page updates by itself.' : 'Ask them to enter their M-Pesa PIN. This updates by itself.'}
        </p>
        <Loader2 size={20} className="mt-4 animate-spin text-forest-500" />
      </div>
    )
  }

  // Paid
  if (stage === 'paid') {
    return (
      <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} className="flex flex-col items-center py-6 text-center">
        <div className="flex h-16 w-16 items-center justify-center rounded-3xl bg-forest-100 text-forest-500">
          <CheckCircle2 size={34} />
        </div>
        <p className="mt-4 font-display text-xl font-bold text-forest-900">Payment received</p>
        {receipt && <p className="mt-1 font-mono text-sm font-semibold text-forest-700">{receipt}</p>}
        <p className="mt-1 text-sm text-muted">It has been added to the statement.</p>
      </motion.div>
    )
  }

  // Cancelled, failed, or no answer in time
  return (
    <div className="flex flex-col items-center py-6 text-center">
      <div className="flex h-16 w-16 items-center justify-center rounded-3xl bg-terracotta/10 text-terracotta">
        <XCircle size={34} />
      </div>
      <p className="mt-4 font-display text-xl font-bold text-forest-900">
        {stage === 'cancelled' ? 'The prompt was cancelled' : stage === 'failed' ? 'The payment did not go through' : 'No answer yet'}
      </p>
      <p className="mt-1 max-w-xs text-sm text-muted">
        {stage === 'cancelled'
          ? 'Nothing was charged.'
          : stage === 'failed'
          ? message || 'Nothing was charged. Please try again.'
          : 'If a payment was made, it will appear in the statement shortly. You can also keep waiting.'}
      </p>
      <div className="mt-5 flex w-full gap-3">
        {stage === 'timeout' && (
          <button onClick={keepWaiting} className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-forest-100 py-3 text-sm font-semibold text-forest-700 hover:bg-forest-200">
            <RefreshCw size={16} /> Keep waiting
          </button>
        )}
        <button onClick={tryAgain} className="flex-1 rounded-xl bg-forest-900 py-3 text-sm font-semibold text-white hover:bg-forest-700">
          Start again
        </button>
      </div>
    </div>
  )
}