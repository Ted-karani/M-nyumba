// Import the React tool for remembering values
import { useState } from 'react'
// Import the animation tool
import { motion } from 'framer-motion'
// Import the icons we use
import { CheckCircle2, KeyRound, Loader2, LogOut, ShieldCheck } from 'lucide-react'
// Import our own files
import { useAuth } from '../AuthContext'
import { changePassword } from '../api'
import { Field, inputClass } from '../components/Field'
import TwoStepCard from '../components/TwoStepCard'
import { initials } from '../format'

// The page where you see your account and change your password
export default function Account() {
  // Get the logged-in user and the logout function
  const { user, signOut } = useAuth()
  // What has been typed so far
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [again, setAgain] = useState('')
  // The error message, and whether the password was changed
  const [error, setError] = useState('')
  const [done, setDone] = useState(false)
  // True while we wait for the backend
  const [busy, setBusy] = useState(false)

  // Run when the form is sent
  async function handleSubmit(event) {
    // Stop the page from reloading
    event.preventDefault()
    // Clear any old error
    setError('')
    // The two new passwords must match
    if (next !== again) {
      setError('The two new passwords are not the same.')
      return
    }
    // Show the loading state
    setBusy(true)
    try {
      await changePassword({ current_password: current, new_password: next })
      // Success: explain, then sign out so the new password is used straight away
      setDone(true)
      setTimeout(signOut, 2000)
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
        <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-gold font-display text-lg font-bold text-forest-900">
          {initials(user.full_name)}
        </div>
        <div className="min-w-0">
          <p className="truncate font-display text-xl font-bold">{user.full_name}</p>
          <p className="truncate text-sm text-forest-200">{user.email}</p>
          <span className="mt-1 inline-block rounded-full bg-white/10 px-2.5 py-0.5 text-xs font-semibold">
            {user.role === 'owner' ? 'Owner' : user.role === 'admin' ? 'Admin' : 'Caretaker'}
          </span>
        </div>
      </motion.div>

      {/* Change password */}
      <div className="mt-5 rounded-3xl bg-paper p-6 shadow-sm">
        <h2 className="flex items-center gap-2 font-display text-lg font-bold text-forest-900">
          <KeyRound size={20} className="text-gold" /> Change your password
        </h2>

        {done ? (
          <div role="status" className="mt-4 flex items-start gap-3 rounded-2xl bg-forest-100 p-4 text-forest-700">
            <CheckCircle2 size={22} className="mt-0.5 shrink-0" />
            <p className="text-sm font-medium">Your password was changed. You are being signed out so you can sign in again with the new one.</p>
          </div>
        ) : (
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
            <button
              type="submit"
              disabled={busy}
              className="flex w-full items-center justify-center gap-2 rounded-xl bg-forest-900 py-3.5 font-semibold text-white hover:bg-forest-700 disabled:opacity-70"
            >
              {busy && <Loader2 size={18} className="animate-spin" />} Change password
            </button>
          </form>
        )}
      </div>

      {/* 2-step login */}
      <TwoStepCard />

      {/* A few safety tips */}
      <div className="mt-5 rounded-3xl bg-forest-100 p-6">
        <h2 className="flex items-center gap-2 font-display text-lg font-bold text-forest-900">
          <ShieldCheck size={20} className="text-forest-500" /> Keeping your account safe
        </h2>
        <ul className="mt-3 list-disc space-y-1.5 pl-5 text-sm text-forest-700">
          <li>Never share your password. Not even with people you trust at work.</li>
          <li>Changing your password signs you out of every device.</li>
          <li>After 5 wrong tries, sign-in is locked for 15 minutes.</li>
          <li>Log out when you use a phone or computer that is not yours.</li>
        </ul>
      </div>

      <button onClick={signOut} className="mt-5 flex w-full items-center justify-center gap-2 rounded-xl bg-paper py-3.5 font-semibold text-forest-700 shadow-sm hover:bg-forest-100">
        <LogOut size={18} /> Log out
      </button>
    </div>
  )
}