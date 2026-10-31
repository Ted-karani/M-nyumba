// Import the React tools we need
import { useCallback, useEffect, useState } from 'react'
// Import the animation tool
import { motion } from 'framer-motion'
// Import the icons we use
import { Check, Copy, Newspaper, Pencil, Pin, Plus, RefreshCw, Trash2 } from 'lucide-react'
// Import our own files
import { createNotice, deleteNotice, getNotices, updateNotice } from '../api'
import { formatDate } from '../format'
import ConfirmDialog from '../components/ConfirmDialog'
import Modal from '../components/Modal'
import NoticeForm from '../components/NoticeForm'

// How the list appears: the cards come in one after another
const listAnimation = { hidden: {}, show: { transition: { staggerChildren: 0.05 } } }
// How each card appears: fade in while sliding up
const itemAnimation = { hidden: { opacity: 0, y: 14 }, show: { opacity: 1, y: 0 } }

// The page where owners post announcements for their tenants
export default function Notices() {
  // The data from the backend (nothing until it arrives)
  const [data, setData] = useState(null)
  // The error message, if loading failed
  const [error, setError] = useState('')
  // Which pop-ups are open (each holds the thing it is about)
  const [adding, setAdding] = useState(false)
  const [editing, setEditing] = useState(null)
  const [deleting, setDeleting] = useState(null)
  // The id of the notice whose text was just copied
  const [copiedId, setCopiedId] = useState(null)

  // Load the notices
  const load = useCallback(() => {
    setError('')
    getNotices()
      .then(setData)
      .catch((err) => setError(err.message))
  }, [])

  // Load them when the page opens
  useEffect(() => {
    load()
  }, [load])

  // Copy a notice as text, to paste into a WhatsApp group
  async function copyText(notice) {
    try {
      await navigator.clipboard.writeText(`${notice.title}\n\n${notice.body}`)
      setCopiedId(notice.id)
      setTimeout(() => setCopiedId(null), 1800)
    } catch {
      // If copying is blocked, nothing happens
    }
  }

  return (
    <div>
      {/* The title and the add button */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-extrabold text-forest-900">Notice board</h1>
          <p className="text-muted">Tenants with portal access see these when they open EstateLoom.</p>
        </div>
        <motion.button whileTap={{ scale: 0.96 }} onClick={() => setAdding(true)} className="flex shrink-0 items-center gap-2 rounded-xl bg-forest-900 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-forest-900/20 hover:bg-forest-700">
          <Plus size={18} /> New notice
        </motion.button>
      </div>

      {/* If loading failed, show the message and a retry button */}
      {error && (
        <div className="mt-6 rounded-3xl bg-terracotta/10 p-6 text-terracotta">
          <p className="font-semibold">Could not load the notices</p>
          <p className="mt-1 text-sm">{error}</p>
          <button onClick={load} className="mt-4 flex items-center gap-2 rounded-xl bg-terracotta px-4 py-2 text-sm font-semibold text-white">
            <RefreshCw size={16} /> Try again
          </button>
        </div>
      )}

      {/* While waiting, show grey placeholder boxes */}
      {!error && !data && (
        <div className="mt-6 space-y-3">
          <div className="h-28 animate-pulse rounded-2xl bg-forest-100" />
          <div className="h-28 animate-pulse rounded-2xl bg-forest-100" />
        </div>
      )}

      {/* Nothing posted yet */}
      {data && data.notices.length === 0 && (
        <div className="mt-8 flex flex-col items-center rounded-3xl bg-paper p-10 text-center shadow-sm">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-forest-100 text-forest-700">
            <Newspaper size={26} />
          </div>
          <p className="mt-4 font-semibold text-forest-900">No notices yet</p>
          <p className="mt-1 max-w-xs text-sm text-muted">Post things like a water shutdown, the rent due date, or house rules.</p>
        </div>
      )}

      {/* The notices */}
      {data && data.notices.length > 0 && (
        <motion.div variants={listAnimation} initial="hidden" animate="show" className="mt-6 grid gap-3 md:grid-cols-2">
          {data.notices.map((notice) => (
            <motion.div key={notice.id} variants={itemAnimation} className={`rounded-2xl bg-paper p-5 shadow-sm ${notice.expired ? 'opacity-60' : ''}`}>
              <div className="flex items-start justify-between gap-3">
                <p className="font-semibold text-forest-900">{notice.title}</p>
                {notice.pinned && <Pin size={16} className="mt-0.5 shrink-0 text-gold" />}
              </div>
              <p className="mt-2 line-clamp-4 whitespace-pre-line text-sm text-ink/80">{notice.body}</p>
              <p className="mt-3 text-xs text-muted">
                {notice.property_name ? `Only ${notice.property_name}` : 'All tenants'} · posted {formatDate(notice.posted_on)}
                {notice.expires_on ? ` · ${notice.expired ? 'ended' : 'until'} ${formatDate(notice.expires_on)}` : ''}
              </p>
              <div className="mt-3 flex gap-2">
                <button onClick={() => copyText(notice)} className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-forest-100 py-2 text-xs font-semibold text-forest-700 hover:bg-forest-200">
                  {copiedId === notice.id ? <Check size={14} /> : <Copy size={14} />} {copiedId === notice.id ? 'Copied' : 'Copy for WhatsApp'}
                </button>
                <button onClick={() => setEditing(notice)} aria-label="Edit notice" className="rounded-xl bg-forest-100 px-3 text-forest-700 hover:bg-forest-200">
                  <Pencil size={15} />
                </button>
                <button onClick={() => setDeleting(notice)} aria-label="Delete notice" className="rounded-xl bg-terracotta/10 px-3 text-terracotta hover:bg-terracotta hover:text-white">
                  <Trash2 size={15} />
                </button>
              </div>
            </motion.div>
          ))}
        </motion.div>
      )}

      {/* Post a notice */}
      <Modal open={adding} title="New notice" onClose={() => setAdding(false)}>
        {data && (
          <NoticeForm
            properties={data.properties}
            onCancel={() => setAdding(false)}
            onSubmit={async (body) => {
              await createNotice(body)
              setAdding(false)
              load()
            }}
          />
        )}
      </Modal>

      {/* Edit a notice */}
      <Modal open={editing !== null} title="Edit notice" onClose={() => setEditing(null)}>
        {editing && data && (
          <NoticeForm
            key={editing.id}
            notice={editing}
            properties={data.properties}
            onCancel={() => setEditing(null)}
            onSubmit={async (body) => {
              await updateNotice(editing.id, body)
              setEditing(null)
              load()
            }}
          />
        )}
      </Modal>

      {/* Delete a notice */}
      <ConfirmDialog
        open={deleting !== null}
        title="Delete this notice?"
        message={deleting ? `Delete "${deleting.title}"? Tenants will no longer see it.` : ''}
        confirmLabel="Delete"
        onClose={() => setDeleting(null)}
        onConfirm={async () => {
          await deleteNotice(deleting.id)
          setDeleting(null)
          load()
        }}
      />
    </div>
  )
}