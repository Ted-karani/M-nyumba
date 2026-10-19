// Import the React tool for remembering values
import { useState } from 'react'
// Import the icon we use
import { Loader2 } from 'lucide-react'
// Import our own files
import { Field, inputClass } from './Field'

// The form for posting or editing a notice
export default function NoticeForm({ notice, properties, onSubmit, onCancel }) {
  // What has been typed so far (when editing, it starts with the notice's words)
  const [title, setTitle] = useState(notice?.title ?? '')
  const [body, setBody] = useState(notice?.body ?? '')
  const [propertyId, setPropertyId] = useState(notice?.property_id ? String(notice.property_id) : '')
  const [pinned, setPinned] = useState(notice?.pinned ?? false)
  const [expiresOn, setExpiresOn] = useState(notice?.expires_on ?? '')
  // The error message, and whether we are waiting for the backend
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  // Run when the form is sent
  async function handleSubmit(event) {
    // Stop the page from reloading
    event.preventDefault()
    setError('')
    setBusy(true)
    try {
      await onSubmit({
        title: title.trim(),
        body: body.trim(),
        property_id: propertyId ? Number(propertyId) : null,
        pinned,
        expires_on: expiresOn || null,
      })
    } catch (err) {
      setError(err.message)
      setBusy(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <Field label="Headline">
        <input className={inputClass} value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Water shutdown on Tuesday" required minLength={3} maxLength={120} autoFocus />
      </Field>
      <Field label="Message">
        <textarea className={`${inputClass} min-h-28`} value={body} onChange={(e) => setBody(e.target.value)} placeholder="Water will be off from 8am to 2pm while the tank is cleaned." required maxLength={2000} />
      </Field>
      <Field label="Who is it for?">
        <select className={inputClass} value={propertyId} onChange={(e) => setPropertyId(e.target.value)}>
          <option value="">All my tenants</option>
          {properties.map((prop) => (
            <option key={prop.id} value={prop.id}>
              Only {prop.name}
            </option>
          ))}
        </select>
      </Field>
      <Field label="Hide it after (optional)" hint="Leave empty to keep showing it until you delete it.">
        <input className={inputClass} type="date" value={expiresOn} onChange={(e) => setExpiresOn(e.target.value)} />
      </Field>
      <button type="button" onClick={() => setPinned(!pinned)} className="flex w-full items-center justify-between gap-3 rounded-xl bg-cream px-4 py-3 text-left">
        <span>
          <span className="block text-sm font-semibold text-forest-900">Pin to the top</span>
          <span className="block text-xs text-muted">Good for things everyone must remember, like the rent due date.</span>
        </span>
        <span className={`relative h-6 w-11 shrink-0 rounded-full transition ${pinned ? 'bg-forest-500' : 'bg-forest-200'}`}>
          <span className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-all ${pinned ? 'left-[22px]' : 'left-0.5'}`} />
        </span>
      </button>
      {error && (
        <div role="alert" className="rounded-xl bg-terracotta/10 px-4 py-3 text-sm font-medium text-terracotta">
          {error}
        </div>
      )}
      <div className="flex gap-3 pt-2">
        <button type="button" onClick={onCancel} className="flex-1 rounded-xl bg-forest-100 py-3 font-semibold text-forest-700 hover:bg-forest-200">
          Cancel
        </button>
        <button type="submit" disabled={busy} className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-forest-900 py-3 font-semibold text-white hover:bg-forest-700 disabled:opacity-70">
          {busy && <Loader2 size={18} className="animate-spin" />}
          {notice ? 'Save changes' : 'Post notice'}
        </button>
      </div>
    </form>
  )
}