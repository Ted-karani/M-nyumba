// Import the React tools we need
import { useCallback, useEffect, useState } from 'react'
// Import the animation tool
import { motion } from 'framer-motion'
// Import the icons we use
import { Building2, Check, Copy, MessageCircle, RefreshCw, UserPlus, Users } from 'lucide-react'
// Import our own files
import { createCaretaker, getCaretakers, getDashboard, updateCaretaker } from '../api'
import { initials, phoneLocal } from '../format'
import CaretakerForm from '../components/CaretakerForm'
import Modal from '../components/Modal'

// How the list appears: the cards come in one after another
const listAnimation = { hidden: {}, show: { transition: { staggerChildren: 0.06 } } }
// How each card appears: fade in while sliding up
const itemAnimation = { hidden: { opacity: 0, y: 14 } , show: { opacity: 1, y: 0 } }

// The page where owners manage their caretakers
export default function Team() {
  // The data from the backend (nothing until it arrives)
  const [caretakers, setCaretakers] = useState(null)
  const [properties, setProperties] = useState([])
  // The error message, if loading failed
  const [error, setError] = useState('')
  // Which pop-ups are open
  const [adding, setAdding] = useState(false)
  const [editing, setEditing] = useState(null)
  // The login details of a caretaker who was just added (shown once)
  const [credentials, setCredentials] = useState(null)
  // True for a moment after the details were copied
  const [copied, setCopied] = useState(false)

  // Load the caretakers and the properties
  const load = useCallback(() => {
    setError('')
    Promise.all([getCaretakers(), getDashboard()])
      .then(([team, dashboard]) => {
        setCaretakers(team)
        setProperties(dashboard.properties)
      })
      .catch((err) => setError(err.message))
  }, [])

  // Load them when the page opens
  useEffect(() => {
    load()
  }, [load])

  // The message the owner can send to the new caretaker
  const shareText = credentials
    ? `Hello ${credentials.name.split(' ')[0]}, your EstateLoom login is ready.\nEmail: ${credentials.email}\nPassword: ${credentials.password}`
    : ''

  // Copy the login details to the clipboard
  async function copyDetails() {
    try {
      await navigator.clipboard.writeText(shareText)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // If copying is blocked, the details are still on the screen to copy by hand
    }
  }

  return (
    <div>
      {/* The title and the add button */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-extrabold text-forest-900">Team</h1>
          <p className="text-muted">Caretakers who look after your properties.</p>
        </div>
        <motion.button
          whileTap={{ scale: 0.96 }}
          onClick={() => setAdding(true)}
          className="flex shrink-0 items-center gap-2 rounded-xl bg-forest-900 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-forest-900/20 hover:bg-forest-700"
        >
          <UserPlus size={18} /> Add caretaker
        </motion.button>
      </div>

      {/* A short reminder of what caretakers can and cannot do */}
      <p className="mt-4 rounded-2xl bg-forest-100 px-4 py-3 text-sm text-forest-700">
        Caretakers can see their properties' units and tenants, and report and update repairs. They never see money,
        payments, or other properties.
      </p>

      {/* If loading failed, show the message and a retry button */}
      {error && (
        <div className="mt-6 rounded-3xl bg-terracotta/10 p-6 text-terracotta">
          <p className="font-semibold">Could not load your team</p>
          <p className="mt-1 text-sm">{error}</p>
          <button onClick={load} className="mt-4 flex items-center gap-2 rounded-xl bg-terracotta px-4 py-2 text-sm font-semibold text-white">
            <RefreshCw size={16} /> Try again
          </button>
        </div>
      )}

      {/* While waiting, show grey placeholder boxes */}
      {!error && !caretakers && (
        <div className="mt-6 space-y-3">
          <div className="h-24 animate-pulse rounded-2xl bg-forest-100" />
          <div className="h-24 animate-pulse rounded-2xl bg-forest-100" />
        </div>
      )}

      {/* If there are no caretakers yet, invite the owner to add one */}
      {caretakers && caretakers.length === 0 && (
        <div className="mt-8 flex flex-col items-center rounded-3xl bg-paper p-10 text-center shadow-sm">
          <div className="flex h-16 w-16 items-center justify-center rounded-3xl bg-forest-100 text-forest-700">
            <Users size={28} />
          </div>
          <h2 className="mt-5 text-xl font-bold text-forest-900">No caretakers yet</h2>
          <p className="mt-1 max-w-xs text-muted">Give each caretaker their own login, limited to the properties they look after.</p>
          <button
            onClick={() => setAdding(true)}
            className="mt-5 flex items-center gap-2 rounded-xl bg-forest-900 px-5 py-3 text-sm font-semibold text-white hover:bg-forest-700"
          >
            <UserPlus size={18} /> Add caretaker
          </button>
        </div>
      )}

      {/* The list of caretakers */}
      {caretakers && caretakers.length > 0 && (
        <motion.div variants={listAnimation} initial="hidden" animate="show" className="mt-6 grid gap-3 md:grid-cols-2">
          {caretakers.map((person) => (
            <motion.button
              key={person.id}
              variants={itemAnimation}
              onClick={() => setEditing(person)}
              className={`rounded-2xl bg-paper p-4 text-left shadow-sm transition hover:-translate-y-0.5 hover:shadow-md ${
                person.is_active ? '' : 'opacity-70'
              }`}
            >
              <div className="flex items-center gap-4">
                <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-forest-100 font-display font-bold text-forest-700">
                  {initials(person.full_name)}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate font-semibold text-forest-900">{person.full_name}</p>
                  <p className="truncate text-sm text-muted">{person.email}</p>
                  {person.phone && <p className="text-xs text-muted">{phoneLocal(person.phone)}</p>}
                </div>
                <span
                  className={`shrink-0 rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                    person.is_active ? 'bg-forest-100 text-forest-700' : 'bg-terracotta/15 text-terracotta'
                  }`}
                >
                  {person.is_active ? 'Active' : 'Disabled'}
                </span>
              </div>
              {/* The properties they look after */}
              <div className="mt-3 flex flex-wrap gap-2">
                {person.properties.length === 0 ? (
                  <span className="text-xs text-muted">No properties assigned</span>
                ) : (
                  person.properties.map((prop) => (
                    <span key={prop.id} className="flex items-center gap-1 rounded-full bg-cream px-2.5 py-1 text-xs font-medium text-forest-900">
                      <Building2 size={12} /> {prop.name}
                    </span>
                  ))
                )}
              </div>
            </motion.button>
          ))}
        </motion.div>
      )}

      {/* Add a caretaker */}
      <Modal open={adding} title="Add caretaker" onClose={() => setAdding(false)}>
        <CaretakerForm
          properties={properties}
          submitLabel="Add caretaker"
          onCancel={() => setAdding(false)}
          onSubmit={async (body) => {
            const created = await createCaretaker(body)
            setAdding(false)
            // Show the login details once, because the password cannot be read back later
            setCredentials({ name: created.full_name, email: created.email, phone: created.phone, password: body.password })
            load()
          }}
        />
      </Modal>

      {/* Edit a caretaker */}
      <Modal open={editing !== null} title="Edit caretaker" onClose={() => setEditing(null)}>
        {editing && (
          <CaretakerForm
            key={editing.id}
            properties={properties}
            initial={editing}
            submitLabel="Save changes"
            onCancel={() => setEditing(null)}
            onSubmit={async (body) => {
              await updateCaretaker(editing.id, body)
              // If a new password was set, show it once so it can be sent
              if (body.password) {
                setCredentials({ name: editing.full_name, email: editing.email, phone: body.phone, password: body.password })
              }
              setEditing(null)
              load()
            }}
          />
        )}
      </Modal>

      {/* The login details, shown once */}
      <Modal open={credentials !== null} title="Login details" onClose={() => setCredentials(null)}>
        {credentials && (
          <div>
            <p className="text-sm text-muted">
              Send these to {credentials.name.split(' ')[0]}. <span className="font-semibold text-forest-900">The password is only shown now</span>
              , but you can always set a new one.
            </p>
            <div className="mt-4 space-y-3 rounded-2xl bg-forest-100 p-4">
              <div>
                <p className="text-xs text-forest-700">Email</p>
                <p className="break-all font-semibold text-forest-900">{credentials.email}</p>
              </div>
              <div>
                <p className="text-xs text-forest-700">Password</p>
                <p className="font-mono text-lg font-bold tracking-wider text-forest-900">{credentials.password}</p>
              </div>
            </div>
            <div className="mt-4 flex flex-col gap-2 sm:flex-row">
              <button
                onClick={copyDetails}
                className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-forest-900 py-3 text-sm font-semibold text-white hover:bg-forest-700"
              >
                {copied ? <Check size={16} /> : <Copy size={16} />} {copied ? 'Copied' : 'Copy details'}
              </button>
              {credentials.phone && (
                <a
                  href={`https://wa.me/${credentials.phone}?text=${encodeURIComponent(shareText)}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-forest-500 py-3 text-sm font-semibold text-white hover:bg-forest-700"
                >
                  <MessageCircle size={16} /> Send on WhatsApp
                </a>
              )}
            </div>
            <button
              onClick={() => setCredentials(null)}
              className="mt-3 w-full rounded-xl bg-forest-100 py-3 text-sm font-semibold text-forest-700 hover:bg-forest-200"
            >
              Done
            </button>
          </div>
        )}
      </Modal>
    </div>
  )
}