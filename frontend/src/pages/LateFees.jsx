// Import the React tools we need
import { useCallback, useEffect, useState } from 'react'
// Import the animation tool
import { motion } from 'framer-motion'
// Import the icons we use
import { CheckCircle2, Clock, Info, Loader2 } from 'lucide-react'
// Import our own files
import { applyLateFees, getLateFeeHistory, getLateFees, saveLateFeeSettings, waiveLateFee } from '../api'
import { Field, inputClass } from '../components/Field'
import { formatDate, money } from '../format'

// "2026-10" becomes "October 2026"
const monthLabel = (period) => {
  const [year, month] = period.split('-').map(Number)
  return new Date(year, month - 1, 1).toLocaleDateString('en-GB', { month: 'long', year: 'numeric' })
}
// A key that names one tenant's month
const keyOf = (item) => `${item.lease_id}|${item.period}`

// The page for late fees
export default function LateFees() {
  // What the server told us, and the state of the page
  const [preview, setPreview] = useState(null)
  const [history, setHistory] = useState([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState('')
  const [message, setMessage] = useState('')
  // The tenants the landlord has ticked
  const [selected, setSelected] = useState(new Set())
  // The rule being edited
  const [form, setForm] = useState({ enabled: false, grace_days: '5', kind: 'flat', amount: '500', start_period: '' })
  const [saved, setSaved] = useState(false)

  // Load the page
  const load = useCallback(async () => {
    setError('')
    try {
      const [fees, past] = await Promise.all([getLateFees(), getLateFeeHistory()])
      setPreview(fees)
      setHistory(past)
      const rule = fees.settings
      setForm({ enabled: rule.enabled, grace_days: String(rule.grace_days), kind: rule.kind, amount: String(rule.amount), start_period: rule.start_period || '' })
      setSelected(new Set(fees.candidates.map(keyOf)))
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])
  useEffect(() => {
    load()
  }, [load])

  // Save the rule
  async function saveRule() {
    setError('')
    setMessage('')
    setBusy('settings')
    try {
      await saveLateFeeSettings({
        enabled: form.enabled,
        grace_days: Number(form.grace_days),
        kind: form.kind,
        amount: Number(form.amount),
        start_period: form.start_period || null,
      })
      setSaved(true)
      setTimeout(() => setSaved(false), 3000)
      await load()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy('')
    }
  }

  // Tick or untick one tenant
  function toggle(item) {
    const next = new Set(selected)
    const key = keyOf(item)
    if (next.has(key)) next.delete(key)
    else next.add(key)
    setSelected(next)
  }

  // Add the ticked fees
  async function apply() {
    const chosen = preview.candidates.filter((item) => selected.has(keyOf(item)))
    const total = chosen.reduce((sum, item) => sum + item.fee, 0)
    if (chosen.length === 0) return
    if (!window.confirm(`Add ${chosen.length} late fee${chosen.length === 1 ? '' : 's'}, ${money(total)} in all, to your tenants' statements?`)) return
    setError('')
    setMessage('')
    setBusy('apply')
    try {
      const result = await applyLateFees(chosen.map((item) => ({ lease_id: item.lease_id, period: item.period })))
      setMessage(`${result.applied} late fee${result.applied === 1 ? '' : 's'} added (${money(result.total)})${result.skipped ? `. ${result.skipped} skipped because they changed.` : '.'}`)
      await load()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy('')
    }
  }

  // Waive one fee (before it is added, or after)
  async function waive(item, added) {
    const question = added ? `Take back this ${money(item.fee ?? item.amount)} fee for ${item.tenant_name}?` : `Waive the late fee for ${item.tenant_name}? They will not be charged for ${monthLabel(item.period)}.`
    if (!window.confirm(question)) return
    setError('')
    setMessage('')
    setBusy(`waive-${keyOf(item)}`)
    try {
      await waiveLateFee({ lease_id: item.lease_id, period: item.period })
      await load()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy('')
    }
  }

  // A sentence that shows the landlord what their rule means
  const example = (() => {
    const grace = Number(form.grace_days) || 0
    const amount = Number(form.amount) || 0
    const fee = form.kind === 'percent' ? Math.round((6000 * amount) / 100) : Math.round(amount)
    return `Example: rent of ${money(6000)} is not fully paid ${grace} day${grace === 1 ? '' : 's'} after its due date. A fee of ${money(fee)}${form.kind === 'percent' ? ` (${amount}% of the rent)` : ''} is added, once for that month.`
  })()

  const candidates = preview ? preview.candidates : []
  const chosen = candidates.filter((item) => selected.has(keyOf(item)))
  const chosenTotal = chosen.reduce((sum, item) => sum + item.fee, 0)

  return (
    <div className="mx-auto max-w-3xl">
      <div className="flex items-center gap-3">
        <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gold/25 text-forest-900">
          <Clock size={22} />
        </div>
        <div>
          <h1 className="text-3xl font-extrabold text-forest-900">Late fees</h1>
          <p className="text-muted">You decide who is charged. Nothing is added by itself.</p>
        </div>
      </div>

      <div className="mt-5 flex items-start gap-3 rounded-2xl bg-cream p-4 text-sm text-ink/80">
        <Info size={18} className="mt-0.5 shrink-0 text-forest-700" />
        <p>
          Only charge a late fee that <span className="font-semibold">your tenancy agreement allows</span>, and make sure your tenants know about it. A fee they never agreed to can be hard to collect.
        </p>
      </div>

      {error && (
        <div role="alert" className="mt-4 rounded-xl bg-terracotta/10 px-4 py-3 text-sm font-medium text-terracotta">
          {error}
        </div>
      )}
      {message && (
        <div role="status" className="mt-4 flex items-center gap-2 rounded-xl bg-forest-100 px-4 py-3 text-sm font-medium text-forest-700">
          <CheckCircle2 size={18} /> {message}
        </div>
      )}
      {loading && !preview && <div className="mt-5 h-48 animate-pulse rounded-3xl bg-forest-100" />}

      {preview && (
        <>
          {/* The rule */}
          <div className="mt-5 rounded-3xl bg-paper p-6 shadow-sm">
            <h2 className="font-display text-lg font-bold text-forest-900">The rule</h2>
            <button type="button" onClick={() => setForm({ ...form, enabled: !form.enabled })} className="mt-3 flex w-full items-center justify-between gap-3 rounded-xl bg-cream px-4 py-3 text-left">
              <span>
                <span className="block text-sm font-semibold text-forest-900">Charge late fees</span>
                <span className="block text-xs text-muted">{form.enabled ? 'On: late tenants will show up below.' : 'Off: nobody is charged.'}</span>
              </span>
              <span className={`relative h-6 w-11 shrink-0 rounded-full transition ${form.enabled ? 'bg-forest-500' : 'bg-forest-200'}`}>
                <span className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-all ${form.enabled ? 'left-[22px]' : 'left-0.5'}`} />
              </span>
            </button>

            {form.enabled && (
              <div className="mt-4 space-y-4">
                <div className="grid grid-cols-2 gap-3">
                  <Field label="Days after the due date" hint="Rent paid within these days has no fee.">
                    <input className={inputClass} type="number" min="0" max="30" step="1" inputMode="numeric" value={form.grace_days} onChange={(e) => setForm({ ...form, grace_days: e.target.value })} />
                  </Field>
                  <Field label="Type of fee">
                    <select className={inputClass} value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })}>
                      <option value="flat">A fixed amount (KSh)</option>
                      <option value="percent">A share of the month’s rent (%)</option>
                    </select>
                  </Field>
                  <Field label={form.kind === 'percent' ? 'Percentage' : 'Amount (KSh)'}>
                    <input className={inputClass} type="number" min="1" step={form.kind === 'percent' ? '0.5' : '1'} inputMode="decimal" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} />
                  </Field>
                  <Field label="Charge rent from" hint="Older months are never charged.">
                    <input className={inputClass} type="month" value={form.start_period} onChange={(e) => setForm({ ...form, start_period: e.target.value })} />
                  </Field>
                </div>
                <p className="rounded-xl bg-forest-100/60 px-4 py-3 text-sm text-forest-900">{example}</p>
              </div>
            )}
            <button onClick={saveRule} disabled={busy === 'settings'} className="mt-4 flex items-center gap-2 rounded-xl bg-forest-900 px-5 py-3 text-sm font-semibold text-white hover:bg-forest-700 disabled:opacity-70">
              {busy === 'settings' && <Loader2 size={16} className="animate-spin" />} Save the rule
            </button>
            {saved && (
              <p className="mt-2 flex items-center gap-1.5 text-sm font-medium text-forest-700">
                <CheckCircle2 size={16} /> Saved
              </p>
            )}
          </div>

          {/* Who is late */}
          {preview.settings.enabled && (
            <div className="mt-4 rounded-3xl bg-paper p-6 shadow-sm">
              <h2 className="font-display text-lg font-bold text-forest-900">Late now</h2>
              {candidates.length === 0 ? (
                <p className="mt-2 text-sm text-muted">Nobody is late under your rule. Good news.</p>
              ) : (
                <>
                  <p className="text-xs text-muted">Untick anyone you do not want to charge, or waive their fee for good.</p>
                  <ul className="mt-3 divide-y divide-forest-100">
                    {candidates.map((item) => {
                      const key = keyOf(item)
                      return (
                        <motion.li key={key} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="flex items-start gap-3 py-4">
                          <input type="checkbox" checked={selected.has(key)} onChange={() => toggle(item)} aria-label={`Charge ${item.tenant_name}`} className="mt-1 h-5 w-5 shrink-0 accent-forest-900" />
                          <div className="min-w-0 flex-1">
                            <p className="text-sm font-semibold text-forest-900">
                              {item.tenant_name} <span className="font-normal text-muted">· {item.unit_number}, {item.property_name}</span>
                            </p>
                            <p className="mt-0.5 text-xs text-muted">
                              {monthLabel(item.period)} rent of {money(item.rent_amount)} was due {formatDate(item.due_date)}. On {formatDate(item.deadline)}, {money(item.unpaid_at_deadline)} was still unpaid.
                            </p>
                            {item.still_owing === 0 && <p className="mt-1 text-xs font-semibold text-forest-700">It has been paid since, but after the deadline.</p>}
                          </div>
                          <div className="shrink-0 text-right">
                            <p className="text-sm font-bold text-forest-900">{money(item.fee)}</p>
                            <button onClick={() => waive(item, false)} disabled={busy === `waive-${key}`} className="mt-1 text-xs font-semibold text-muted hover:text-terracotta">
                              Waive
                            </button>
                          </div>
                        </motion.li>
                      )
                    })}
                  </ul>
                  <div className="mt-2 flex flex-wrap items-center justify-between gap-3 border-t border-forest-100 pt-4">
                    <div className="flex gap-3 text-xs font-semibold text-forest-700">
                      <button onClick={() => setSelected(new Set(candidates.map(keyOf)))}>Tick all</button>
                      <button onClick={() => setSelected(new Set())}>Untick all</button>
                    </div>
                    <button onClick={apply} disabled={chosen.length === 0 || busy === 'apply'} className="flex items-center gap-2 rounded-xl bg-forest-900 px-5 py-3 text-sm font-semibold text-white hover:bg-forest-700 disabled:opacity-50">
                      {busy === 'apply' && <Loader2 size={16} className="animate-spin" />}
                      {chosen.length === 0 ? 'Add late fees' : `Add ${chosen.length} fee${chosen.length === 1 ? '' : 's'} (${money(chosenTotal)})`}
                    </button>
                  </div>
                </>
              )}
            </div>
          )}

          {/* What was done before */}
          {history.length > 0 && (
            <div className="mt-4 rounded-3xl bg-paper p-6 shadow-sm">
              <h2 className="font-display text-lg font-bold text-forest-900">Recent</h2>
              <ul className="mt-3 divide-y divide-forest-100">
                {history.map((row) => (
                  <li key={`${row.lease_id}|${row.period}`} className="flex items-center justify-between gap-3 py-3">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold text-forest-900">
                        {row.tenant_name} <span className="font-normal text-muted">· {row.unit_number}, {row.property_name}</span>
                      </p>
                      <p className="text-xs text-muted">
                        {monthLabel(row.period)} · {row.action === 'applied' ? `Fee of ${money(row.amount)} added` : `Waived (${money(row.amount)})`} · {formatDate(row.created_at.slice(0, 10))}
                      </p>
                    </div>
                    {row.can_waive && (
                      <button onClick={() => waive({ ...row, fee: row.amount }, true)} disabled={busy === `waive-${row.lease_id}|${row.period}`} className="shrink-0 text-xs font-semibold text-muted hover:text-terracotta">
                        Take back
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
    </div>
  )
}