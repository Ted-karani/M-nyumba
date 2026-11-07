// Import the React tools we need
import { useCallback, useEffect, useState } from 'react'
// Import the animation tool
import { motion } from 'framer-motion'
// Import the icons we use
import { AlertTriangle, CheckCircle2, ChevronLeft, ChevronRight, Download, Info, Landmark, Loader2 } from 'lucide-react'
// Import our own files
import { deleteTaxFiling, downloadTaxSchedule, getTaxOverview, saveTaxFiling, saveTaxSettings } from '../api'
import { Field, inputClass } from '../components/Field'
import Modal from '../components/Modal'
import { formatDate, money } from '../format'

// Small date helpers for months written like "2026-10"
const pad = (number) => String(number).padStart(2, '0')
const thisMonth = () => {
  const now = new Date()
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}`
}
const shift = (period, months) => {
  const [year, month] = period.split('-').map(Number)
  const index = year * 12 + (month - 1) + months
  return `${Math.floor(index / 12)}-${pad((index % 12) + 1)}`
}
const monthName = (period, style = 'long') => {
  const [year, month] = period.split('-').map(Number)
  return new Date(year, month - 1, 1).toLocaleDateString('en-GB', style === 'long' ? { month: 'long', year: 'numeric' } : { month: 'short' })
}

// What each state of a month looks like at the top of the page
const STATES = {
  filed: { tone: 'bg-forest-500', label: 'Filed and paid' },
  due: { tone: 'bg-forest-900', label: 'Tax to pay' },
  overdue: { tone: 'bg-terracotta', label: 'Overdue: tax to pay' },
  upcoming: { tone: 'bg-forest-700', label: 'So far this month' },
  nil: { tone: 'bg-forest-900', label: 'Nothing received' },
  not_applicable: { tone: 'bg-forest-700', label: 'Not for non-residents' },
}

// A row in the "how we got this number" card
function Line({ label, value, strong, note }) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-2">
      <div>
        <p className={`text-sm ${strong ? 'font-bold text-forest-900' : 'text-ink/80'}`}>{label}</p>
        {note && <p className="text-xs text-muted">{note}</p>}
      </div>
      <p className={`shrink-0 text-sm ${strong ? 'font-bold text-forest-900' : 'text-ink/80'}`}>{value}</p>
    </div>
  )
}

// The page for the monthly rental income tax
export default function RentTax() {
  // The month on screen, what the server told us, and any error
  const [period, setPeriod] = useState(shift(thisMonth(), -1))
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  // The "mark as filed" window and its form
  const [filing, setFiling] = useState(false)
  const [form, setForm] = useState({ amount: '', date: '', reference: '', note: '' })
  const [busy, setBusy] = useState('')
  // The settings form
  const [resident, setResident] = useState(true)
  const [rate, setRate] = useState('7.5')
  const [saved, setSaved] = useState(false)

  // Load a month
  const load = useCallback(() => {
    setLoading(true)
    setError('')
    getTaxOverview(period)
      .then((result) => {
        setData(result)
        setResident(result.settings.resident)
        setRate(String(result.settings.rate_percent))
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [period])
  useEffect(() => {
    load()
  }, [load])

  // The building settings as the server wants them
  const treatmentsWith = (propertyId, value) => {
    const map = {}
    data.month.properties.forEach((line) => {
      if (line.setting !== 'auto') map[line.property_id] = line.setting
    })
    if (value === 'auto') delete map[propertyId]
    else map[propertyId] = value
    return map
  }

  // Save the settings (and reload the month)
  async function saveSettings(nextTreatments) {
    setError('')
    setBusy('settings')
    try {
      await saveTaxSettings({ resident, rate_percent: Number(rate), treatments: nextTreatments })
      setSaved(true)
      setTimeout(() => setSaved(false), 3000)
      load()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy('')
    }
  }

  // Open the "mark as filed" window with sensible starting values
  function openFiling() {
    const existing = data.month.filing
    setForm({
      amount: String(existing ? existing.amount_paid : data.month.tax_due),
      date: existing ? existing.paid_on : new Date().toISOString().slice(0, 10),
      reference: existing?.reference || '',
      note: existing?.note || '',
    })
    setFiling(true)
  }

  // Save the filing
  async function submitFiling(event) {
    event.preventDefault()
    setError('')
    setBusy('filing')
    try {
      await saveTaxFiling(period, { amount_paid: Number(form.amount), paid_on: form.date, reference: form.reference.trim() || null, note: form.note.trim() || null })
      setFiling(false)
      load()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy('')
    }
  }

  // Take back the filed mark
  async function undoFiling() {
    if (!window.confirm('Remove the record that this month was filed?')) return
    setBusy('undo')
    try {
      await deleteTaxFiling(period)
      load()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy('')
    }
  }

  // Download the Excel file
  async function handleDownload() {
    setBusy('download')
    setError('')
    try {
      await downloadTaxSchedule(period)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy('')
    }
  }

  const month = data?.month
  const year = data?.year
  const state = month ? STATES[month.state] : null
  const atCurrent = period >= thisMonth()
  const biggest = year ? Math.max(1, ...year.months.map((item) => item.gross_rent)) : 1

  return (
    <div className="mx-auto max-w-3xl">
      <div className="flex items-center gap-3">
        <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gold/25 text-forest-900">
          <Landmark size={22} />
        </div>
        <div>
          <h1 className="text-3xl font-extrabold text-forest-900">Rental income tax</h1>
          <p className="text-muted">The monthly tax on rent from homes, worked out from your payments.</p>
        </div>
      </div>

      {/* The honest warning, always visible */}
      <div className="mt-5 flex items-start gap-3 rounded-2xl bg-cream p-4 text-sm text-ink/80">
        <Info size={18} className="mt-0.5 shrink-0 text-forest-700" />
        <p>
          This is an <span className="font-semibold">estimate to help you</span>, not tax advice. KRA’s rules can change, so check the rate and your figures with KRA or an accountant before you file.
        </p>
      </div>

      {/* The month picker */}
      <div className="mt-5 flex items-center justify-between rounded-2xl bg-paper p-2 shadow-sm">
        <button onClick={() => setPeriod(shift(period, -1))} aria-label="Earlier month" className="rounded-xl p-3 text-forest-700 hover:bg-forest-100">
          <ChevronLeft size={20} />
        </button>
        <p className="font-display text-lg font-bold text-forest-900">Rent received in {monthName(period)}</p>
        <button onClick={() => setPeriod(shift(period, 1))} disabled={atCurrent} aria-label="Later month" className="rounded-xl p-3 text-forest-700 hover:bg-forest-100 disabled:opacity-30">
          <ChevronRight size={20} />
        </button>
      </div>

      {error && (
        <div role="alert" className="mt-4 rounded-xl bg-terracotta/10 px-4 py-3 text-sm font-medium text-terracotta">
          {error}
        </div>
      )}
      {loading && !data && <div className="mt-5 h-48 animate-pulse rounded-3xl bg-forest-100" />}

      {month && (
        <motion.div key={period} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
          {/* The big number */}
          <div className={`mt-5 rounded-3xl p-6 text-white shadow-xl ${state.tone}`}>
            <p className="text-sm font-semibold opacity-90">{state.label}</p>
            {month.state === 'nil' || month.state === 'not_applicable' ? (
              <p className="mt-1 font-display text-3xl font-extrabold">{month.state === 'nil' ? 'KSh 0' : 'Does not apply'}</p>
            ) : (
              <p className="mt-1 font-display text-5xl font-extrabold">{money(month.state === 'filed' ? month.filing.amount_paid : month.tax_due)}</p>
            )}
            <p className="mt-2 text-sm opacity-90">
              {month.state === 'filed' && `Paid on ${formatDate(month.filing.paid_on)}${month.filing.reference ? ` · reference ${month.filing.reference}` : ''}`}
              {month.state === 'due' && `Due by ${formatDate(month.due_date)} · ${month.days_left} day${month.days_left === 1 ? '' : 's'} left`}
              {month.state === 'overdue' && `Was due on ${formatDate(month.due_date)} · ${Math.abs(month.days_left)} day${Math.abs(month.days_left) === 1 ? '' : 's'} ago`}
              {month.state === 'upcoming' && `This month is not over, so this can still change. It will be due by ${formatDate(month.due_date)}.`}
              {month.state === 'nil' && `You may still need to file a nil return by ${formatDate(month.due_date)}. Ask KRA or your accountant.`}
              {month.state === 'not_applicable' && 'This simple tax is for Kenyan residents. Non-resident landlords file differently: ask KRA or an accountant.'}
            </p>
            <div className="mt-5 flex flex-wrap gap-2">
              {month.state !== 'upcoming' && month.state !== 'not_applicable' && month.state !== 'filed' && (
                <button onClick={openFiling} className="rounded-xl bg-white px-4 py-2.5 text-sm font-semibold text-forest-900 hover:bg-cream">
                  Mark as filed
                </button>
              )}
              {month.state === 'filed' && (
                <>
                  <button onClick={openFiling} className="rounded-xl bg-white/20 px-4 py-2.5 text-sm font-semibold hover:bg-white/30">
                    Change details
                  </button>
                  <button onClick={undoFiling} disabled={busy === 'undo'} className="rounded-xl bg-white/20 px-4 py-2.5 text-sm font-semibold hover:bg-white/30">
                    Undo
                  </button>
                </>
              )}
              <button onClick={handleDownload} disabled={busy === 'download'} className="flex items-center gap-2 rounded-xl bg-white/20 px-4 py-2.5 text-sm font-semibold hover:bg-white/30">
                {busy === 'download' ? <Loader2 size={16} className="animate-spin" /> : <Download size={16} />} Excel for my accountant
              </button>
            </div>
          </div>

          {/* How we got the number */}
          {month.state !== 'not_applicable' && (
            <div className="mt-4 rounded-3xl bg-paper p-6 shadow-sm">
              <h2 className="font-display text-lg font-bold text-forest-900">How we got this number</h2>
              <div className="mt-2 divide-y divide-forest-100">
                <Line label="Rent received" value={money(month.rent)} note="From homes, in this month" />
                {month.arrears > 0 && <Line label="Old balances collected" value={money(month.arrears)} note="Rent from before EstateLoom, paid now" />}
                {month.advance > 0 && <Line label="Paid in advance" value={money(month.advance)} note="More than was owed yet, counted as rent received" />}
                <Line label="Gross rent" value={money(month.gross_rent)} strong />
                <Line label={`Tax at ${month.rate_percent}%`} value={money(month.tax_due)} strong />
              </div>
              {(month.deposits > 0 || month.bills > 0 || month.commercial > 0) && (
                <div className="mt-4 rounded-2xl bg-cream p-4">
                  <p className="text-sm font-semibold text-forest-900">Money received but left out</p>
                  <div className="mt-1 divide-y divide-forest-100/70">
                    {month.deposits > 0 && <Line label="Deposits" value={money(month.deposits)} note="A deposit is not rent" />}
                    {month.bills > 0 && <Line label="Water, electricity, Wi-Fi and other charges" value={money(month.bills)} />}
                    {month.commercial > 0 && <Line label="Shops and other commercial units" value={money(month.commercial)} note="Not part of this tax" />}
                  </div>
                </div>
              )}
              <p className="mt-4 text-xs text-muted">
                Each payment is applied to what the tenant owed longest first, and only the part that paid rent counts. You billed {money(month.rent_billed)} in rent for homes this month.
              </p>
            </div>
          )}

          {/* The buildings */}
          {month.properties.length > 0 && (
            <div className="mt-4 rounded-3xl bg-paper p-6 shadow-sm">
              <h2 className="font-display text-lg font-bold text-forest-900">Your buildings</h2>
              <p className="text-xs text-muted">We treat units called shop, office, store and similar as commercial. You can change a whole building.</p>
              <ul className="mt-3 divide-y divide-forest-100">
                {month.properties.map((line) => (
                  <li key={line.property_id} className="py-3">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-semibold text-forest-900">{line.name}</p>
                        <p className="text-xs text-muted">
                          {line.residential_units} home{line.residential_units === 1 ? '' : 's'}
                          {line.commercial_units > 0 ? `, ${line.commercial_units} commercial` : ''}
                        </p>
                      </div>
                      <p className="shrink-0 text-sm font-semibold text-forest-900">{money(line.gross_rent)}</p>
                    </div>
                    <select
                      value={line.setting}
                      onChange={(e) => saveSettings(treatmentsWith(line.property_id, e.target.value))}
                      disabled={busy === 'settings'}
                      aria-label={`How to treat ${line.name}`}
                      className={`${inputClass} mt-2 py-2 text-sm`}
                    >
                      <option value="auto">Automatic (shops count as commercial)</option>
                      <option value="residential">All homes</option>
                      <option value="commercial">All commercial (not taxed here)</option>
                    </select>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* The year */}
          <div className="mt-4 rounded-3xl bg-paper p-6 shadow-sm">
            <h2 className="font-display text-lg font-bold text-forest-900">The last 12 months</h2>
            <p className="font-display text-2xl font-extrabold text-forest-900">{money(year.total)}</p>
            <p className="text-sm text-muted">
              {year.status === 'below' && `Below the ${money(data.settings.threshold_low)} a year line. This simple tax may not apply to you. Check with KRA.`}
              {year.status === 'in_band' && `Between ${money(data.settings.threshold_low)} and ${money(data.settings.threshold_high)} a year: this is the range this simple tax is meant for.`}
              {year.status === 'above' && `Above ${money(data.settings.threshold_high)} a year. Rent over this is declared in the yearly income tax return instead. Ask an accountant.`}
            </p>
            <div className="mt-4 flex h-24 items-end gap-1.5">
              {year.months.map((item) => (
                <button key={item.period} onClick={() => setPeriod(item.period)} className="group flex h-full flex-1 flex-col items-center justify-end gap-1" aria-label={monthName(item.period)}>
                  <span
                    className={`w-full rounded-t-md transition ${item.period === period ? 'ring-2 ring-forest-900' : ''} ${
                      item.state === 'filed' ? 'bg-forest-500' : item.state === 'overdue' ? 'bg-terracotta' : item.state === 'due' ? 'bg-gold' : 'bg-forest-200'
                    }`}
                    style={{ height: `${Math.max(4, (item.gross_rent / biggest) * 100)}%` }}
                  />
                  <span className="text-[9px] text-muted">{monthName(item.period, 'short')}</span>
                </button>
              ))}
            </div>
            <p className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-muted">
              <span>Green: filed</span>
              <span>Gold: to pay</span>
              <span>Red: overdue</span>
              <span>Grey: nothing to do yet</span>
            </p>
            <p className="mt-2 text-xs text-muted">Counted only from the payments recorded in EstateLoom.</p>
          </div>

          {/* The settings */}
          <div className="mt-4 rounded-3xl bg-paper p-6 shadow-sm">
            <h2 className="font-display text-lg font-bold text-forest-900">Settings</h2>
            <button type="button" onClick={() => setResident(!resident)} className="mt-3 flex w-full items-center justify-between gap-3 rounded-xl bg-cream px-4 py-3 text-left">
              <span>
                <span className="block text-sm font-semibold text-forest-900">I am a Kenyan tax resident</span>
                <span className="block text-xs text-muted">This simple tax is only for residents.</span>
              </span>
              <span className={`relative h-6 w-11 shrink-0 rounded-full transition ${resident ? 'bg-forest-500' : 'bg-forest-200'}`}>
                <span className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-all ${resident ? 'left-[22px]' : 'left-0.5'}`} />
              </span>
            </button>
            <div className="mt-3">
              <Field label="Tax rate (%)" hint={`KRA’s published rate is ${data.settings.default_rate}%. Change it only if KRA changes it.`}>
                <input className={inputClass} type="number" min="0.1" max="30" step="0.1" value={rate} onChange={(e) => setRate(e.target.value)} />
              </Field>
            </div>
            <button
              onClick={() =>
                saveSettings(
                  Object.fromEntries(month.properties.filter((line) => line.setting !== 'auto').map((line) => [line.property_id, line.setting]))
                )
              }
              disabled={busy === 'settings'}
              className="mt-3 flex items-center gap-2 rounded-xl bg-forest-900 px-5 py-3 text-sm font-semibold text-white hover:bg-forest-700 disabled:opacity-70"
            >
              {busy === 'settings' && <Loader2 size={16} className="animate-spin" />} Save settings
            </button>
            {saved && (
              <p className="mt-2 flex items-center gap-1.5 text-sm font-medium text-forest-700">
                <CheckCircle2 size={16} /> Saved
              </p>
            )}
          </div>

          {/* A guide for the first time */}
          <details className="mt-4 rounded-3xl bg-paper p-6 shadow-sm">
            <summary className="cursor-pointer font-display text-lg font-bold text-forest-900">Filing for the first time?</summary>
            <ol className="mt-3 list-decimal space-y-2 pl-5 text-sm text-ink/80">
              <li>Take the gross rent for the month from this page.</li>
              <li>Sign in to KRA’s online system (iTax, or eRITS if KRA has moved your account to it) and open the monthly rental income return.</li>
              <li>Enter the gross rent. Check that the tax KRA calculates matches the tax shown here.</li>
              <li>Pay by the 20th of the following month, using the payment details KRA gives you for the return. Keep the receipt.</li>
              <li>Come back here, press “Mark as filed”, and add the reference.</li>
            </ol>
            <p className="mt-3 text-xs text-muted">If you receive no rent in a month, you may still need to file a nil return. Ask KRA or your accountant. The tax on rent from homes has no deductions for repairs or expenses.</p>
          </details>
        </motion.div>
      )}

      {/* The "mark as filed" window */}
      <Modal open={filing} title={`Filed: ${monthName(period)}`} onClose={() => setFiling(false)}>
        <form onSubmit={submitFiling} className="space-y-4">
          <Field label="Amount you paid KRA (KSh)">
            <input className={inputClass} type="number" min="0" step="1" inputMode="numeric" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} required />
          </Field>
          <Field label="Date you paid">
            <input className={inputClass} type="date" max={new Date().toISOString().slice(0, 10)} value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} required />
          </Field>
          <Field label="KRA reference or receipt (optional)">
            <input className={inputClass} value={form.reference} onChange={(e) => setForm({ ...form, reference: e.target.value })} maxLength={40} />
          </Field>
          <Field label="Note (optional)">
            <input className={inputClass} value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} maxLength={200} />
          </Field>
          {error && (
            <div role="alert" className="flex items-start gap-2 rounded-xl bg-terracotta/10 px-4 py-3 text-sm font-medium text-terracotta">
              <AlertTriangle size={16} className="mt-0.5 shrink-0" /> {error}
            </div>
          )}
          <button type="submit" disabled={busy === 'filing'} className="flex w-full items-center justify-center gap-2 rounded-xl bg-forest-900 py-3.5 font-semibold text-white hover:bg-forest-700 disabled:opacity-70">
            {busy === 'filing' && <Loader2 size={18} className="animate-spin" />} Save
          </button>
        </form>
      </Modal>
    </div>
  )
}