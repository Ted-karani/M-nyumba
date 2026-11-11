// Import the React tools we need
import { useEffect, useState } from 'react'
// Import the page-switching tool
import { Link } from 'react-router-dom'
// Import the animation tool
import { motion } from 'framer-motion'
// Import the icons we use
import { CheckCircle2, Circle, ListChecks, PartyPopper } from 'lucide-react'
// Import our own files
import { getGettingStarted } from '../api'

// One step of the list
function StepRow({ step }) {
  return (
    <li className="flex items-start gap-3 py-4">
      {step.done ? <CheckCircle2 size={22} className="mt-0.5 shrink-0 text-forest-500" /> : <Circle size={22} className="mt-0.5 shrink-0 text-forest-200" />}
      <div className="min-w-0 flex-1">
        <p className={`text-sm font-semibold ${step.done ? 'text-muted line-through' : 'text-forest-900'}`}>{step.title}</p>
        <p className="mt-0.5 text-xs text-muted">{step.description}</p>
      </div>
      {!step.done && (
        <Link to={step.link} className="shrink-0 rounded-xl bg-forest-900 px-4 py-2 text-xs font-semibold text-white hover:bg-forest-700">
          {step.action}
        </Link>
      )}
    </li>
  )
}

// The page with the whole checklist
export default function GettingStarted() {
  const [progress, setProgress] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    getGettingStarted()
      .then(setProgress)
      .catch((err) => setError(err.message))
  }, [])

  const percent = progress ? Math.round((progress.done_count / progress.total) * 100) : 0
  const core = progress ? progress.steps.filter((step) => step.core) : []
  const more = progress ? progress.steps.filter((step) => !step.core) : []

  return (
    <div className="mx-auto max-w-3xl">
      <div className="flex items-center gap-3">
        <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gold/25 text-forest-900">
          <ListChecks size={22} />
        </div>
        <div>
          <h1 className="text-3xl font-extrabold text-forest-900">Getting started</h1>
          <p className="text-muted">The steps that get EstateLoom working for you. They tick off by themselves.</p>
        </div>
      </div>

      {error && (
        <div role="alert" className="mt-5 rounded-xl bg-terracotta/10 px-4 py-3 text-sm font-medium text-terracotta">
          {error}
        </div>
      )}
      {!progress && !error && <div className="mt-5 h-48 animate-pulse rounded-3xl bg-forest-100" />}

      {progress && (
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
          <div className={`mt-5 rounded-3xl p-6 text-white shadow-xl ${progress.done_count === progress.total ? 'bg-forest-500' : 'bg-forest-900'}`}>
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="font-display text-3xl font-extrabold">
                  {progress.done_count} of {progress.total}
                </p>
                <p className="text-sm opacity-90">{progress.done_count === progress.total ? 'You are all set up.' : progress.core_done ? 'The basics are done. A few more things help.' : 'Start with the first three. They make everything else work.'}</p>
              </div>
              {progress.done_count === progress.total && <PartyPopper size={36} className="shrink-0 text-gold" />}
            </div>
            <div className="mt-4 h-2 overflow-hidden rounded-full bg-white/20">
              <motion.div className="h-full rounded-full bg-gold" initial={{ width: 0 }} animate={{ width: `${percent}%` }} transition={{ duration: 0.6 }} />
            </div>
          </div>

          <div className="mt-4 rounded-3xl bg-paper p-6 shadow-sm">
            <h2 className="font-display text-lg font-bold text-forest-900">To get started</h2>
            <ul className="mt-1 divide-y divide-forest-100">
              {core.map((step) => (
                <StepRow key={step.id} step={step} />
              ))}
            </ul>
          </div>

          <div className="mt-4 rounded-3xl bg-paper p-6 shadow-sm">
            <h2 className="font-display text-lg font-bold text-forest-900">Recommended</h2>
            <ul className="mt-1 divide-y divide-forest-100">
              {more.map((step) => (
                <StepRow key={step.id} step={step} />
              ))}
            </ul>
          </div>
        </motion.div>
      )}
    </div>
  )
}