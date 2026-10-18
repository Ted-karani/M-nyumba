// Import the React tools we need
import { useEffect, useState } from 'react'
// Import the tool that draws QR codes
import QRCode from 'qrcode'
// Import the animation tool
import { motion } from 'framer-motion'
// Import the icons we use
import { Check, Copy, Loader2, ShieldCheck } from 'lucide-react'
// Import our own files
import { disableTwoStep, enableTwoStep, getTwoStep, startTwoStep } from '../api'
import { Field, inputClass } from './Field'

// The card on the account page for turning 2-step login on and off
export default function TwoStepCard() {
  // Whether it is on (nothing until it arrives)
  const [status, setStatus] = useState(null)
  // What we are doing: "idle", "setup" (scan the code), "codes" (save the recovery codes), or "disable"
  const [mode, setMode] = useState('idle')
  // The secret and QR code during setup
  const [setup, setSetup] = useState(null)
  const [qr, setQr] = useState('')
  // The recovery codes (shown once)
  const [codes, setCodes] = useState([])
  // What has been typed
  const [code, setCode] = useState('')
  const [password, setPassword] = useState('')
  // The error message, and whether the codes were copied
  const [error, setError] = useState('')
  const [copied, setCopied] = useState(false)
  // True while we wait for the backend
  const [busy, setBusy] = useState(false)

  // Find out whether it is on
  async function loadStatus() {
    try {
      setStatus(await getTwoStep())
    } catch (err) {
      setError(err.message)
    }
  }

  // Load it when the card first appears
  useEffect(() => {
    loadStatus()
  }, [])

  // Start the setup: get a secret and draw its QR code
  async function begin() {
    setError('')
    setBusy(true)
    try {
      const data = await startTwoStep()
      setSetup(data)
      setQr(await QRCode.toDataURL(data.otpauth_url, { margin: 1, width: 220 }))
      setCode('')
      setMode('setup')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  // Finish the setup with the first code from the app
  async function confirm(event) {
    event.preventDefault()
    setError('')
    setBusy(true)
    try {
      const data = await enableTwoStep(code.trim())
      setCodes(data.recovery_codes)
      setMode('codes')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  // Turn it off
  async function turnOff(event) {
    event.preventDefault()
    setError('')
    setBusy(true)
    try {
      await disableTwoStep({ password, code: code.trim() })
      setMode('idle')
      setPassword('')
      setCode('')
      await loadStatus()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  // Copy the recovery codes
  async function copyCodes() {
    try {
      await navigator.clipboard.writeText(codes.join('\n'))
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // If copying is blocked, the codes are still on the screen
    }
  }

  // The error box, shown in every state
  const errorBox = error && (
    <div role="alert" className="mt-4 rounded-xl bg-terracotta/10 px-4 py-3 text-sm font-medium text-terracotta">
      {error}
    </div>
  )

  return (
    <div className="mt-5 rounded-3xl bg-paper p-6 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <h2 className="flex items-center gap-2 font-display text-lg font-bold text-forest-900">
          <ShieldCheck size={20} className="text-gold" /> 2-step login
        </h2>
        {status && (
          <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${status.enabled ? 'bg-forest-100 text-forest-700' : 'bg-ink/10 text-muted'}`}>
            {status.enabled ? 'On' : 'Off'}
          </span>
        )}
      </div>

      {!status && !error && <div className="mt-4 h-16 animate-pulse rounded-2xl bg-forest-100" />}

      {/* Off: explain and offer to turn it on */}
      {status && !status.enabled && mode === 'idle' && (
        <div>
          <p className="mt-3 text-sm text-muted">
            After your password, sign-in asks for a 6-digit code from an app on your phone. Even if someone learns your password, they cannot get in without your phone.
          </p>
          <button
            onClick={begin}
            disabled={busy}
            className="mt-4 flex items-center gap-2 rounded-xl bg-forest-900 px-5 py-3 text-sm font-semibold text-white hover:bg-forest-700 disabled:opacity-70"
          >
            {busy && <Loader2 size={16} className="animate-spin" />} Turn on 2-step login
          </button>
          {errorBox}
        </div>
      )}

      {/* Setting up: scan the QR code and type the first code */}
      {mode === 'setup' && setup && (
        <motion.form initial={{ opacity: 0 }} animate={{ opacity: 1 }} onSubmit={confirm} className="mt-4">
          <ol className="list-decimal space-y-1 pl-5 text-sm text-muted">
            <li>Install an authenticator app (Google Authenticator, Microsoft Authenticator, or Authy).</li>
            <li>In the app, add an account and scan this picture.</li>
            <li>Type the 6-digit code the app shows.</li>
          </ol>
          <div className="mt-4 flex flex-col items-center gap-3 rounded-2xl bg-cream p-4">
            {qr && <img src={qr} alt="QR code for your authenticator app" className="h-44 w-44 rounded-lg" />}
            <p className="text-xs text-muted">Cannot scan? Type this key into the app instead:</p>
            <p className="break-all text-center font-mono text-sm font-semibold text-forest-900">{(setup.secret.match(/.{1,4}/g) || []).join(' ')}</p>
          </div>
          <div className="mt-4">
            <Field label="6-digit code from the app">
              <input
                className={`${inputClass} text-center font-mono text-xl tracking-widest`}
                value={code}
                onChange={(e) => setCode(e.target.value)}
                inputMode="numeric"
                autoComplete="one-time-code"
                maxLength={7}
                placeholder="123456"
                required
              />
            </Field>
          </div>
          {errorBox}
          <div className="mt-4 flex gap-3">
            <button
              type="button"
              onClick={() => {
                setMode('idle')
                setError('')
              }}
              className="flex-1 rounded-xl bg-forest-100 py-3 text-sm font-semibold text-forest-700 hover:bg-forest-200"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={busy}
              className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-forest-900 py-3 text-sm font-semibold text-white hover:bg-forest-700 disabled:opacity-70"
            >
              {busy && <Loader2 size={16} className="animate-spin" />} Turn on
            </button>
          </div>
        </motion.form>
      )}

      {/* Just turned on: show the recovery codes once */}
      {mode === 'codes' && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mt-4">
          <p className="rounded-xl bg-gold/20 px-4 py-3 text-sm font-semibold text-forest-900">
            2-step login is on. Save these recovery codes now. They are shown only once.
          </p>
          <p className="mt-3 text-sm text-muted">If you lose your phone, each code lets you sign in one time. Keep them somewhere safe, away from your phone.</p>
          <div className="mt-3 grid grid-cols-2 gap-2 rounded-2xl bg-cream p-4 font-mono text-sm font-semibold text-forest-900">
            {codes.map((item) => (
              <span key={item}>{item}</span>
            ))}
          </div>
          <div className="mt-4 flex gap-3">
            <button onClick={copyCodes} className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-forest-100 py-3 text-sm font-semibold text-forest-700 hover:bg-forest-200">
              {copied ? <Check size={16} /> : <Copy size={16} />} {copied ? 'Copied' : 'Copy codes'}
            </button>
            <button
              onClick={async () => {
                setCodes([])
                setMode('idle')
                await loadStatus()
              }}
              className="flex-1 rounded-xl bg-forest-900 py-3 text-sm font-semibold text-white hover:bg-forest-700"
            >
              I saved them
            </button>
          </div>
        </motion.div>
      )}

      {/* On: show how many recovery codes are left, and offer to turn it off */}
      {status && status.enabled && mode === 'idle' && (
        <div>
          <p className="mt-3 text-sm text-muted">
            Sign-in asks for a code from your app. You have <span className="font-semibold text-forest-900">{status.recovery_codes_left}</span> recovery code
            {status.recovery_codes_left === 1 ? '' : 's'} left.
          </p>
          <button onClick={() => setMode('disable')} className="mt-4 text-sm font-semibold text-terracotta hover:underline">
            Turn off 2-step login
          </button>
          {errorBox}
        </div>
      )}

      {/* Turning it off: needs the password and a code */}
      {mode === 'disable' && (
        <motion.form initial={{ opacity: 0 }} animate={{ opacity: 1 }} onSubmit={turnOff} className="mt-4 space-y-4">
          <Field label="Your password">
            <input className={inputClass} type="password" value={password} onChange={(e) => setPassword(e.target.value)} required autoComplete="current-password" />
          </Field>
          <Field label="A code from your app, or a recovery code">
            <input className={`${inputClass} font-mono`} value={code} onChange={(e) => setCode(e.target.value)} required maxLength={20} autoComplete="one-time-code" />
          </Field>
          {errorBox}
          <div className="flex gap-3">
            <button
              type="button"
              onClick={() => {
                setMode('idle')
                setError('')
              }}
              className="flex-1 rounded-xl bg-forest-100 py-3 text-sm font-semibold text-forest-700 hover:bg-forest-200"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={busy}
              className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-terracotta py-3 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-70"
            >
              {busy && <Loader2 size={16} className="animate-spin" />} Turn off
            </button>
          </div>
        </motion.form>
      )}
    </div>
  )
}