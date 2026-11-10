// Import the React tools we need
import { useRef, useState } from 'react'
// Import the page-switching tool
import { Link } from 'react-router-dom'
// Import the animation tool
import { motion } from 'framer-motion'
// Import the icons we use
import { AlertTriangle, ArrowLeft, CheckCircle2, FileSearch, Info, Loader2, Upload } from 'lucide-react'
// Import our own files
import { analyzeStatement, previewStatement, recordFromStatement } from '../api'
import { inputClass } from '../components/Field'
import { formatDate, money } from '../format'

// The things we need from the statement: [name, what to call it, is it needed]
const FIELDS = [
  ['receipt', 'M-Pesa code (Receipt No.)', true],
  ['date', 'Date and time', true],
  ['amount_in', 'Money received (Paid In)', true],
  ['status', 'Status', false],
  ['details', 'Details', false],
  ['party', 'Who paid (Other Party)', false],
  ['account', 'Account number the tenant typed', false],
  ['amount_out', 'Money paid out (Withdrawn)', false],
  ['linked', 'Linked transaction', false],
]

// A card with a title, a count, and a few words about what to do
function Group({ tone, title, count, children, help }) {
  return (
    <div className="mt-4 rounded-3xl bg-paper p-6 shadow-sm">
      <div className="flex items-center justify-between gap-3">
        <h2 className="font-display text-lg font-bold text-forest-900">{title}</h2>
        <span className={`rounded-full px-3 py-1 text-xs font-bold ${tone}`}>{count}</span>
      </div>
      <p className="mt-1 text-xs text-muted">{help}</p>
      <div className="mt-3">{children}</div>
    </div>
  )
}

// One payment of EstateLoom, with a link to the tenant
function PaymentLine({ row, extra }) {
  return (
    <li className="flex items-start justify-between gap-3 py-3">
      <div className="min-w-0">
        <Link to={`/tenants/${row.tenant_id}`} className="block truncate text-sm font-semibold text-forest-900 hover:underline">
          {row.tenant_name} <span className="font-normal text-muted">· {row.unit_number}, {row.property_name}</span>
        </Link>
        <p className="font-mono text-xs text-muted">
          {row.receipt} · {formatDate(row.paid_on)}
        </p>
        {extra && <p className="mt-1 text-xs text-terracotta">{extra}</p>}
      </div>
      <p className="shrink-0 text-sm font-bold text-forest-900">{money(row.amount)}</p>
    </li>
  )
}

// The page that checks an M-Pesa statement against the payments in EstateLoom
export default function Reconcile() {
  // Where we are: "upload", "columns" or "results"
  const [step, setStep] = useState('upload')
  const [file, setFile] = useState(null)
  // What we learned about the file, and the columns chosen
  const [preview, setPreview] = useState(null)
  const [mapping, setMapping] = useState({})
  // The result of the check, and what is chosen to record
  const [result, setResult] = useState(null)
  const [choice, setChoice] = useState({})
  const [ticked, setTicked] = useState(new Set())
  // The state of the page
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const picker = useRef(null)

  // The columns as the server wants them
  const payload = () => ({
    header_row: preview.header_row,
    ...Object.fromEntries(FIELDS.map(([key]) => [key, mapping[key] === '' || mapping[key] === undefined ? null : Number(mapping[key])])),
  })

  // Run an action, show its error, and stop the busy state
  async function run(name, action) {
    setError('')
    setBusy(name)
    try {
      await action()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy('')
    }
  }

  // A file was chosen: look at it
  async function handleFile(event) {
    const chosen = event.target.files[0]
    event.target.value = ''
    if (!chosen) return
    setMessage('')
    await run('preview', async () => {
      const shown = await previewStatement(chosen)
      setFile(chosen)
      setPreview(shown)
      setMapping(Object.fromEntries(Object.entries(shown.suggested).map(([key, value]) => [key, value === null ? '' : String(value)])))
      setStep('columns')
    })
  }

  // Compare the statement with EstateLoom
  const check = () =>
    run('check', async () => {
      const found = await analyzeStatement(file, payload())
      setResult(found)
      setChoice(Object.fromEntries(found.missing.filter((row) => row.suggested_lease_id).map((row) => [row.receipt, String(row.suggested_lease_id)])))
      setTicked(new Set(found.missing.filter((row) => row.suggested_lease_id).map((row) => row.receipt)))
      setStep('results')
    })

  // Record the ticked payments, then check again
  async function record() {
    const assignments = result.missing.filter((row) => ticked.has(row.receipt) && choice[row.receipt]).map((row) => ({ receipt: row.receipt, lease_id: Number(choice[row.receipt]) }))
    if (assignments.length === 0) return
    await run('record', async () => {
      const done = await recordFromStatement(file, payload(), assignments)
      setMessage(`${done.recorded} payment${done.recorded === 1 ? '' : 's'} recorded.${done.skipped ? ` ${done.skipped} skipped: ${done.problems.join('; ')}` : ''}`)
      const found = await analyzeStatement(file, payload())
      setResult(found)
      setChoice(Object.fromEntries(found.missing.filter((row) => row.suggested_lease_id).map((row) => [row.receipt, String(row.suggested_lease_id)])))
      setTicked(new Set(found.missing.filter((row) => row.suggested_lease_id).map((row) => row.receipt)))
    })
  }

  // Start again with another file
  function reset() {
    setStep('upload')
    setFile(null)
    setPreview(null)
    setResult(null)
    setMessage('')
    setError('')
  }

  const ready = FIELDS.filter(([, , needed]) => needed).every(([key]) => mapping[key] !== '' && mapping[key] !== undefined)
  const summary = result?.summary
  const nothingWrong = result && result.missing.length + result.mismatched.length + result.reversed.length + result.not_in_statement.length === 0

  return (
    <div className="mx-auto max-w-3xl">
      <div className="flex items-center gap-3">
        <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gold/25 text-forest-900">
          <FileSearch size={22} />
        </div>
        <div>
          <h1 className="text-3xl font-extrabold text-forest-900">M-Pesa statement check</h1>
          <p className="text-muted">Compare your Paybill statement with the payments you have recorded.</p>
        </div>
      </div>

      <div className="mt-5 flex items-start gap-3 rounded-2xl bg-cream p-4 text-sm text-ink/80">
        <Info size={18} className="mt-0.5 shrink-0 text-forest-700" />
        <p>
          Your file is read here to compare it, and <span className="font-semibold">it is not saved</span>. Nothing is changed unless you press “Record”. Reversals are found by their wording, so always check anything marked below against your M-Pesa statement.
        </p>
      </div>

      {error && (
        <div role="alert" className="mt-4 flex items-start gap-2 rounded-xl bg-terracotta/10 px-4 py-3 text-sm font-medium text-terracotta">
          <AlertTriangle size={16} className="mt-0.5 shrink-0" /> {error}
        </div>
      )}

      {/* Step 1: choose the file */}
      {step === 'upload' && (
        <div className="mt-5 rounded-3xl bg-paper p-8 text-center shadow-sm">
          <input ref={picker} type="file" accept=".csv,.xlsx,.txt" onChange={handleFile} className="hidden" />
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-forest-100 text-forest-700">
            <Upload size={24} />
          </div>
          <p className="mt-4 font-semibold text-forest-900">Choose your M-Pesa statement</p>
          <p className="mt-1 text-sm text-muted">From the M-Pesa business portal, download the Paybill statement as Excel (.xlsx) or CSV, for the dates you want to check.</p>
          <button onClick={() => picker.current && picker.current.click()} disabled={busy !== ''} className="mt-5 inline-flex items-center gap-2 rounded-xl bg-forest-900 px-6 py-3 text-sm font-semibold text-white hover:bg-forest-700 disabled:opacity-60">
            {busy === 'preview' ? <Loader2 size={16} className="animate-spin" /> : <Upload size={16} />} Choose a file
          </button>
        </div>
      )}

      {/* Step 2: check the columns */}
      {step === 'columns' && preview && (
        <div className="mt-5 rounded-3xl bg-paper p-6 shadow-sm">
          <h2 className="font-display text-lg font-bold text-forest-900">Check the columns</h2>
          <p className="text-sm text-muted">
            {file.name}: {preview.rows_found} rows. We guessed which column is which. {preview.header_found ? 'Please check the guesses.' : 'We could not find the heading row, so please choose carefully.'}
          </p>
          <div className="mt-4 space-y-3">
            {FIELDS.map(([key, label, needed]) => (
              <label key={key} className="block">
                <span className="mb-1 block text-sm font-medium">
                  {label} {needed && <span className="text-terracotta">*</span>}
                </span>
                <select className={inputClass} value={mapping[key] ?? ''} onChange={(e) => setMapping({ ...mapping, [key]: e.target.value })}>
                  <option value="">{needed ? 'Choose...' : 'Not in my file'}</option>
                  {preview.columns.map((name, index) => (
                    <option key={index} value={index}>
                      {index + 1}. {name || '(no heading)'}
                    </option>
                  ))}
                </select>
              </label>
            ))}
          </div>
          {preview.sample.length > 0 && (
            <div className="mt-5 overflow-x-auto rounded-2xl bg-cream p-3">
              <p className="mb-2 text-xs font-semibold text-forest-900">The first rows of your file</p>
              <table className="min-w-full text-left text-[11px] text-ink/80">
                <thead>
                  <tr>
                    {preview.columns.map((name, index) => (
                      <th key={index} className="whitespace-nowrap px-2 py-1 font-semibold">
                        {index + 1}. {name}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {preview.sample.map((row, rowIndex) => (
                    <tr key={rowIndex}>
                      {row.map((value, index) => (
                        <td key={index} className="whitespace-nowrap px-2 py-1">
                          {value}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <div className="mt-5 flex gap-3">
            <button onClick={reset} className="flex items-center gap-2 rounded-xl bg-forest-100 px-5 py-3 text-sm font-semibold text-forest-700 hover:bg-forest-200">
              <ArrowLeft size={16} /> Back
            </button>
            <button onClick={check} disabled={!ready || busy !== ''} className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-forest-900 px-5 py-3 text-sm font-semibold text-white hover:bg-forest-700 disabled:opacity-50">
              {busy === 'check' && <Loader2 size={16} className="animate-spin" />} Check my statement
            </button>
          </div>
        </div>
      )}

      {/* Step 3: the result */}
      {step === 'results' && result && (
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
          <div className={`mt-5 rounded-3xl p-6 text-white shadow-xl ${nothingWrong ? 'bg-forest-500' : 'bg-forest-900'}`}>
            <p className="text-sm font-semibold opacity-90">
              {summary.first_date ? `${formatDate(summary.first_date)} to ${formatDate(summary.last_date)}` : 'Your statement'}
            </p>
            <p className="mt-1 font-display text-3xl font-extrabold">{summary.credit_count} payments in</p>
            <p className="text-sm opacity-90">
              {money(summary.credit_total)} received · {summary.matched} match your records
            </p>
            <p className="mt-2 text-xs opacity-80">
              {nothingWrong ? 'Everything in the statement matches what you recorded.' : 'Some things need your attention. They are listed below.'}
              {summary.skipped > 0 ? ` ${summary.skipped} lines were not payments (headings, fees or totals) and were skipped.` : ''}
              {summary.duplicates > 0 ? ` ${summary.duplicates} repeated code${summary.duplicates === 1 ? '' : 's'} counted once.` : ''}
            </p>
            <button onClick={reset} className="mt-4 rounded-xl bg-white/20 px-4 py-2 text-sm font-semibold hover:bg-white/30">
              Check another statement
            </button>
          </div>

          {message && (
            <div role="status" className="mt-4 flex items-center gap-2 rounded-xl bg-forest-100 px-4 py-3 text-sm font-medium text-forest-700">
              <CheckCircle2 size={18} /> {message}
            </div>
          )}

          {/* Money that nobody recorded */}
          {result.missing.length > 0 && (
            <Group tone="bg-gold/30 text-forest-900" title="In the statement, not recorded" count={result.missing.length} help="Money arrived that is not in EstateLoom. Choose the tenant, tick the ones to add, and press Record. The amount and date come from the statement.">
              <ul className="divide-y divide-forest-100">
                {result.missing.map((row) => (
                  <li key={row.receipt} className="py-3">
                    <div className="flex items-start gap-3">
                      <input
                        type="checkbox"
                        checked={ticked.has(row.receipt)}
                        disabled={!choice[row.receipt]}
                        onChange={() => {
                          const next = new Set(ticked)
                          if (next.has(row.receipt)) next.delete(row.receipt)
                          else next.add(row.receipt)
                          setTicked(next)
                        }}
                        aria-label={`Record ${row.receipt}`}
                        className="mt-1 h-5 w-5 shrink-0 accent-forest-900"
                      />
                      <div className="min-w-0 flex-1">
                        <p className="flex items-baseline justify-between gap-3">
                          <span className="font-mono text-xs text-muted">
                            {row.receipt} · {formatDate(row.paid_on)}
                          </span>
                          <span className="text-sm font-bold text-forest-900">{money(row.amount)}</span>
                        </p>
                        {(row.party || row.details) && <p className="mt-0.5 truncate text-xs text-muted">{row.party || row.details}</p>}
                        {row.account && <p className="text-xs text-muted">Account typed: {row.account}</p>}
                        <select
                          className={`${inputClass} mt-2 py-2 text-sm`}
                          value={choice[row.receipt] || ''}
                          onChange={(e) => {
                            setChoice({ ...choice, [row.receipt]: e.target.value })
                            const next = new Set(ticked)
                            if (e.target.value) next.add(row.receipt)
                            else next.delete(row.receipt)
                            setTicked(next)
                          }}
                          aria-label={`Tenant for ${row.receipt}`}
                        >
                          <option value="">Choose the tenant...</option>
                          {result.leases.map((lease) => (
                            <option key={lease.lease_id} value={lease.lease_id}>
                              {lease.label}
                              {row.candidates.includes(lease.lease_id) ? '  (suggested)' : ''}
                            </option>
                          ))}
                        </select>
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
              <button onClick={record} disabled={busy !== '' || ![...ticked].some((receipt) => choice[receipt])} className="mt-3 flex items-center gap-2 rounded-xl bg-forest-900 px-5 py-3 text-sm font-semibold text-white hover:bg-forest-700 disabled:opacity-50">
                {busy === 'record' && <Loader2 size={16} className="animate-spin" />} Record {[...ticked].filter((receipt) => choice[receipt]).length} payment{[...ticked].filter((receipt) => choice[receipt]).length === 1 ? '' : 's'}
              </button>
            </Group>
          )}

          {/* Reversed or failed */}
          {result.reversed.length > 0 && (
            <Group tone="bg-terracotta/15 text-terracotta" title="Counted here, but reversed or failed" count={result.reversed.length} help="EstateLoom counts these as paid, but the statement says the money did not stay. Open the tenant, check, and delete the payment if it is wrong.">
              <ul className="divide-y divide-forest-100">
                {result.reversed.map((row) => (
                  <PaymentLine key={row.payment_id} row={row} extra={row.why} />
                ))}
              </ul>
            </Group>
          )}

          {/* A different amount */}
          {result.mismatched.length > 0 && (
            <Group tone="bg-amber/20 text-amber" title="A different amount" count={result.mismatched.length} help="The same M-Pesa code is in both, but the amounts differ. Open the tenant and correct whichever is wrong.">
              <ul className="divide-y divide-forest-100">
                {result.mismatched.map((row) => (
                  <PaymentLine key={row.payment_id} row={row} extra={`The statement says ${money(row.statement_amount)}, you recorded ${money(row.amount)}.`} />
                ))}
              </ul>
            </Group>
          )}

          {/* Recorded but not in the statement */}
          {result.not_in_statement.length > 0 && (
            <Group tone="bg-amber/20 text-amber" title="Recorded, but not in the statement" count={result.not_in_statement.length} help="You recorded these as M-Pesa within the dates of the statement, but their codes are not in it. A mistyped code is the usual reason.">
              <ul className="divide-y divide-forest-100">
                {result.not_in_statement.map((row) => (
                  <PaymentLine key={row.payment_id} row={row} />
                ))}
              </ul>
            </Group>
          )}
        </motion.div>
      )}
    </div>
  )
}