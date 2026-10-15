// Import the React tools we need
import { useCallback, useEffect, useState } from 'react'
// Import the page-switching tools
import { useLocation, useNavigate } from 'react-router-dom'
// Import the animation tool
import { motion } from 'framer-motion'
// Import the icons we use
import { Building2, Phone, Plus, RefreshCw, Wrench } from 'lucide-react'
// Import our own files
import { useAuth } from '../AuthContext'
import { createRepair, deleteRepair, getRepairs, getUnitDirectory, getWorkDirectory, updateRepair } from '../api'
import { formatDate, money, phoneLocal } from '../format'
import ConfirmDialog from '../components/ConfirmDialog'
import { inputClass } from '../components/Field'
import Modal from '../components/Modal'
import RepairForm from '../components/RepairForm'

// How the list appears: the cards come in one after another
const listAnimation = { hidden: {}, show: { transition: { staggerChildren: 0.05 } } }
// How each card appears: fade in while sliding up
const itemAnimation = { hidden: { opacity: 0, y: 14 }, show: { opacity: 1, y: 0 } }

// The words and colors for each status
const STATUS_STYLES = {
  open: { label: 'Open', style: 'bg-amber/20 text-amber' },
  in_progress: { label: 'In progress', style: 'bg-gold/25 text-forest-900' },
  fixed: { label: 'Fixed', style: 'bg-forest-100 text-forest-700' },
}

// The words and colors for each priority (normal gets no label, to keep the cards calm)
const PRIORITY_STYLES = {
  urgent: { label: 'Urgent', style: 'bg-terracotta/15 text-terracotta' },
  low: { label: 'Low', style: 'bg-ink/10 text-muted' },
}

// Say how long ago something was reported, like "3 days ago"
function age(createdAt) {
  // The backend saves times in UTC without a "Z" on the end, so we add it
  const created = new Date(createdAt.endsWith('Z') ? createdAt : `${createdAt}Z`)
  // How many whole days have passed
  const days = Math.floor((Date.now() - created.getTime()) / 86400000)
  if (days <= 0) return 'Today'
  if (days === 1) return '1 day ago'
  return `${days} days ago`
}

// The page that lists all the repairs
export default function Repairs() {
  // Who is logged in? Caretakers see a simpler version without money
  const { user } = useAuth()
  const isCaretaker = user.role === 'caretaker'
  // Lets us read what the last page sent us, and clear it
  const location = useLocation()
  const navigate = useNavigate()
  // The filters: which status ("" means all) and which property
  const [status, setStatus] = useState('')
  const [propertyId, setPropertyId] = useState('')
  // The data from the backend (nothing until it arrives)
  const [report, setReport] = useState(null)
  const [directory, setDirectory] = useState(null)
  // The error message, if loading failed
  const [error, setError] = useState('')
  // Which pop-ups are open
  const [adding, setAdding] = useState(false)
  const [editing, setEditing] = useState(null)
  const [deleting, setDeleting] = useState(null)

  // Load the properties and units once, for the forms and the property filter
  useEffect(() => {
    const loader = isCaretaker ? getWorkDirectory : getUnitDirectory
    loader()
      .then(setDirectory)
      .catch((err) => setError(err.message))
  }, [isCaretaker])

  // If we came from the caretaker home screen's "Report a problem" button, open the form straight away
  useEffect(() => {
    if (location.state && location.state.add && directory) {
      setAdding(true)
      // Clear the message so a refresh does not open it again
      navigate(location.pathname, { replace: true, state: null })
    }
  }, [location.state, location.pathname, directory, navigate])

  // Load the repairs (called again after every change)
  const load = useCallback(() => {
    setError('')
    getRepairs({ status, property_id: propertyId })
      .then(setReport)
      .catch((err) => setError(err.message))
  }, [status, propertyId])

  // Load them when the page opens or a filter changes
  useEffect(() => {
    load()
  }, [load])

  // The filter buttons, with the number of repairs in each stage
  const filters = report
    ? [
        { key: '', label: 'All', count: report.open_count + report.in_progress_count + report.fixed_count },
        { key: 'open', label: 'Open', count: report.open_count },
        { key: 'in_progress', label: 'In progress', count: report.in_progress_count },
        { key: 'fixed', label: 'Fixed', count: report.fixed_count },
      ]
    : []

  return (
    <div>
      {/* The title and the report button */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-extrabold text-forest-900">Repairs</h1>
          <p className="text-muted">
            {isCaretaker ? 'Report problems and keep them moving.' : 'Every problem, who is fixing it, and what it cost.'}
          </p>
        </div>
        <motion.button
          whileTap={{ scale: 0.96 }}
          onClick={() => setAdding(true)}
          disabled={!directory}
          className="flex shrink-0 items-center gap-2 rounded-xl bg-forest-900 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-forest-900/20 hover:bg-forest-700 disabled:opacity-60"
        >
          <Plus size={18} /> Report
        </motion.button>
      </div>

      {/* If loading failed, show the message and a retry button */}
      {error && (
        <div className="mt-6 rounded-3xl bg-terracotta/10 p-6 text-terracotta">
          <p className="font-semibold">Could not load your repairs</p>
          <p className="mt-1 text-sm">{error}</p>
          <button onClick={load} className="mt-4 flex items-center gap-2 rounded-xl bg-terracotta px-4 py-2 text-sm font-semibold text-white">
            <RefreshCw size={16} /> Try again
          </button>
        </div>
      )}

      {/* While waiting, show grey placeholder boxes */}
      {!error && !report && (
        <div className="mt-6 space-y-3">
          <div className="h-28 animate-pulse rounded-3xl bg-forest-100" />
          <div className="h-24 animate-pulse rounded-2xl bg-forest-100" />
        </div>
      )}

      {report && (
        <>
          {/* The green summary card (caretakers see counts, owners also see what was spent) */}
          <motion.div
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-6 grid grid-cols-3 gap-3 rounded-3xl bg-forest-900 p-5 text-white shadow-xl"
          >
            <div>
              <p className="text-xs text-forest-200">Open</p>
              <p className="font-display text-3xl font-bold">{report.open_count}</p>
            </div>
            <div>
              <p className="text-xs text-forest-200">In progress</p>
              <p className="font-display text-3xl font-bold">{report.in_progress_count}</p>
            </div>
            {isCaretaker ? (
              <div>
                <p className="text-xs text-forest-200">Fixed</p>
                <p className="font-display text-3xl font-bold">{report.fixed_count}</p>
              </div>
            ) : (
              <div>
                <p className="text-xs text-forest-200">Spent this month</p>
                <p className="font-display text-xl font-bold sm:text-3xl">{money(report.cost_this_month)}</p>
              </div>
            )}
          </motion.div>

          {/* The filter buttons and the property dropdown */}
          <div className="mt-5 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div className="flex flex-wrap gap-2">
              {filters.map((item) => (
                <button
                  key={item.key}
                  onClick={() => setStatus(item.key)}
                  className={`rounded-full px-4 py-2 text-sm font-semibold transition ${
                    status === item.key ? 'bg-forest-900 text-white' : 'bg-paper text-forest-700 hover:bg-forest-100'
                  }`}
                >
                  {item.label} <span className="opacity-70">{item.count}</span>
                </button>
              ))}
            </div>
            {directory && directory.properties.length > 1 && (
              <select
                value={propertyId}
                onChange={(e) => setPropertyId(e.target.value)}
                className={`${inputClass} md:w-56`}
                aria-label="Filter by property"
              >
                <option value="">All properties</option>
                {directory.properties.map((prop) => (
                  <option key={prop.property_id} value={prop.property_id}>
                    {prop.name}
                  </option>
                ))}
              </select>
            )}
          </div>

          {/* The list of repairs */}
          {report.items.length === 0 ? (
            <div className="mt-6 flex flex-col items-center rounded-3xl bg-paper p-10 text-center shadow-sm">
              <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-forest-100 text-forest-700">
                <Wrench size={26} />
              </div>
              <p className="mt-4 font-semibold text-forest-900">
                {status || propertyId ? 'Nothing matches that' : 'No repairs reported'}
              </p>
              <p className="mt-1 text-sm text-muted">
                {status || propertyId ? 'Try another filter.' : 'When something breaks, report it here so it does not get forgotten.'}
              </p>
            </div>
          ) : (
            <motion.div
              key={`${status}-${propertyId}`}
              variants={listAnimation}
              initial="hidden"
              animate="show"
              className="mt-5 grid gap-3 md:grid-cols-2"
            >
              {report.items.map((item) => {
                // The label and colors for this repair
                const statusInfo = STATUS_STYLES[item.status]
                const priorityInfo = PRIORITY_STYLES[item.priority]
                return (
                  <motion.button
                    key={item.id}
                    variants={itemAnimation}
                    onClick={() => setEditing(item)}
                    className={`rounded-2xl bg-paper p-4 text-left shadow-sm transition hover:-translate-y-0.5 hover:shadow-md ${
                      item.status === 'fixed' ? 'opacity-75' : ''
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <p className="font-semibold text-forest-900">{item.title}</p>
                      <span className={`shrink-0 rounded-full px-2.5 py-0.5 text-xs font-semibold ${statusInfo.style}`}>
                        {statusInfo.label}
                      </span>
                    </div>
                    <p className="mt-1 flex items-center gap-1.5 text-sm text-muted">
                      <Building2 size={14} className="shrink-0" />
                      <span className="truncate">
                        {item.unit_number ? `Unit ${item.unit_number}` : 'Whole property'} · {item.property_name}
                      </span>
                    </p>
                    {item.description && <p className="mt-2 line-clamp-2 text-sm text-ink/80">{item.description}</p>}
                    <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted">
                      {priorityInfo && (
                        <span className={`rounded-full px-2 py-0.5 font-semibold ${priorityInfo.style}`}>{priorityInfo.label}</span>
                      )}
                      <span>
                        {item.status === 'fixed' && item.resolved_on
                          ? `Fixed ${formatDate(item.resolved_on)}`
                          : `Reported ${age(item.created_at)}`}
                        {item.reported_by_name ? ` by ${item.reported_by_name.split(' ')[0]}` : ''}
                      </span>
                      {item.cost != null && <span className="font-semibold text-forest-900">{money(item.cost)}</span>}
                    </div>
                    {item.contractor_name && (
                      <p className="mt-2 flex items-center gap-1.5 text-xs text-forest-700">
                        <Phone size={13} className="shrink-0" />
                        {item.contractor_name}
                        {item.contractor_phone ? ` · ${phoneLocal(item.contractor_phone)}` : ''}
                      </p>
                    )}
                  </motion.button>
                )
              })}
            </motion.div>
          )}
        </>
      )}

      {/* Report a problem */}
      <Modal open={adding} title="Report a problem" onClose={() => setAdding(false)}>
        {directory && (
          <RepairForm
            directory={directory}
            submitLabel="Report problem"
            onCancel={() => setAdding(false)}
            onSubmit={async (body) => {
              await createRepair(body)
              setAdding(false)
              load()
            }}
          />
        )}
      </Modal>

      {/* Edit a repair */}
      <Modal open={editing !== null} title="Update repair" onClose={() => setEditing(null)}>
        {editing && directory && (
          <RepairForm
            key={editing.id}
            directory={directory}
            initial={editing}
            canSetCost={!isCaretaker}
            submitLabel="Save changes"
            onCancel={() => setEditing(null)}
            onSubmit={async (body) => {
              await updateRepair(editing.id, body)
              setEditing(null)
              load()
            }}
            // Only owners can delete a repair
            onDelete={
              isCaretaker
                ? undefined
                : () => {
                    // Close the edit window and ask "are you sure?"
                    setDeleting(editing)
                    setEditing(null)
                  }
            }
          />
        )}
      </Modal>

      {/* Delete a repair */}
      <ConfirmDialog
        open={deleting !== null}
        title="Delete this repair?"
        message={deleting ? `Delete "${deleting.title}"? This cannot be undone.` : ''}
        confirmLabel="Delete"
        onClose={() => setDeleting(null)}
        onConfirm={async () => {
          await deleteRepair(deleting.id)
          setDeleting(null)
          load()
        }}
      />
    </div>
  )
}