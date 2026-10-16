// Import the React tool for remembering values
import { useState } from 'react'
// Import the icons we use
import { FileUp, Loader2, Trash2 } from 'lucide-react'
// Import our own files
import { Field, inputClass } from './Field'
import { ACCEPT, DOCUMENT_KINDS, MAX_FILE_BYTES, fileSize } from '../documents'

// The form for uploading a document, or for editing the details of one
export default function DocumentForm({ properties, tenants, initial, submitLabel, onSubmit, onCancel, onDelete }) {
  // Are we editing an existing document? (then there is no file to choose)
  const isEdit = Boolean(initial)
  // What the person has typed so far
  const [file, setFile] = useState(null)
  const [title, setTitle] = useState(initial?.title ?? '')
  const [kind, setKind] = useState(initial?.kind ?? 'other')
  const [propertyId, setPropertyId] = useState('')
  const [tenantId, setTenantId] = useState('')
  const [expiresOn, setExpiresOn] = useState(initial?.expires_on ?? '')
  // The error message to show (empty means none)
  const [error, setError] = useState('')
  // True while we wait for the backend
  const [busy, setBusy] = useState(false)

  // Check a chosen file before we try to send it
  function handleFile(event) {
    const picked = event.target.files[0]
    if (!picked) return
    setError('')
    // The ending must be one we accept
    const ending = (picked.name.toLowerCase().match(/\.[a-z0-9]+$/) || [''])[0]
    if (!ACCEPT.split(',').includes(ending)) {
      setError('This file type is not allowed. Use PDF, JPG, PNG, WebP, Word, or Excel.')
      setFile(null)
      return
    }
    // It must not be too big
    if (picked.size > MAX_FILE_BYTES) {
      setError(`This file is too large (${fileSize(picked.size)}). The limit is 10 MB.`)
      setFile(null)
      return
    }
    setFile(picked)
    // If no title was typed yet, use the file's name
    if (!title) setTitle(picked.name.replace(/\.[^.]+$/, ''))
  }

  // Run when the form is sent
  async function handleSubmit(event) {
    // Stop the page from reloading
    event.preventDefault()
    // Clear any old error
    setError('')
    // A new document needs a file
    if (!isEdit && !file) {
      setError('Choose a file first.')
      return
    }
    // Show the loading state
    setBusy(true)
    try {
      if (isEdit) {
        // Send the changed details
        await onSubmit({ title: title.trim(), kind, expires_on: expiresOn || null })
      } else {
        // Send the file and its details together (empty choices are left out)
        const form = new FormData()
        form.append('file', file)
        form.append('title', title.trim())
        form.append('kind', kind)
        if (propertyId) form.append('property_id', propertyId)
        if (tenantId) form.append('tenant_id', tenantId)
        if (expiresOn) form.append('expires_on', expiresOn)
        await onSubmit(form)
      }
    } catch (err) {
      // Show the error under the form
      setError(err.message)
    } finally {
      // Stop the loading state
      setBusy(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {/* The file chooser (only when uploading) */}
      {isEdit ? (
        <p className="rounded-xl bg-forest-100 px-4 py-3 text-sm text-forest-700">
          {initial.original_name} · {fileSize(initial.size_bytes)}
        </p>
      ) : (
        <label className="flex cursor-pointer flex-col items-center gap-2 rounded-2xl border-2 border-dashed border-forest-200 bg-cream px-4 py-6 text-center transition hover:border-forest-500">
          <FileUp size={26} className="text-forest-500" />
          <span className="text-sm font-semibold text-forest-900">{file ? file.name : 'Choose a file or take a photo'}</span>
          <span className="text-xs text-muted">{file ? fileSize(file.size) : 'PDF, picture, Word or Excel, up to 10 MB'}</span>
          <input type="file" accept={ACCEPT} onChange={handleFile} className="hidden" />
        </label>
      )}

      <Field label="Name of the document">
        <input className={inputClass} value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Kinoru title deed" required maxLength={150} autoComplete="off" />
      </Field>

      <Field label="What kind is it?">
        <select className={inputClass} value={kind} onChange={(e) => setKind(e.target.value)}>
          {DOCUMENT_KINDS.map((item) => (
            <option key={item.key} value={item.key}>
              {item.label}
            </option>
          ))}
        </select>
      </Field>

      {/* Which property and tenant it belongs to (only when uploading) */}
      {!isEdit && (
        <div className="grid grid-cols-2 gap-3">
          <Field label="Property (optional)">
            <select className={inputClass} value={propertyId} onChange={(e) => setPropertyId(e.target.value)}>
              <option value="">None</option>
              {properties.map((prop) => (
                <option key={prop.property_id} value={prop.property_id}>
                  {prop.name}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Tenant (optional)">
            <select className={inputClass} value={tenantId} onChange={(e) => setTenantId(e.target.value)}>
              <option value="">None</option>
              {tenants.map((tenant) => (
                <option key={tenant.id} value={tenant.id}>
                  {tenant.full_name}
                </option>
              ))}
            </select>
          </Field>
        </div>
      )}

      <Field label="Expiry date (optional)" hint="For permits, licences and insurance. You will be reminded on the dashboard.">
        <input className={inputClass} type="date" value={expiresOn} onChange={(e) => setExpiresOn(e.target.value)} />
      </Field>

      {/* The error appears here if something goes wrong */}
      {error && (
        <div role="alert" className="rounded-xl bg-terracotta/10 px-4 py-3 text-sm font-medium text-terracotta">
          {error}
        </div>
      )}

      <div className="flex gap-3 pt-2">
        {onDelete && (
          <button
            type="button"
            onClick={onDelete}
            aria-label="Delete this document"
            className="rounded-xl bg-terracotta/10 px-4 text-terracotta hover:bg-terracotta hover:text-white"
          >
            <Trash2 size={18} />
          </button>
        )}
        <button
          type="button"
          onClick={onCancel}
          className="flex-1 rounded-xl bg-forest-100 py-3 font-semibold text-forest-700 hover:bg-forest-200"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={busy}
          className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-forest-900 py-3 font-semibold text-white hover:bg-forest-700 disabled:opacity-70"
        >
          {busy && <Loader2 size={18} className="animate-spin" />}
          {submitLabel}
        </button>
      </div>
    </form>
  )
}