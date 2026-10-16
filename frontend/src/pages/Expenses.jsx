// Import the React tools we need
import { useCallback, useEffect, useState } from 'react'
// Import the animation tool
import { motion } from 'framer-motion'
// Import the icons we use
import { ChevronLeft, ChevronRight, Coins, Plus, RefreshCw } from 'lucide-react'
// Import our own files
import { createExpense, deleteExpense, getDashboard, getExpenses, updateExpense } from '../api'
import { EXPENSE_CATEGORIES, categoryLabel } from '../categories'
import { currentPeriod, formatDate, money, monthLabel, shiftPeriod } from '../format'
import ConfirmDialog from '../components/ConfirmDialog'
import ExpenseForm from '../components/ExpenseForm'
import { inputClass } from '../components/Field'
import Modal from '../components/Modal'

// How the list appears: the cards come in one after another
const listAnimation = { hidden: {}, show: { transition: { staggerChildren: 0.04 } } }
// How each card appears: fade in while sliding up
const itemAnimation = { hidden: { opacity: 0, y: 12 }, show: { opacity: 1, y: 0 } }

// The page that lists everything spent
export default function Expenses() {
  // The filters: which month, which property, which kind
  const [month, setMonth] = useState(currentPeriod())
  const [propertyId, setPropertyId] = useState('')
  const [category, setCategory] = useState('')
  // The data from the backend (nothing until it arrives)
  const [data, setData] = useState(null)
  const [properties, setProperties] = useState([])
  // The error message, if loading failed
  const [error, setError] = useState('')
  // Which pop-ups are open
  const [adding, setAdding] = useState(false)
  const [editing, setEditing] = useState(null)
  const [deleting, setDeleting] = useState(null)

  // Load the properties once, for the forms and the filter
  useEffect(() => {
    getDashboard()
      .then((dashboard) => setProperties(dashboard.properties))
      .catch(() => setProperties([]))
  }, [])

  // Load the expenses (called again after every change)
  const load = useCallback(() => {
    setError('')
    getExpenses({ month, property_id: propertyId, category })
      .then(setData)
      .catch((err) => setError(err.message))
  }, [month, propertyId, category])

  // Load them when the page opens or a filter changes
  useEffect(() => {
    load()
  }, [load])

  // The biggest kind of expense, so the bars can be drawn in proportion
  const biggest = data && data.by_category.length > 0 ? data.by_category[0].total : 1

  return (
    <div>
      {/* The title and the add button */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-extrabold text-forest-900">Expenses</h1>
          <p className="text-muted">What you spend to run your properties.</p>
        </div>
        <motion.button
          whileTap={{ scale: 0.96 }}
          onClick={() => setAdding(true)}
          className="flex shrink-0 items-center gap-2 rounded-xl bg-forest-900 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-forest-900/20 hover:bg-forest-700"
        >
          <Plus size={18} /> Add
        </motion.button>
      </div>

      {/* The month controls */}
      <div className="mt-6 flex flex-wrap items-center gap-2">
        <div className="flex items-center rounded-xl bg-paper shadow-sm">
          <button onClick={() => setMonth(shiftPeriod(month || currentPeriod(), -1))} aria-label="Previous month" className="rounded-l-xl p-3 text-forest-700 hover:bg-forest-100">
            <ChevronLeft size={18} />
          </button>
          <span className="min-w-36 px-2 text-center text-sm font-semibold text-forest-900">{month ? monthLabel(month) : 'All time'}</span>
          <button onClick={() => setMonth(shiftPeriod(month || currentPeriod(), 1))} aria-label="Next month" className="rounded-r-xl p-3 text-forest-700 hover:bg-forest-100">
            <ChevronRight size={18} />
          </button>
        </div>
        <button
          onClick={() => setMonth(currentPeriod())}
          className={`rounded-full px-4 py-2 text-sm font-semibold transition ${month === currentPeriod() ? 'bg-forest-900 text-white' : 'bg-paper text-forest-700 hover:bg-forest-100'}`}
        >
          This month
        </button>
        <button
          onClick={() => setMonth('')}
          className={`rounded-full px-4 py-2 text-sm font-semibold transition ${month === '' ? 'bg-forest-900 text-white' : 'bg-paper text-forest-700 hover:bg-forest-100'}`}
        >
          All time
        </button>
      </div>

      {/* If loading failed, show the message and a retry button */}
      {error && (
        <div className="mt-6 rounded-3xl bg-terracotta/10 p-6 text-terracotta">
          <p className="font-semibold">Could not load your expenses</p>
          <p className="mt-1 text-sm">{error}</p>
          <button onClick={load} className="mt-4 flex items-center gap-2 rounded-xl bg-terracotta px-4 py-2 text-sm font-semibold text-white">
            <RefreshCw size={16} /> Try again
          </button>
        </div>
      )}

      {/* While waiting, show grey placeholder boxes */}
      {!error && !data && (
        <div className="mt-6 space-y-3">
          <div className="h-36 animate-pulse rounded-3xl bg-forest-100" />
          <div className="h-16 animate-pulse rounded-2xl bg-forest-100" />
        </div>
      )}

      {data && (
        <>
          {/* The green summary card */}
          <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} className="mt-4 rounded-3xl bg-forest-900 p-6 text-white shadow-xl">
            <p className="text-sm text-forest-200">{month ? `Spent in ${monthLabel(month)}` : 'Spent, all time'}</p>
            <p className="font-display text-4xl font-bold">{money(data.total)}</p>
            <p className="mt-1 text-sm text-forest-200">
              {data.count} expense{data.count === 1 ? '' : 's'} · repairs are counted separately on the Reports page
            </p>
            {/* The biggest kinds of expense */}
            {data.by_category.length > 0 && (
              <div className="mt-5 space-y-3">
                {data.by_category.slice(0, 4).map((item) => (
                  <div key={item.category}>
                    <div className="flex justify-between text-sm">
                      <span className="text-forest-100">{categoryLabel(item.category)}</span>
                      <span className="font-semibold">{money(item.total)}</span>
                    </div>
                    <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-white/15">
                      <motion.div
                        className="h-full rounded-full bg-gold"
                        initial={{ width: 0 }}
                        animate={{ width: `${(item.total / biggest) * 100}%` }}
                        transition={{ duration: 0.7, ease: 'easeOut' }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </motion.div>

          {/* The property and kind filters */}
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            {properties.length > 1 && (
              <select value={propertyId} onChange={(e) => setPropertyId(e.target.value)} className={inputClass} aria-label="Filter by property">
                <option value="">All properties</option>
                {properties.map((prop) => (
                  <option key={prop.property_id} value={prop.property_id}>
                    {prop.name}
                  </option>
                ))}
              </select>
            )}
            <select value={category} onChange={(e) => setCategory(e.target.value)} className={inputClass} aria-label="Filter by kind">
              <option value="">All kinds</option>
              {EXPENSE_CATEGORIES.map((item) => (
                <option key={item.key} value={item.key}>
                  {item.label}
                </option>
              ))}
            </select>
          </div>

          {/* The list of expenses */}
          {data.items.length === 0 ? (
            <div className="mt-6 flex flex-col items-center rounded-3xl bg-paper p-10 text-center shadow-sm">
              <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-forest-100 text-forest-700">
                <Coins size={26} />
              </div>
              <p className="mt-4 font-semibold text-forest-900">No expenses here</p>
              <p className="mt-1 text-sm text-muted">Add what you spend, so your reports show what is really left.</p>
            </div>
          ) : (
            <motion.div key={`${month}-${propertyId}-${category}`} variants={listAnimation} initial="hidden" animate="show" className="mt-4 divide-y divide-forest-100 overflow-hidden rounded-2xl bg-paper shadow-sm">
              {data.items.map((item) => (
                <motion.button
                  key={item.id}
                  variants={itemAnimation}
                  onClick={() => setEditing(item)}
                  className="flex w-full items-center gap-3 p-4 text-left transition hover:bg-forest-100/50"
                >
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-semibold text-forest-900">{item.description || categoryLabel(item.category)}</p>
                    <p className="truncate text-xs text-muted">
                      {categoryLabel(item.category)} · {item.property_name || 'General'}
                      {item.paid_to ? ` · ${item.paid_to}` : ''}
                    </p>
                    <p className="text-xs text-muted">{formatDate(item.spent_on)}</p>
                  </div>
                  <p className="font-display text-lg font-bold text-terracotta">{money(item.amount)}</p>
                </motion.button>
              ))}
            </motion.div>
          )}
        </>
      )}

      {/* Add an expense */}
      <Modal open={adding} title="Add an expense" onClose={() => setAdding(false)}>
        <ExpenseForm
          properties={properties}
          submitLabel="Save expense"
          onCancel={() => setAdding(false)}
          onSubmit={async (body) => {
            await createExpense(body)
            setAdding(false)
            load()
          }}
        />
      </Modal>

      {/* Edit an expense */}
      <Modal open={editing !== null} title="Edit expense" onClose={() => setEditing(null)}>
        {editing && (
          <ExpenseForm
            key={editing.id}
            properties={properties}
            initial={editing}
            submitLabel="Save changes"
            onCancel={() => setEditing(null)}
            onSubmit={async (body) => {
              await updateExpense(editing.id, body)
              setEditing(null)
              load()
            }}
            onDelete={() => {
              // Close the edit window and ask "are you sure?"
              setDeleting(editing)
              setEditing(null)
            }}
          />
        )}
      </Modal>

      {/* Delete an expense */}
      <ConfirmDialog
        open={deleting !== null}
        title="Delete this expense?"
        message={deleting ? `Delete the ${money(deleting.amount)} expense? This cannot be undone.` : ''}
        confirmLabel="Delete"
        onClose={() => setDeleting(null)}
        onConfirm={async () => {
          await deleteExpense(deleting.id)
          setDeleting(null)
          load()
        }}
      />
    </div>
  )
}