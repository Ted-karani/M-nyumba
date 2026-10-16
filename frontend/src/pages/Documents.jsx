// Import the React tools we need
import { useCallback, useEffect, useState } from 'react'
// Import the animation tool
import { motion } from 'framer-motion'
// Import the icons we use
import { ExternalLink, FileText, FolderOpen, Pencil, Plus, RefreshCw } from 'lucide-react'
// Import our own files
import { deleteDocument, getDashboard, getDocuments, getTenants, openFile, updateDocument, uploadDocument } from '../api'
import { DOCUMENT_KINDS, expiryText, fileSize, kindLabel } from '../documents'
import { formatDate } from '../format'
import AuthImage from '../components/AuthImage'
import ConfirmDialog from '../components/ConfirmDialog'
import DocumentForm from '../components/DocumentForm'
import { inputClass } from '../components/Field'
import Modal from '../components/Modal'

// How the list appears: the cards come in one after another
const listAnimation = { hidden: {}, show: { transition: { staggerChildren: 0.04 } } }
// How each card appears: fade in while sliding up
const itemAnimation = { hidden: { opacity: 0, y: 12 } , show: { opacity: 1, y: 0 } }

// The page that lists all the documents
export default function Documents() {
  // The filters: which kind, which property, and whether to show only the ones about to expire
  const [kind, setKind] = useState('')
  const [propertyId, setPropertyId] = useState('')
  const [expiring, setExpiring] = useState(false)
  // The data from the backend (nothing until it arrives)
  const [documents, setDocuments] = useState(null)
  const [properties, setProperties] = useState([])
  const [tenants, setTenants] = useState([])
  // The error message, if something failed
  const [error, setError] = useState('')
  // Which pop-ups are open
  const [adding, setAdding] = useState(false)
  const [editing, setEditing] = useState(null)
  const [deleting, setDeleting] = useState(null)

  // Load the properties and tenants once, for the forms and the filter
  useEffect(() => {
    getDashboard()
      .then((dashboard) => setProperties(dashboard.properties))
      .catch(() => setProperties([]))
    getTenants()
      .then(setTenants)
      .catch(() => setTenants([]))
  }, [])

  // Load the documents (called again after every change)
  const load = useCallback(() => {
    setError('')
    getDocuments({ kind, property_id: propertyId, expiring: expiring ? 'true' : '' })
      .then(setDocuments)
      .catch((err) => setError(err.message))
  }, [kind, propertyId, expiring])

  // Load them when the page opens or a filter changes
  useEffect(() => {
    load()
  }, [load])

  // Open a document in a new tab
  async function handleOpen(document) {
    setError('')
    try {
      await openFile(`/documents/${document.id}/file`, document.original_name)
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div>
      {/* The title and the upload button */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-extrabold text-forest-900">Documents</h1>
          <p className="text-muted">Leases, title deeds, permits and photos, safe in one place.</p>
        </div>
        <motion.button
          whileTap={{ scale: 0.96 }}
          onClick={() => setAdding(true)}
          className="flex shrink-0 items-center gap-2 rounded-xl bg-forest-900 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-forest-900/20 hover:bg-forest-700"
        >
          <Plus size={18} /> Upload
        </motion.button>
      </div>

      {/* The filters */}
      <div className="mt-6 grid gap-3 sm:grid-cols-2">
        <select value={kind} onChange={(e) => setKind(e.target.value)} className={inputClass} aria-label="Filter by kind">
          <option value="">All kinds</option>
          {DOCUMENT_KINDS.map((item) => (
            <option key={item.key} value={item.key}>
              {item.label}
            </option>
          ))}
        </select>
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
      </div>
      <button
        onClick={() => setExpiring(!expiring)}
        className={`mt-3 rounded-full px-4 py-2 text-sm font-semibold transition ${expiring ? 'bg-forest-900 text-white' : 'bg-paper text-forest-700 hover:bg-forest-100'}`}
      >
        Expiring soon or expired
      </button>

      {/* The error message, if something failed */}
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
      {!error && !documents && (
        <div className="mt-6 space-y-3">
          <div className="h-20 animate-pulse rounded-2xl bg-forest-100" />
          <div className="h-20 animate-pulse rounded-2xl bg-forest-100" />
        </div>
      )}

      {/* If there are no documents, say so */}
      {documents && documents.length === 0 && (
        <div className="mt-6 flex flex-col items-center rounded-3xl bg-paper p-10 text-center shadow-sm">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-forest-100 text-forest-700">
            <FolderOpen size={26} />
          </div>
          <p className="mt-4 font-semibold text-forest-900">{kind || propertyId || expiring ? 'Nothing matches that' : 'No documents yet'}</p>
          <p className="mt-1 max-w-xs text-sm text-muted">
            {kind || propertyId || expiring ? 'Try another filter.' : 'Upload a title deed, a lease, or a permit, and add its expiry date so you never miss a renewal.'}
          </p>
        </div>
      )}

      {/* The list of documents */}
      {documents && documents.length > 0 && (
        <motion.div key={`${kind}-${propertyId}-${expiring}`} variants={listAnimation} initial="hidden" animate="show" className="mt-5 grid gap-3 md:grid-cols-2">
          {documents.map((doc) => {
            // Is it a picture? Then we can show a small preview
            const isImage = doc.content_type.startsWith('image/')
            // The words and color for the expiry date
            const days = doc.days_to_expiry
            const expiryColor = days === null ? '' : days < 0 ? 'bg-terracotta/15 text-terracotta' : days <= 30 ? 'bg-amber/20 text-amber' : 'bg-forest-100 text-forest-700'
            return (
              <motion.div key={doc.id} variants={itemAnimation} className="flex gap-3 rounded-2xl bg-paper p-4 shadow-sm">
                {/* The preview or an icon */}
                <button onClick={() => handleOpen(doc)} aria-label={`Open ${doc.title}`} className="shrink-0">
                  {isImage ? (
                    <AuthImage path={`/documents/${doc.id}/file`} alt={doc.title} className="h-14 w-14 rounded-xl object-cover" />
                  ) : (
                    <span className="flex h-14 w-14 items-center justify-center rounded-xl bg-forest-100 text-forest-700">
                      <FileText size={24} />
                    </span>
                  )}
                </button>
                <div className="min-w-0 flex-1">
                  <button onClick={() => handleOpen(doc)} className="block max-w-full truncate text-left font-semibold text-forest-900 hover:underline">
                    {doc.title}
                  </button>
                  <p className="truncate text-xs text-muted">
                    {kindLabel(doc.kind)} · {fileSize(doc.size_bytes)}
                  </p>
                  <p className="truncate text-xs text-muted">
                    {[doc.property_name, doc.tenant_name].filter(Boolean).join(' · ') || 'Not linked to a property or tenant'}
                  </p>
                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    {days !== null && <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${expiryColor}`}>{expiryText(days)}</span>}
                    <span className="text-xs text-muted">Added {formatDate(doc.created_at.slice(0, 10))}</span>
                  </div>
                </div>
                <div className="flex shrink-0 flex-col gap-1">
                  <button onClick={() => handleOpen(doc)} aria-label="Open" className="rounded-lg p-2 text-muted hover:bg-forest-100 hover:text-forest-900">
                    <ExternalLink size={16} />
                  </button>
                  <button onClick={() => setEditing(doc)} aria-label="Edit details" className="rounded-lg p-2 text-muted hover:bg-forest-100 hover:text-forest-900">
                    <Pencil size={16} />
                  </button>
                </div>
              </motion.div>
            )
          })}
        </motion.div>
      )}

      {/* Upload a document */}
      <Modal open={adding} title="Upload a document" onClose={() => setAdding(false)}>
        <DocumentForm
          properties={properties}
          tenants={tenants}
          submitLabel="Upload"
          onCancel={() => setAdding(false)}
          onSubmit={async (form) => {
            await uploadDocument(form)
            setAdding(false)
            load()
          }}
        />
      </Modal>

      {/* Edit a document's details */}
      <Modal open={editing !== null} title="Edit details" onClose={() => setEditing(null)}>
        {editing && (
          <DocumentForm
            key={editing.id}
            properties={properties}
            tenants={tenants}
            initial={editing}
            submitLabel="Save changes"
            onCancel={() => setEditing(null)}
            onSubmit={async (body) => {
              await updateDocument(editing.id, body)
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

      {/* Delete a document */}
      <ConfirmDialog
        open={deleting !== null}
        title="Delete this document?"
        message={deleting ? `Delete "${deleting.title}" and its file? This cannot be undone.` : ''}
        confirmLabel="Delete"
        onClose={() => setDeleting(null)}
        onConfirm={async () => {
          await deleteDocument(deleting.id)
          setDeleting(null)
          load()
        }}
      />
    </div>
  )
}