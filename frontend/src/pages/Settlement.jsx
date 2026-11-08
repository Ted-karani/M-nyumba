// Import the React tools we need
import { useCallback, useEffect, useState } from 'react'
// Import the page-switching tools
import { Link, useParams } from 'react-router-dom'
// Import the icons we use
import { ArrowLeft, CheckCircle2, Info, Lock, Loader2, Plus, Printer, Trash2 } from 'lucide-react'
// Import our own files
import { useAuth } from '../AuthContext'
import { deleteRefund, finalizeSettlement, getSettlement, reopenSettlement, saveRefund, saveSettlement } from '../api'
import { Field, inputClass } from '../components/Field'
import { formatDate, money } from '../format'

// Quick ideas for deductions
const IDEAS = ['Cleaning', 'Repainting', 'Key replacement', 'Damaged item', 'Final water bill', 'Final electricity bill']
// Each deduction row gets its own number, so the screen can tell them apart
let nextRow = 1

// A row in the money summary
function Row({ label, value, strong, tone }) {
  return (
    <div className={`flex items-baseline justify-between gap-4 py-2 ${strong ? 'border-t border-forest-100 pt-3' : ''}`}>
      <p className={`text-sm ${strong ? 'font-bold text-forest-900' : 'text-ink/80'}`}>{label}</p>
      <p className={`shrink-0 text-sm ${strong ? 'font-bold' : ''} ${tone || 'text-forest-900'}`}>{value}</p>
    </div>
  )
}

// The page for one tenant's move-out settlement
export default function Settlement() {
  const { leaseId } = useParams()
  const { user } = useAuth()
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState('')
  // The form the landlord is filling in
  const [held, setHeld] = useState('0')
  const [rows, setRows] = useState([])
  const [notes, setNotes] = useState('')
  // The refund form, and whether the printable statement is showing
  const [refund, setRefund] = useState({ amount: '', date: new Date().toISOString().slice(0, 10), method: 'mpesa', reference: '', note: '' })
  const [printing, setPrinting] = useState(false)

  // Load the tenancy, and fill the form from the settlement (or from the ledger, if there is none yet)
  const load = useCallback(async () => {
    setError('')
    try {
      const result = await getSettlement(leaseId)
      setData(result)
      const settlement = result.settlement
      setHeld(String(settlement ? settlement.deposit_held : result.suggested.deposit_held))
      setRows((settlement ? settlement.deductions : []).map((item) => ({ id: nextRow++, label: item.label, amount: String(item.amount) })))
      setNotes(settlement?.notes || '')
      setRefund((old) => ({ ...old, amount: String(settlement ? settlement.refund_due : '') }))
    } catch (err) {
      setError(err.message)
    }
  }, [leaseId])
  useEffect(() => {
    load()
  }, [load])

  // Run an action and then reload
  async function run(name, action) {
    setError('')
    setBusy(name)
    try {
      await action()
      await load()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy('')
    }
  }

  // The form as the server wants it
  const payload = () => ({
    deposit_held: Number(held) || 0,
    deductions: rows.filter((row) => row.label.trim() && Number(row.amount) > 0).map((row) => ({ label: row.label.trim(), amount: Number(row.amount) })),
    notes: notes.trim() || null,
  })

  if (error && !data) {
    return (
      <div className="mx-auto max-w-3xl">
        <Link to="/settlements" className="flex items-center gap-1.5 text-sm font-semibold text-forest-700 hover:underline">
          <ArrowLeft size={15} /> Back
        </Link>
        <div role="alert" className="mt-4 rounded-xl bg-terracotta/10 px-4 py-3 text-sm font-medium text-terracotta">
          {error}
        </div>
      </div>
    )
  }
  if (!data) return <div className="mx-auto h-48 max-w-3xl animate-pulse rounded-3xl bg-forest-100" />

  const { lease, suggested, settlement } = data
  const locked = settlement?.status === 'final'
  // The numbers on screen: frozen ones when final, otherwise worked out from the form
  const sums = locked
    ? settlement
    : (() => {
        const items = payload().deductions
        const total = items.reduce((sum, item) => sum + item.amount, 0)
        const net = (Number(held) || 0) + suggested.credit - suggested.unpaid_charges - total
        return { deposit_held: Number(held) || 0, credit: suggested.credit, unpaid_charges: suggested.unpaid_charges, deductions: items, total_deductions: total, refund_due: Math.max(net, 0), tenant_owes: Math.max(-net, 0) }
      })()
  const done = settlement?.refund

  // The statement (shown on screen in a window, and printed from there)
  const statement = (
    <div id="print-area" className="mx-auto max-w-2xl bg-white p-8 text-ink">
      <p className="text-xs font-semibold uppercase tracking-wide text-muted">Deposit settlement statement</p>
      <h2 className="mt-1 font-display text-2xl font-extrabold text-forest-900">{lease.tenant_name}</h2>
      <p className="text-sm text-muted">
        {lease.unit_number}, {lease.property_name}
      </p>
      <p className="mt-1 text-sm text-muted">
        Tenancy from {formatDate(lease.start_date)}
        {lease.end_date ? ` to ${formatDate(lease.end_date)}` : ''}
      </p>
      <div className="mt-5 divide-y divide-forest-100 border-y border-forest-100">
        <Row label="Deposit held" value={money(sums.deposit_held)} />
        {sums.credit > 0 && <Row label="Rent paid ahead" value={`+ ${money(sums.credit)}`} />}
        {sums.unpaid_charges > 0 && <Row label="Rent, bills and fees still owing" value={`- ${money(sums.unpaid_charges)}`} />}
        {sums.deductions.map((item, index) => (
          <Row key={index} label={item.label} value={`- ${money(item.amount)}`} />
        ))}
      </div>
      {sums.tenant_owes > 0 ? (
        <Row strong label="The tenant still owes" value={money(sums.tenant_owes)} tone="text-terracotta" />
      ) : (
        <Row strong label="Refund to the tenant" value={money(sums.refund_due)} />
      )}
      {settlement?.notes && <p className="mt-3 text-sm">Note: {settlement.notes}</p>}
      {done && (
        <p className="mt-3 text-sm">
          Refund of {money(done.amount)} paid on {formatDate(done.paid_on)} by {done.method}
          {done.reference ? `, reference ${done.reference}` : ''}.
        </p>
      )}
      <div className="mt-12 grid grid-cols-2 gap-10 text-sm">
        <div>
          <div className="border-t border-ink/60 pt-1">Landlord: {user.full_name}</div>
          <p className="mt-1 text-xs text-muted">Date:</p>
        </div>
        <div>
          <div className="border-t border-ink/60 pt-1">Tenant: {lease.tenant_name}</div>
          <p className="mt-1 text-xs text-muted">Date:</p>
        </div>
      </div>
      <p className="mt-8 text-[10px] text-muted">Prepared with EstateLoom on {formatDate(new Date().toISOString().slice(0, 10))}.</p>
    </div>
  )

  return (
    <div className="mx-auto max-w-3xl">
      <Link to="/settlements" className="flex items-center gap-1.5 text-sm font-semibold text-forest-700 hover:underline">
        <ArrowLeft size={15} /> All settlements
      </Link>
      <h1 className="mt-3 text-3xl font-extrabold text-forest-900">{lease.tenant_name}</h1>
      <p className="text-muted">
        {lease.unit_number}, {lease.property_name}
        {lease.end_date ? ` · moved out ${formatDate(lease.end_date)}` : ''}
      </p>

      {error && (
        <div role="alert" className="mt-4 rounded-xl bg-terracotta/10 px-4 py-3 text-sm font-medium text-terracotta">
          {error}
        </div>
      )}

      {locked && (
        <div className="mt-4 flex items-center gap-2 rounded-xl bg-forest-100 px-4 py-3 text-sm font-medium text-forest-700">
          <Lock size={16} /> Final. The numbers are frozen{settlement.finalized_at ? ` (${formatDate(settlement.finalized_at.slice(0, 10))})` : ''}.
        </div>
      )}

      {/* The deposit, and the deductions */}
      {!locked && (
        <div className="mt-5 rounded-3xl bg-paper p-6 shadow-sm">
          <h2 className="font-display text-lg font-bold text-forest-900">1. The deposit</h2>
          <Field
            label="Deposit you are holding (KSh)"
            hint={suggested.found_from === 'paid' ? `The tenant has paid ${money(suggested.deposit_held)} of the ${money(suggested.deposit_charged)} deposit. Change it if that is wrong.` : `Taken from the deposit written on the tenancy (${money(lease.agreed_deposit)}). Change it if that is wrong.`}
          >
            <input className={inputClass} type="number" min="0" step="1" inputMode="numeric" value={held} onChange={(e) => setHeld(e.target.value)} />
          </Field>

          <h2 className="mt-6 font-display text-lg font-bold text-forest-900">2. Deductions</h2>
          <p className="text-xs text-muted">Damage, cleaning, a final bill that is not on the statement yet. Rent, bills and fees the tenant still owes are taken off automatically.</p>
          <div className="mt-3 flex flex-wrap gap-2">
            {IDEAS.map((idea) => (
              <button key={idea} type="button" onClick={() => setRows([...rows, { id: nextRow++, label: idea, amount: '' }])} className="flex items-center gap-1 rounded-full bg-forest-100 px-3 py-1.5 text-xs font-semibold text-forest-700 hover:bg-forest-200">
                <Plus size={12} /> {idea}
              </button>
            ))}
          </div>
          <div className="mt-3 space-y-2">
            {rows.map((row) => (
              <div key={row.id} className="flex gap-2">
                <input className={inputClass} placeholder="What for" maxLength={60} value={row.label} onChange={(e) => setRows(rows.map((item) => (item.id === row.id ? { ...item, label: e.target.value } : item)))} aria-label="What the deduction is for" />
                <input className={`${inputClass} w-32`} type="number" min="1" step="1" inputMode="numeric" placeholder="KSh" value={row.amount} onChange={(e) => setRows(rows.map((item) => (item.id === row.id ? { ...item, amount: e.target.value } : item)))} aria-label="Amount" />
                <button type="button" onClick={() => setRows(rows.filter((item) => item.id !== row.id))} aria-label="Remove" className="rounded-xl px-2 text-muted hover:bg-terracotta/10 hover:text-terracotta">
                  <Trash2 size={16} />
                </button>
              </div>
            ))}
            <button type="button" onClick={() => setRows([...rows, { id: nextRow++, label: '', amount: '' }])} className="flex items-center gap-1.5 text-sm font-semibold text-forest-700 hover:underline">
              <Plus size={14} /> Add another
            </button>
          </div>
          <div className="mt-4">
            <Field label="Note on the statement (optional)">
              <input className={inputClass} maxLength={300} value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Keys returned on 3 March" />
            </Field>
          </div>
        </div>
      )}

      {/* The result */}
      <div className="mt-4 rounded-3xl bg-paper p-6 shadow-sm">
        <h2 className="font-display text-lg font-bold text-forest-900">{locked ? 'The settlement' : '3. The result'}</h2>
        <div className="mt-2 divide-y divide-forest-100">
          <Row label="Deposit held" value={money(sums.deposit_held)} />
          {sums.credit > 0 && <Row label="Rent paid ahead" value={`+ ${money(sums.credit)}`} />}
          {sums.unpaid_charges > 0 && <Row label="Rent, bills and fees still owing" value={`- ${money(sums.unpaid_charges)}`} />}
          {sums.deductions.map((item, index) => (
            <Row key={index} label={item.label} value={`- ${money(item.amount)}`} />
          ))}
        </div>
        {sums.tenant_owes > 0 ? (
          <Row strong label="The tenant still owes you" value={money(sums.tenant_owes)} tone="text-terracotta" />
        ) : (
          <Row strong label="Refund to the tenant" value={money(sums.refund_due)} />
        )}
        {sums.tenant_owes > 0 && <p className="mt-1 text-xs text-muted">The deposit does not cover everything. The rest stays on the tenant’s statement for you to collect.</p>}
        <div className="mt-4 flex items-start gap-2 rounded-xl bg-cream p-3 text-xs text-ink/80">
          <Info size={14} className="mt-0.5 shrink-0 text-forest-700" />
          <p>This does not change the tenant’s statement. A deposit kept to cover unpaid rent may count as rental income: ask your accountant. Check the final month’s rent charge before you settle.</p>
        </div>

        {!locked && (
          <div className="mt-5 flex flex-col gap-3 sm:flex-row">
            <button onClick={() => run('save', () => saveSettlement(leaseId, payload()))} disabled={busy !== ''} className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-forest-100 py-3.5 font-semibold text-forest-700 hover:bg-forest-200 disabled:opacity-60">
              {busy === 'save' && <Loader2 size={18} className="animate-spin" />} Save draft
            </button>
            <button
              onClick={() => window.confirm('Finalise this settlement? The numbers will be frozen. You can still reopen it before a refund is recorded.') && run('final', () => finalizeSettlement(leaseId, payload()))}
              disabled={busy !== ''}
              className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-forest-900 py-3.5 font-semibold text-white hover:bg-forest-700 disabled:opacity-60"
            >
              {busy === 'final' && <Loader2 size={18} className="animate-spin" />} Finalise
            </button>
          </div>
        )}
        {locked && (
          <div className="mt-5 flex flex-wrap gap-2">
            <button onClick={() => setPrinting(true)} className="flex items-center gap-2 rounded-xl bg-forest-900 px-5 py-3 text-sm font-semibold text-white hover:bg-forest-700">
              <Printer size={16} /> Statement to print
            </button>
            {!done && (
              <button onClick={() => window.confirm('Open this settlement again to change it?') && run('reopen', () => reopenSettlement(leaseId))} disabled={busy !== ''} className="rounded-xl bg-forest-100 px-5 py-3 text-sm font-semibold text-forest-700 hover:bg-forest-200">
                Reopen
              </button>
            )}
          </div>
        )}
      </div>

      {/* The refund */}
      {locked && settlement.refund_due > 0 && (
        <div className="mt-4 rounded-3xl bg-paper p-6 shadow-sm">
          <h2 className="font-display text-lg font-bold text-forest-900">The refund</h2>
          {done ? (
            <>
              <p className="mt-2 flex items-center gap-2 text-sm font-semibold text-forest-700">
                <CheckCircle2 size={18} /> {money(done.amount)} paid on {formatDate(done.paid_on)} by {done.method}
                {done.reference ? ` (${done.reference})` : ''}
              </p>
              {done.amount < settlement.refund_due && <p className="mt-1 text-xs text-muted">{money(settlement.refund_due - done.amount)} is still to be refunded.</p>}
              <button onClick={() => window.confirm('Remove the record of this refund?') && run('undo', () => deleteRefund(leaseId))} disabled={busy !== ''} className="mt-3 text-sm font-semibold text-muted hover:text-terracotta">
                Remove the record
              </button>
            </>
          ) : (
            <form
              onSubmit={(event) => {
                event.preventDefault()
                run('refund', () => saveRefund(leaseId, { amount: Number(refund.amount), paid_on: refund.date, method: refund.method, reference: refund.reference.trim() || null, note: refund.note.trim() || null }))
              }}
              className="mt-3 space-y-4"
            >
              <p className="text-sm text-muted">Record it once you have paid the tenant. This only keeps a record: no money moves from here.</p>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Amount paid (KSh)">
                  <input className={inputClass} type="number" min="1" max={settlement.refund_due} step="1" inputMode="numeric" value={refund.amount} onChange={(e) => setRefund({ ...refund, amount: e.target.value })} required />
                </Field>
                <Field label="Date paid">
                  <input className={inputClass} type="date" max={new Date().toISOString().slice(0, 10)} value={refund.date} onChange={(e) => setRefund({ ...refund, date: e.target.value })} required />
                </Field>
                <Field label="How">
                  <select className={inputClass} value={refund.method} onChange={(e) => setRefund({ ...refund, method: e.target.value })}>
                    <option value="mpesa">M-Pesa</option>
                    <option value="cash">Cash</option>
                    <option value="bank">Bank</option>
                  </select>
                </Field>
                <Field label="M-Pesa code or reference">
                  <input className={inputClass} maxLength={40} value={refund.reference} onChange={(e) => setRefund({ ...refund, reference: e.target.value })} />
                </Field>
              </div>
              <button type="submit" disabled={busy !== ''} className="flex items-center gap-2 rounded-xl bg-forest-900 px-5 py-3 text-sm font-semibold text-white hover:bg-forest-700 disabled:opacity-60">
                {busy === 'refund' && <Loader2 size={16} className="animate-spin" />} Record the refund
              </button>
            </form>
          )}
        </div>
      )}

      {/* The printable statement */}
      {printing && (
        <div className="fixed inset-0 z-50 overflow-auto bg-forest-900/60 p-4 backdrop-blur-sm">
          <div className="mx-auto max-w-2xl">
            <div className="mb-3 flex justify-end gap-2 print:hidden">
              <button onClick={() => window.print()} className="flex items-center gap-2 rounded-xl bg-white px-4 py-2.5 text-sm font-semibold text-forest-900 hover:bg-cream">
                <Printer size={16} /> Print or save as PDF
              </button>
              <button onClick={() => setPrinting(false)} className="rounded-xl bg-white/20 px-4 py-2.5 text-sm font-semibold text-white hover:bg-white/30">
                Close
              </button>
            </div>
            <div className="rounded-2xl shadow-xl">{statement}</div>
          </div>
        </div>
      )}
    </div>
  )
}