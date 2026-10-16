// Import the React tools we need
import { useCallback, useEffect, useState } from 'react'
// Import the animation tool
import { motion } from 'framer-motion'
// Import the icons we use
import { CalendarCheck, Check, Pencil, Plus, RefreshCw, Repeat, Undo2 } from 'lucide-react'
// Import our own files
import { completeTask, createTask, deleteTask, getDashboard, getTasks, updateTask } from '../api'
import { formatDate } from '../format'
import ConfirmDialog from '../components/ConfirmDialog'
import Modal from '../components/Modal'
import TaskForm from '../components/TaskForm'

// How the list appears: the cards come in one after another
const listAnimation = { hidden: {}, show: { transition: { staggerChildren: 0.04 } } }
// How each card appears: fade in while sliding up
const itemAnimation = { hidden: { opacity: 0, y: 12 }, show: { opacity: 1, y: 0 } }

// The words for each kind of repeat
const REPEAT_WORDS = { monthly: 'Every month', quarterly: 'Every 3 months', yearly: 'Every year' }

// Write how far away a due date is
function dueText(days) {
  if (days < 0) return `${-days} day${days === -1 ? '' : 's'} overdue`
  if (days === 0) return 'Due today'
  return `Due in ${days} day${days === 1 ? '' : 's'}`
}

// The page that lists all the tasks
export default function Tasks() {
  // The tasks and the properties (nothing until they arrive)
  const [tasks, setTasks] = useState(null)
  const [properties, setProperties] = useState([])
  // The error and success messages
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  // Whether finished tasks are shown
  const [showDone, setShowDone] = useState(false)
  // Which pop-ups are open
  const [adding, setAdding] = useState(false)
  const [editing, setEditing] = useState(null)
  const [deleting, setDeleting] = useState(null)

  // Load the properties once, for the form
  useEffect(() => {
    getDashboard()
      .then((dashboard) => setProperties(dashboard.properties))
      .catch(() => setProperties([]))
  }, [])

  // Load all the tasks (called again after every change)
  const load = useCallback(() => {
    setError('')
    getTasks('all')
      .then(setTasks)
      .catch((err) => setError(err.message))
  }, [])

  // Load them when the page opens
  useEffect(() => {
    load()
  }, [load])

  // Mark a task done
  async function handleDone(task) {
    setError('')
    try {
      const updated = await completeTask(task.id)
      // Say what happens next
      setMessage(
        task.repeat === 'none' ? `"${task.title}" is done.` : `"${task.title}" is done. Next due ${formatDate(updated.due_date)}.`
      )
      load()
    } catch (err) {
      setError(err.message)
    }
  }

  // Bring a finished task back
  async function handleReopen(task) {
    setError('')
    try {
      await updateTask(task.id, { is_done: false })
      setMessage('')
      load()
    } catch (err) {
      setError(err.message)
    }
  }

  // Split the tasks into groups
  const open = tasks ? tasks.filter((task) => !task.is_done) : []
  const groups = [
    { key: 'overdue', title: 'Overdue', color: 'text-terracotta', items: open.filter((task) => task.status === 'overdue') },
    { key: 'soon', title: 'Coming up (next 2 weeks)', color: 'text-amber', items: open.filter((task) => task.status === 'soon') },
    { key: 'later', title: 'Later', color: 'text-forest-700', items: open.filter((task) => task.status === 'later') },
  ]
  // The finished tasks, the latest finished first
  const done = tasks
    ? tasks.filter((task) => task.is_done).sort((a, b) => (b.last_done_on || '').localeCompare(a.last_done_on || ''))
    : []

  // One card for one task
  const renderTask = (task) => (
    <motion.div key={task.id} variants={itemAnimation} className="flex items-center gap-3 rounded-2xl bg-paper p-4 shadow-sm">
      {/* The button that marks it done (or brings it back) */}
      {task.is_done ? (
        <button onClick={() => handleReopen(task)} aria-label="Reopen this task" className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-forest-100 text-forest-700 hover:bg-forest-200">
          <Undo2 size={18} />
        </button>
      ) : (
        <button onClick={() => handleDone(task)} aria-label="Mark as done" className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border-2 border-forest-200 text-forest-500 transition hover:border-forest-500 hover:bg-forest-500 hover:text-white">
          <Check size={18} />
        </button>
      )}
      <div className="min-w-0 flex-1">
        <p className={`truncate font-semibold ${task.is_done ? 'text-muted line-through' : 'text-forest-900'}`}>{task.title}</p>
        <p className="truncate text-xs text-muted">
          {task.is_done ? `Done ${task.last_done_on ? formatDate(task.last_done_on) : ''}` : `${formatDate(task.due_date)} · ${dueText(task.days_left)}`}
          {task.property_name ? ` · ${task.property_name}` : ''}
        </p>
        {task.repeat !== 'none' && (
          <p className="mt-1 flex items-center gap-1 text-xs text-forest-700">
            <Repeat size={12} /> {REPEAT_WORDS[task.repeat]}
          </p>
        )}
      </div>
      <button onClick={() => setEditing(task)} aria-label="Edit this task" className="shrink-0 rounded-lg p-2 text-muted hover:bg-forest-100 hover:text-forest-900">
        <Pencil size={16} />
      </button>
    </motion.div>
  )

  return (
    <div>
      {/* The title and the add button */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-extrabold text-forest-900">Tasks</h1>
          <p className="text-muted">Tax dates, renewals, and jobs that repeat.</p>
        </div>
        <motion.button
          whileTap={{ scale: 0.96 }}
          onClick={() => setAdding(true)}
          className="flex shrink-0 items-center gap-2 rounded-xl bg-forest-900 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-forest-900/20 hover:bg-forest-700"
        >
          <Plus size={18} /> Add
        </motion.button>
      </div>

      {/* The messages */}
      {message && (
        <div role="status" className="mt-4 rounded-xl bg-forest-100 px-4 py-3 text-sm font-medium text-forest-700">
          {message}
        </div>
      )}
      {error && (
        <div className="mt-6 rounded-3xl bg-terracotta/10 p-6 text-terracotta">
          <p className="font-semibold">Something went wrong</p>
          <p className="mt-1 text-sm">{error}</p>
          <button onClick={load} className="mt-4 flex items-center gap-2 rounded-xl bg-terracotta px-4 py-2 text-sm font-semibold text-white">
            <RefreshCw size={16} /> Try again
          </button>
        </div>
      )}

      {/* While waiting, show grey placeholder boxes */}
      {!error && !tasks && (
        <div className="mt-6 space-y-3">
          <div className="h-20 animate-pulse rounded-2xl bg-forest-100" />
          <div className="h-20 animate-pulse rounded-2xl bg-forest-100" />
        </div>
      )}

      {/* If there are no tasks at all, invite the person to add one */}
      {tasks && tasks.length === 0 && (
        <div className="mt-8 flex flex-col items-center rounded-3xl bg-paper p-10 text-center shadow-sm">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-forest-100 text-forest-700">
            <CalendarCheck size={26} />
          </div>
          <p className="mt-4 font-semibold text-forest-900">No tasks yet</p>
          <p className="mt-1 max-w-xs text-sm text-muted">Add the dates you must not miss. Repeating tasks move on by themselves when you mark them done.</p>
        </div>
      )}

      {/* The open tasks, in groups */}
      {tasks && groups.map((group) =>
        group.items.length > 0 ? (
          <div key={group.key} className="mt-6">
            <h2 className={`mb-3 text-sm font-bold uppercase tracking-wide ${group.color}`}>
              {group.title} <span className="font-medium text-muted">({group.items.length})</span>
            </h2>
            <motion.div variants={listAnimation} initial="hidden" animate="show" className="grid gap-3 md:grid-cols-2">
              {group.items.map(renderTask)}
            </motion.div>
          </div>
        ) : null
      )}

      {/* The finished tasks */}
      {done.length > 0 && (
        <div className="mt-8">
          <button onClick={() => setShowDone(!showDone)} className="text-sm font-semibold text-forest-700 hover:underline">
            {showDone ? 'Hide' : 'Show'} finished tasks ({done.length})
          </button>
          {showDone && (
            <motion.div variants={listAnimation} initial="hidden" animate="show" className="mt-3 grid gap-3 md:grid-cols-2">
              {done.map(renderTask)}
            </motion.div>
          )}
        </div>
      )}

      {/* Add a task */}
      <Modal open={adding} title="Add a task" onClose={() => setAdding(false)}>
        <TaskForm
          properties={properties}
          submitLabel="Add task"
          onCancel={() => setAdding(false)}
          onSubmit={async (body) => {
            await createTask(body)
            setAdding(false)
            setMessage('')
            load()
          }}
        />
      </Modal>

      {/* Edit a task */}
      <Modal open={editing !== null} title="Edit task" onClose={() => setEditing(null)}>
        {editing && (
          <TaskForm
            key={editing.id}
            properties={properties}
            initial={editing}
            submitLabel="Save changes"
            onCancel={() => setEditing(null)}
            onSubmit={async (body) => {
              await updateTask(editing.id, body)
              setEditing(null)
              setMessage('')
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

      {/* Delete a task */}
      <ConfirmDialog
        open={deleting !== null}
        title="Delete this task?"
        message={deleting ? `Delete "${deleting.title}"? This cannot be undone.` : ''}
        confirmLabel="Delete"
        onClose={() => setDeleting(null)}
        onConfirm={async () => {
          await deleteTask(deleting.id)
          setDeleting(null)
          load()
        }}
      />
    </div>
  )
}