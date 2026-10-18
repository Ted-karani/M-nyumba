// Import the React tool for remembering values
import { useState } from 'react'
// Import the animation tools
import { AnimatePresence, motion } from 'framer-motion'
// Import the icons we use
import { ArrowLeft, Building2, Eye, EyeOff, KeyRound, Loader2, ShieldCheck, BellRing, Wallet } from 'lucide-react'
// Import our login information
import { useAuth } from '../AuthContext'

// The look shared by every text box
const inputClass =
  'w-full rounded-xl border border-forest-200 bg-paper px-4 py-3 outline-none transition focus:border-forest-500 focus:ring-4 focus:ring-forest-100'

// A label with a text box under it
function Field({ label, children }) {
  return (
    <label className="block">
      <span className="mb-1 block text-sm font-medium">{label}</span>
      {children}
    </label>
  )
}

// The login and sign-up screen
export default function Login() {
  // Get the login functions
  const { signIn, signUp, completeOtp } = useAuth()
  // Which form is showing: "signin" or "signup"
  const [mode, setMode] = useState('signin')
  // Which step we are on: "password" or "code"
  const [step, setStep] = useState('password')
  // The short-lived pass we hold between the password and the code
  const [challenge, setChallenge] = useState('')
  // What the person has typed so far
  const [fullName, setFullName] = useState('')
  const [phone, setPhone] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [code, setCode] = useState('')
  // Whether the person wants to use a recovery code instead of the app's code
  const [useRecovery, setUseRecovery] = useState(false)
  // Whether the password is visible
  const [showPassword, setShowPassword] = useState(false)
  // The error message to show (empty means none)
  const [error, setError] = useState('')
  // True while we wait for the backend
  const [busy, setBusy] = useState(false)
  // A shortcut for "are we creating an account?"
  const isSignup = mode === 'signup'

  // Run when the password form is sent
  async function handleSubmit(event) {
    // Stop the page from reloading
    event.preventDefault()
    // Clear any old error and show the loading state
    setError('')
    setBusy(true)
    try {
      let result
      if (isSignup) {
        // Create the account (an empty phone is sent as nothing)
        result = await signUp({
          full_name: fullName.trim(),
          email: email.trim(),
          phone: phone.trim() || null,
          password,
        })
      } else {
        // Log in
        result = await signIn(email.trim(), password)
      }
      // If a code is needed, move to the code step
      if (result && result.requiresOtp) {
        setChallenge(result.challenge)
        setCode('')
        setUseRecovery(false)
        setStep('code')
      }
    } catch (err) {
      // Show the error under the form
      setError(err.message)
    } finally {
      // Stop the loading state
      setBusy(false)
    }
  }

  // Run when the code form is sent
  async function handleCode(event) {
    // Stop the page from reloading
    event.preventDefault()
    // Clear any old error and show the loading state
    setError('')
    setBusy(true)
    try {
      await completeOtp(challenge, code.trim())
    } catch (err) {
      // Show the error under the form
      setError(err.message)
    } finally {
      // Stop the loading state
      setBusy(false)
    }
  }

  // Go back to the password step
  function backToPassword() {
    setStep('password')
    setChallenge('')
    setCode('')
    setError('')
  }

  // Switch between the two forms
  function switchMode() {
    setMode(isSignup ? 'signin' : 'signup')
    setError('')
  }

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-2">
      {/* The green brand panel: a header on phones, a side panel on desktop */}
      <div className="relative overflow-hidden rounded-b-[2.5rem] bg-forest-900 px-8 pb-12 pt-12 text-white lg:flex lg:flex-col lg:justify-between lg:rounded-none lg:p-16">
        {/* Soft decorative circles */}
        <div className="absolute -right-20 -top-20 h-72 w-72 rounded-full bg-forest-700/40" />
        <div className="absolute -bottom-24 -left-16 h-64 w-64 rounded-full bg-gold/10" />

        {/* The logo and name */}
        <motion.div
          initial={{ opacity: 0, y: -12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="relative flex items-center gap-3"
        >
          <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-gold text-forest-900">
            <Building2 size={22} />
          </div>
          <span className="font-display text-2xl font-bold">M-nyumba</span>
        </motion.div>

        {/* The headline and selling points */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.1 }}
          className="relative mt-10 lg:mt-0"
        >
          <h1 className="font-display text-3xl font-extrabold leading-tight lg:text-5xl">
            Every house.
            <br />
            Every payment.
            <br />
            <span className="text-gold">One place.</span>
          </h1>
          <p className="mt-4 max-w-md text-forest-200">
            Know who has paid, what is vacant, and who is late, without the notebook.
          </p>
          {/* These three only show on big screens */}
          <ul className="mt-8 hidden space-y-4 text-forest-100 lg:block">
            <li className="flex items-center gap-3">
              <Wallet size={20} className="text-gold" /> Track rent, deposits and balances
            </li>
            <li className="flex items-center gap-3">
              <BellRing size={20} className="text-gold" /> See overdue tenants instantly
            </li>
            <li className="flex items-center gap-3">
              <ShieldCheck size={20} className="text-gold" /> Your data stays private to you
            </li>
          </ul>
        </motion.div>

        {/* A small footer line (desktop only) */}
        <p className="relative hidden text-sm text-forest-200/70 lg:block">Built for landlords in Kenya</p>
      </div>

      {/* The form side */}
      <div className="flex items-center justify-center px-6 py-10">
        {step === 'code' ? (
          // The second step: the 6-digit code
          <motion.div initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }} className="w-full max-w-sm">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-forest-100 text-forest-700">
              <KeyRound size={26} />
            </div>
            <h2 className="mt-5 text-3xl font-bold text-forest-900">Enter your code</h2>
            <p className="mt-1 text-muted">
              {useRecovery
                ? 'Type one of your recovery codes. Each one works only once.'
                : 'Open your authenticator app and type the 6-digit code for M-nyumba.'}
            </p>

            <form onSubmit={handleCode} className="mt-8 space-y-4">
              <Field label={useRecovery ? 'Recovery code' : '6-digit code'}>
                <input
                  className={`${inputClass} text-center font-mono text-xl tracking-widest`}
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  inputMode={useRecovery ? 'text' : 'numeric'}
                  autoComplete="one-time-code"
                  maxLength={useRecovery ? 20 : 7}
                  placeholder={useRecovery ? 'a1b2c3-d4e5f6' : '123456'}
                  autoFocus
                  required
                />
              </Field>

              {/* The error message fades in when something goes wrong */}
              <AnimatePresence>
                {error && (
                  <motion.div
                    initial={{ opacity: 0, y: -6 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0 }}
                    role="alert"
                    className="rounded-xl bg-terracotta/10 px-4 py-3 text-sm font-medium text-terracotta"
                  >
                    {error}
                  </motion.div>
                )}
              </AnimatePresence>

              <motion.button
                whileTap={{ scale: 0.98 }}
                type="submit"
                disabled={busy}
                className="flex w-full items-center justify-center gap-2 rounded-xl bg-forest-900 py-3.5 font-semibold text-white shadow-lg shadow-forest-900/20 transition hover:bg-forest-700 disabled:opacity-70"
              >
                {busy && <Loader2 size={18} className="animate-spin" />}
                Sign in
              </motion.button>
            </form>

            <div className="mt-6 flex flex-col items-center gap-3 text-sm">
              <button
                type="button"
                onClick={() => {
                  setUseRecovery(!useRecovery)
                  setCode('')
                  setError('')
                }}
                className="font-semibold text-forest-700 hover:underline"
              >
                {useRecovery ? 'Use the code from my app' : 'I lost my phone: use a recovery code'}
              </button>
              <button type="button" onClick={backToPassword} className="flex items-center gap-1 text-muted hover:text-forest-900">
                <ArrowLeft size={14} /> Back to sign in
              </button>
            </div>
          </motion.div>
        ) : (
          // The first step: email and password
          <motion.div initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, delay: 0.2 }} className="w-full max-w-sm">
            <h2 className="text-3xl font-bold text-forest-900">{isSignup ? 'Create your account' : 'Welcome back'}</h2>
            <p className="mt-1 text-muted">{isSignup ? 'Start managing your properties.' : 'Sign in to see your properties.'}</p>

            <form onSubmit={handleSubmit} className="mt-8 space-y-4">
              {/* The name and phone boxes slide in only when signing up */}
              <AnimatePresence initial={false}>
                {isSignup && (
                  <motion.div
                    key="signup-fields"
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    exit={{ opacity: 0, height: 0 }}
                    transition={{ duration: 0.3 }}
                    className="space-y-4 overflow-hidden"
                  >
                    <Field label="Full name">
                      <input
                        className={inputClass}
                        value={fullName}
                        onChange={(e) => setFullName(e.target.value)}
                        placeholder="Jane Wanjiru"
                        required={isSignup}
                        minLength={2}
                        autoComplete="name"
                      />
                    </Field>
                    <Field label="Phone (optional)">
                      <input
                        className={inputClass}
                        value={phone}
                        onChange={(e) => setPhone(e.target.value)}
                        placeholder="0712 345 678"
                        inputMode="tel"
                        autoComplete="tel"
                      />
                    </Field>
                  </motion.div>
                )}
              </AnimatePresence>

              <Field label="Email">
                <input
                  className={inputClass}
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  required
                  autoComplete="email"
                />
              </Field>

              <Field label="Password">
                <div className="relative">
                  <input
                    className={`${inputClass} pr-12`}
                    type={showPassword ? 'text' : 'password'}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder={isSignup ? 'At least 8 characters' : 'Your password'}
                    required
                    minLength={isSignup ? 8 : undefined}
                    autoComplete={isSignup ? 'new-password' : 'current-password'}
                  />
                  {/* The little eye that shows or hides the password */}
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted hover:text-forest-700"
                    aria-label={showPassword ? 'Hide password' : 'Show password'}
                  >
                    {showPassword ? <EyeOff size={20} /> : <Eye size={20} />}
                  </button>
                </div>
              </Field>

              {/* The error message fades in when something goes wrong */}
              <AnimatePresence>
                {error && (
                  <motion.div
                    initial={{ opacity: 0, y: -6 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0 }}
                    role="alert"
                    className="rounded-xl bg-terracotta/10 px-4 py-3 text-sm font-medium text-terracotta"
                  >
                    {error}
                  </motion.div>
                )}
              </AnimatePresence>

              {/* The main button */}
              <motion.button
                whileTap={{ scale: 0.98 }}
                type="submit"
                disabled={busy}
                className="flex w-full items-center justify-center gap-2 rounded-xl bg-forest-900 py-3.5 font-semibold text-white shadow-lg shadow-forest-900/20 transition hover:bg-forest-700 disabled:opacity-70"
              >
                {busy && <Loader2 size={18} className="animate-spin" />}
                {isSignup ? 'Create account' : 'Sign in'}
              </motion.button>
            </form>

            {/* The link that switches between the two forms */}
            <p className="mt-6 text-center text-sm text-muted">
              {isSignup ? 'Already have an account?' : 'New to M-nyumba?'}{' '}
              <button type="button" onClick={switchMode} className="font-semibold text-forest-700 hover:underline">
                {isSignup ? 'Sign in' : 'Create an account'}
              </button>
            </p>
          </motion.div>
        )}
      </div>
    </div>
  )
}