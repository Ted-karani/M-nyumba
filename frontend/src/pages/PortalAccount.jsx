// Import the React tool for remembering values
import { useState } from 'react'
// Import the animation tool
import { motion } from 'framer-motion'
// Import the icons we use
import { CheckCircle2, KeyRound, Loader2, LogOut } from 'lucide-react'
// Import our own files
import { useAuth } from '../AuthContext'
import { changePortalPassword, saveToken } from '../api'
import { Field, inputClass } from '../components/Field'
import { initials, phoneLocal } from '../format'

// The page where a tenant sees their details and changes their password
export default function PortalAccount() {
  // Get the logged-in user and the logout function
  const { user, signOut } = useAuth()
  // What has been typed so far
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [again, setAgain] = useState('')
  // The error message, whether it worked, and whether we are waiting for the backend
  const [error, setError] = useState('')
  const [done, setDone] = useState(false)
  const [busy, setBusy] = useState(false)

  // Run when the form is sent
  async function handleSubmit(event) {
    // Stop the page from reloading
    event.preventDefault()
    setError('')
    setDone(false)
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
      setCurrent('')
      setNext('')
      setAgain('')
      setDone(true)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto max-w-xl">
      <h1 className="text-3xl font-extrabold text-forest-900">My account</h1>

      {/* Who you are */}
      <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} className="mt-6 flex items-center gap-4 rounded-3xl bg-forest-900 p-6 text-white shadow-xl">
        <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-gold font-display text-lg font-bold text-forest-900">{initials(user.full_name)}</div>
        <div className="min-w-0">
          <p className="truncate font-display text-xl font-bold">{user.full_name}</p>
          <p className="truncate text-sm text-forest-200">Sign in with {phoneLocal(user.phone || '')}</p>
        </div>
      </motion.div>

      {/* Change password */}
      <div className="mt-5 rounded-3xl bg-paper p-6 shadow-sm">
        <h2 className="flex items-center gap-2 font-display text-lg font-bold text-forest-900">
          <KeyRound size={20} className="text-gold" /> Change your password
        </h2>
        <form onSubmit={handleSubmit} className="mt-4 space-y-4">
          <Field label="Your current password">
            <input className={inputClass} type="password" value={current} onChange={(e) => setCurrent(e.target.value)} required autoComplete="current-password" />
          </Field>
          <Field label="New password" hint="At least 8 characters, with some letters. Not a common password.">
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
          {done && (
            <div role="status" className="flex items-center gap-2 rounded-xl bg-forest-100 px-4 py-3 text-sm font-medium text-forest-700">
              <CheckCircle2 size={18} /> Your password was changed. Other devices were signed out.
            </div>
          )}
          <button type="submit" disabled={busy} className="flex w-full items-center justify-center gap-2 rounded-xl bg-forest-900 py-3.5 font-semibold text-white hover:bg-forest-700 disabled:opacity-70">
            {busy && <Loader2 size={18} className="animate-spin" />} Change password
          </button>
        </form>
        <p className="mt-3 text-xs text-muted">Forgot your password? Ask your landlord to make you a new one.</p>
      </div>

      <button onClick={signOut} className="mt-5 flex w-full items-center justify-center gap-2 rounded-xl bg-paper py-3.5 font-semibold text-forest-700 shadow-sm hover:bg-forest-100">
        <LogOut size={18} /> Log out
      </button>
    </div>
  )
}