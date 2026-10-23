// Import the React tools we need
import { useCallback, useEffect, useState } from 'react'
// Import the page-switching tool
import { Link } from 'react-router-dom'
// Import the animation tool
import { motion } from 'framer-motion'
// Import the icons we use
import { ChevronDown, ChevronUp, ClipboardCheck, Plus, Receipt, Smartphone, Trash2, Wallet } from 'lucide-react'
// Import our own files
import {
  createCharge,
  createPayment,
  deleteCharge,
  deletePayment,
  endLease,
  getCharges,
  getLeaseInspections,
  getMpesaEnabled,
  getPayments,
} from '../api'
import { CHARGE_LABELS, METHOD_LABELS, formatDate, money } from '../format'
import BalanceBadge from './BalanceBadge'
import ChargeForm from './ChargeForm'
import ConfirmDialog from './ConfirmDialog'
import Modal from './Modal'
import MpesaPrompt from './MpesaPrompt'
import PaymentForm from './PaymentForm'

// Say how far along a checklist is
function checklistStatus(inspection) {
  if (!inspection) return 'Not started'
  return inspection.finalized_at ? 'Done and locked' : 'In progress'
}

// One card for one lease: its balance, actions, and a statement of charges and payments
export default function LeaseCard({ lease, unitInfo, onChanged }) {
  // The charges and payments (nothing until they arrive)
  const [charges, setCharges] = useState(null)
  const [payments, setPayments] = useState(null)
  // The move-in and move-out checklists (nothing until they arrive)
  const [inspections, setInspections] = useState(null)
  // Whether the "Request M-Pesa" button is available to this owner
  const [mpesaOn, setMpesaOn] = useState(false)
  // An error message if the statement could not load
  const [statementError, setStatementError] = useState('')
  // Whether to show the whole statement or only the latest few rows
  const [showAll, setShowAll] = useState(false)
  // Which pop-ups are open
  const [paying, setPaying] = useState(false)
  const [charging, setCharging] = useState(false)
  const [ending, setEnding] = useState(false)
  const [requesting, setRequesting] = useState(false)
  // The row chosen for deleting (nothing when closed)
  const [deleting, setDeleting] = useState(null)

  // Whether this lease is still running
  const isActive = lease.status === 'active'

  // Load the charges and payments of this lease
  const loadStatement = useCallback(async () => {
    try {
      // Ask for both at the same time
      const [chargeList, paymentList] = await Promise.all([getCharges(lease.id), getPayments(lease.id)])
      setCharges(chargeList)
      setPayments(paymentList)
      setStatementError('')
    } catch (err) {
      setStatementError(err.message)
    }
  }, [lease.id])

  // Load the statement when the card first appears
  useEffect(() => {
    loadStatement()
  }, [loadStatement])

  // Load the checklists when the card first appears (if this fails we simply show them as not started)
  useEffect(() => {
    getLeaseInspections(lease.id)
      .then(setInspections)
      .catch(() => setInspections(null))
  }, [lease.id])

  // Find out whether the M-Pesa button should show (if this fails, it stays hidden)
  useEffect(() => {
    getMpesaEnabled()
      .then((result) => setMpesaOn(result.enabled))
      .catch(() => setMpesaOn(false))
  }, [])

  // After any change, reload the statement and tell the page to reload the balance
  async function refresh() {
    await loadStatement()
    onChanged()
  }

  // Put the charges and payments into one list, newest first
  const rows =
    charges && payments
      ? [
          ...charges.map((charge) => ({
            key: `c${charge.id}`,
            kind: 'charge',
            raw: charge,
            date: charge.due_date,
            amount: charge.amount,
            title:
              charge.description ||
              `${CHARGE_LABELS[charge.charge_type] || charge.charge_type}${charge.period ? ` · ${charge.period}` : ''}`,
            sub: `Charge · due ${formatDate(charge.due_date)}`,
          })),
          ...payments.map((payment) => ({
            key: `p${payment.id}`,
            kind: 'payment',
            raw: payment,
            date: payment.paid_on,
            amount: payment.amount,
            title: `${METHOD_LABELS[payment.method] || payment.method} payment`,
            sub: `Payment · ${payment.reference ? `${payment.reference} · ` : ''}${formatDate(payment.paid_on)}`,
          })),
        ].sort((a, b) => (a.date < b.date ? 1 : a.date > b.date ? -1 : 0))
      : null
  // Show only the latest five rows unless the person asks for all
  const visibleRows = rows ? (showAll ? rows : rows.slice(0, 5)) : []

  return (
    <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} className="rounded-3xl bg-paper p-5 shadow-sm">
      {/* The top: the unit and the balance */}
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <p className="font-display text-2xl font-bold text-forest-900">{lease.unit_number}</p>
            <span
              className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                isActive ? 'bg-forest-100 text-forest-700' : 'bg-ink/10 text-muted'
              }`}
            >
              {isActive ? 'Active' : 'Ended'}
            </span>
          </div>
          <p className="truncate text-sm text-muted">{unitInfo ? unitInfo.property_name : ''}</p>
          <p className="mt-1 text-xs text-muted">
            {isActive
              ? `Since ${formatDate(lease.start_date)}${lease.end_date ? ` · leaving ${formatDate(lease.end_date)}` : ''}`
              : `${formatDate(lease.start_date)} to ${lease.end_date ? formatDate(lease.end_date) : '?'}`}
          </p>
        </div>
        <BalanceBadge amount={lease.balance} size="lg" />
      </div>

      {/* The money numbers */}
      <div className="mt-4 grid grid-cols-3 gap-2 text-center">
        <div className="rounded-2xl bg-cream p-3">
          <p className="text-xs text-muted">Rent</p>
          <p className="text-sm font-bold text-forest-900">{money(lease.rent_amount)}</p>
        </div>
        <div className="rounded-2xl bg-cream p-3">
          <p className="text-xs text-muted">Charged</p>
          <p className="text-sm font-bold text-forest-900">{money(lease.total_charged)}</p>
        </div>
        <div className="rounded-2xl bg-cream p-3">
          <p className="text-xs text-muted">Paid</p>
          <p className="text-sm font-bold text-forest-500">{money(lease.total_paid)}</p>
        </div>
      </div>

      {/* The action buttons */}
      <div className="mt-4 flex flex-wrap gap-2">
        {isActive && mpesaOn && (
          <motion.button
            whileTap={{ scale: 0.96 }}
            onClick={() => setRequesting(true)}
            className="flex items-center gap-2 rounded-xl bg-forest-500 px-4 py-2.5 text-sm font-semibold text-white hover:bg-forest-700"
          >
            <Smartphone size={16} /> Request M-Pesa
          </motion.button>
        )}
        <motion.button
          whileTap={{ scale: 0.96 }}
          onClick={() => setPaying(true)}
          className="flex items-center gap-2 rounded-xl bg-forest-900 px-4 py-2.5 text-sm font-semibold text-white hover:bg-forest-700"
        >
          <Wallet size={16} /> Record payment
        </motion.button>
        {isActive && (
          <motion.button
            whileTap={{ scale: 0.96 }}
            onClick={() => setCharging(true)}
            className="flex items-center gap-2 rounded-xl bg-forest-100 px-4 py-2.5 text-sm font-semibold text-forest-700 hover:bg-forest-200"
          >
            <Plus size={16} /> Add charge
          </motion.button>
        )}
        {isActive && (
          <button
            onClick={() => setEnding(true)}
            className="rounded-xl px-4 py-2.5 text-sm font-semibold text-terracotta hover:bg-terracotta/10"
          >
            End lease
          </button>
        )}
      </div>

      {/* The move-in and move-out checklists */}
      <div className="mt-3 grid grid-cols-2 gap-2">
        {[
          { kind: 'move_in', label: 'Move-in checklist', inspection: inspections && inspections.move_in },
          { kind: 'move_out', label: 'Move-out checklist', inspection: inspections && inspections.move_out },
        ].map((item) => (
          <Link
            key={item.kind}
            to={`/leases/${lease.id}/inspection/${item.kind}`}
            className="rounded-xl bg-cream p-3 transition hover:bg-forest-100"
          >
            <p className="flex items-center gap-1.5 text-xs font-semibold text-forest-900">
              <ClipboardCheck size={14} className="shrink-0 text-forest-500" /> {item.label}
            </p>
            <p className={`mt-0.5 text-xs ${item.inspection && item.inspection.finalized_at ? 'font-semibold text-forest-500' : 'text-muted'}`}>
              {checklistStatus(item.inspection)}
            </p>
          </Link>
        ))}
      </div>

      {/* The statement */}
      <div className="mt-5 border-t border-forest-100 pt-4">
        <p className="text-sm font-semibold text-forest-900">Statement</p>
        {statementError && <p className="mt-2 text-sm text-terracotta">{statementError}</p>}
        {!statementError && !rows && <div className="mt-3 h-16 animate-pulse rounded-2xl bg-forest-100" />}
        {rows && rows.length === 0 && <p className="mt-2 text-sm text-muted">Nothing here yet.</p>}
        {rows && rows.length > 0 && (
          <>
            <ul className="mt-1 divide-y divide-forest-100">
              {visibleRows.map((row) => (
                <li key={row.key} className="flex items-center gap-3 py-2.5">
                  <span
                    className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl ${
                      row.kind === 'payment' ? 'bg-forest-100 text-forest-700' : 'bg-amber/15 text-amber'
                    }`}
                  >
                    {row.kind === 'payment' ? <Wallet size={16} /> : <Receipt size={16} />}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-semibold text-forest-900">{row.title}</p>
                    <p className="truncate text-xs text-muted">{row.sub}</p>
                  </div>
                  <p className={`text-sm font-semibold ${row.kind === 'payment' ? 'text-forest-500' : 'text-forest-900'}`}>
                    {money(row.amount)}
                  </p>
                  <button
                    onClick={() => setDeleting(row)}
                    aria-label={`Delete this ${row.kind}`}
                    className="rounded-lg p-1.5 text-muted hover:bg-terracotta/10 hover:text-terracotta"
                  >
                    <Trash2 size={15} />
                  </button>
                </li>
              ))}
            </ul>
            {/* Show or hide the older rows */}
            {rows.length > 5 && (
              <button
                onClick={() => setShowAll(!showAll)}
                className="mt-2 flex items-center gap-1 text-sm font-medium text-forest-700 hover:underline"
              >
                {showAll ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                {showAll ? 'Show less' : `Show all (${rows.length})`}
              </button>
            )}
          </>
        )}
      </div>

      {/* Ask for an M-Pesa payment */}
      <Modal open={requesting} title="Request M-Pesa payment" onClose={() => setRequesting(false)}>
        {requesting && <MpesaPrompt mode="owner" leaseId={lease.id} balance={lease.balance} tenantPhone={lease.tenant_phone || ''} onPaid={refresh} />}
      </Modal>

      {/* Record a payment */}
      <Modal open={paying} title="Record payment" onClose={() => setPaying(false)}>
        <PaymentForm
          lease={lease}
          onCancel={() => setPaying(false)}
          onSubmit={async (body) => {
            await createPayment(lease.id, body)
            setPaying(false)
            await refresh()
          }}
        />
      </Modal>

      {/* Add a charge */}
      <Modal open={charging} title="Add charge" onClose={() => setCharging(false)}>
        {charges && (
          <ChargeForm
            lease={lease}
            charges={charges}
            onCancel={() => setCharging(false)}
            onSubmit={async (body) => {
              await createCharge(lease.id, body)
              setCharging(false)
              await refresh()
            }}
          />
        )}
      </Modal>

      {/* End the lease */}
      <ConfirmDialog
        open={ending}
        title="End this lease?"
        message={`${lease.tenant_name} leaves unit ${lease.unit_number} today and the unit becomes vacant. Any balance they still owe stays on record.`}
        confirmLabel="End lease"
        onClose={() => setEnding(false)}
        onConfirm={async () => {
          await endLease(lease.id)
          setEnding(false)
          onChanged()
        }}
      />

      {/* Delete a charge or payment */}
      <ConfirmDialog
        open={deleting !== null}
        title={deleting ? `Delete this ${deleting.kind}?` : 'Delete?'}
        message={
          deleting
            ? `Delete the ${deleting.kind} of ${money(deleting.amount)}? This changes the balance, so only do it to fix a mistake.`
            : ''
        }
        confirmLabel="Delete"
        onClose={() => setDeleting(null)}
        onConfirm={async () => {
          if (deleting.kind === 'payment') await deletePayment(deleting.raw.id)
          else await deleteCharge(deleting.raw.id)
          setDeleting(null)
          await refresh()
        }}
      />
    </motion.div>
  )
}