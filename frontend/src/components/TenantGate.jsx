// Import the React tools we need
import { useEffect, useState } from 'react'
// Import the page-switching tool that shows the page inside
import { Outlet } from 'react-router-dom'
// Import the animation tool
import { motion } from 'framer-motion'
// Import the icons we use
import { KeyRound, Loader2, LogOut } from 'lucide-react'
// Import our own files
import { useAuth } from '../AuthContext'
import { changePortalPassword, getPortalStatus, saveToken } from '../api'
import { Field, inputClass } from './Field'
import Wordmark from './Logo'

// The screen where a tenant chooses their own password for the first time
function SetPassword({ name, onDone }) {
  // The logout function
  const { signOut } = useAuth()
  // What has been typed so far
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [again, setAgain] = useState('')
  // The error message, and whether we are waiting for the backend
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  // Run when the form is sent
  async function handleSubmit(event) {
    // Stop the page from reloading
    event.preventDefault()
    setError('')
    // The two new passwords must match
    if (next !== again) {
      setError('The two new passwords are not the same.')
      return
    }
    setBusy(true)
    try {
      // Change the password, and keep the fresh login we get back
      const result = await changePortalPassword({ current_password: current, new_password: next })
      saveToken(result.access_token)
      onDone()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-cream px-6 py-10">
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="w-full max-w-sm">
        <Wordmark size="lg" />
        <div className="mt-8 flex h-14 w-14 items-center justify-center rounded-2xl bg-forest-100 text-forest-700">
          <KeyRound size={26} />
        </div>
        <h1 className="mt-4 text-3xl font-extrabold text-forest-900">Welcome, {name.split(' ')[0]}</h1>
        <p className="mt-1 text-muted">Choose your own password so only you can see your rent details.</p>

        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          <Field label="The temporary password you were given">
            <input className={inputClass} type="password" value={current} onChange={(e) => setCurrent(e.target.value)} required autoComplete="current-password" />
          </Field>
          <Field label="Your new password" hint="At least 8 characters, with some letters. Not a common password.">
            <input className={inputClass} type="password" value={next} onChange={(e) => setNext(e.target.value)} required minLength={8} maxLength={64} autoComplete="new-password" />
          </Field>
          <Field label="New password again">
            <input className={inputClass} type="password" value={again} onChange={(e) => setAgain(e.target.value)} required minLength={8} maxLength={64} autoComplete="new-password" />
          </Field>
          {error && (
            <div role="alert" className="rounded-xl bg-terracotta/10 px-4 py-3 text-sm font-medium text-terracotta">
              {error}
            </div>
          )}
          <button type="submit" disabled={busy} className="flex w-full items-center justify-center gap-2 rounded-xl bg-forest-900 py-3.5 font-semibold text-white hover:bg-forest-700 disabled:opacity-70">
            {busy && <Loader2 size={18} className="animate-spin" />} Save my password
          </button>
        </form>
        <button onClick={signOut} className="mt-4 flex w-full items-center justify-center gap-2 text-sm font-medium text-muted hover:text-forest-900">
          <LogOut size={14} /> Log out
        </button>
      </motion.div>
    </div>
  )
}

// A gate around the tenant screens: a tenant who still has a temporary password must choose their own first
export default function TenantGate() {
  // Whether the tenant must change the password (nothing until we know)
  const [status, setStatus] = useState(null)
  // The error message, if we could not find out
  const [error, setError] = useState('')

  // Find out when the gate first appears
  useEffect(() => {
    getPortalStatus()
      .then(setStatus)
      .catch((err) => setError(err.message))
  }, [])

  // If we could not find out, say so
  if (error) {
    return <p className="m-6 rounded-2xl bg-terracotta/10 p-4 text-terracotta">{error}</p>
  }
  // While waiting, show a spinner
  if (!status) {
    return (
      <div className="flex min-h-screen items-center justify-center text-forest-700">
        <Loader2 className="animate-spin" size={32} />
      </div>
    )
  }
  // A temporary password: choose a real one first
  if (status.must_change_password) {
    return <SetPassword name={status.tenant_name} onDone={() => setStatus({ ...status, must_change_password: false })} />
  }
  // Otherwise show the page
  return <Outlet />
}