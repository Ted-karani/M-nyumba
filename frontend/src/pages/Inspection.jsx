// Import the React tools we need
import { useCallback, useEffect, useState } from 'react'
// Import the page-switching tools
import { Link, useParams } from 'react-router-dom'
// Import the animation tool
import { motion } from 'framer-motion'
// Import the icons we use
import { ArrowLeft, CheckCircle2, ClipboardCheck, Loader2, Lock, Plus, Printer, RefreshCw, Trash2, TriangleAlert } from 'lucide-react'
// Import our own files
import { useAuth } from '../AuthContext'
import {
  addInspectionItem,
  deleteInspection,
  deleteInspectionItem,
  deleteInspectionPhoto,
  finalizeInspection,
  getLeaseInspections,
  startInspection,
  unlockInspection,
  updateInspection,
  updateInspectionItem,
  uploadInspectionPhoto,
} from '../api'
import { compressImage, formatDateTime } from '../inspection'
import { formatDate, todayISO } from '../format'
import AuthImage from '../components/AuthImage'
import ConfirmDialog from '../components/ConfirmDialog'
import { Field, inputClass } from '../components/Field'
import InspectionItemRow from '../components/InspectionItemRow'
import Modal from '../components/Modal'
import PhotoThumbs from '../components/PhotoThumbs'

// The page for a move-in or move-out checklist
export default function Inspection() {
  // Read the lease and the kind from the address, like /leases/4/inspection/move_in
  const { leaseId, kind } = useParams()
  // Who is logged in (caretakers go back to their home screen)
  const { user } = useAuth()
  const isCaretaker = user.role === 'caretaker'
  const isMoveOut = kind === 'move_out'
  const title = isMoveOut ? 'Move-out checklist' : 'Move-in checklist'
  // Both checklists of the lease (nothing until they arrive)
  const [data, setData] = useState(null)
  // The error message
  const [error, setError] = useState('')
  // The date and busy state of the "start" form
  const [startDate, setStartDate] = useState(todayISO())
  const [starting, setStarting] = useState(false)
  // Which area (or "general") is uploading photos right now
  const [uploading, setUploading] = useState(null)
  // True while a button like "finish" is working
  const [working, setWorking] = useState(false)
  // The photo being viewed, and whether it can be deleted
  const [viewing, setViewing] = useState(null)
  // Whether the "delete this checklist" question is open
  const [deleting, setDeleting] = useState(false)
  // The name typed for a new area
  const [newArea, setNewArea] = useState('')

  // Load both checklists (a quiet reload keeps what is on the screen)
  const load = useCallback(
    (quiet = false) => {
      if (!quiet) setData(null)
      return getLeaseInspections(leaseId)
        .then((result) => {
          setData(result)
          setError('')
        })
        .catch((err) => setError(err.message))
    },
    [leaseId]
  )

  // Load them when the page opens
  useEffect(() => {
    load()
  }, [load])

  // Only two kinds exist
  if (kind !== 'move_in' && kind !== 'move_out') {
    return <p className="rounded-2xl bg-terracotta/10 p-4 text-terracotta">This page does not exist.</p>
  }

  // If loading failed, show the message and a retry button
  if (error && !data) {
    return (
      <div className="rounded-3xl bg-terracotta/10 p-6 text-terracotta">
        <p className="font-semibold">Could not open this checklist</p>
        <p className="mt-1 text-sm">{error}</p>
        <button onClick={() => load()} className="mt-4 flex items-center gap-2 rounded-xl bg-terracotta px-4 py-2 text-sm font-semibold text-white">
          <RefreshCw size={16} /> Try again
        </button>
      </div>
    )
  }

  // While waiting, show grey placeholder boxes
  if (!data) {
    return (
      <div className="space-y-3">
        <div className="h-40 animate-pulse rounded-3xl bg-forest-100" />
        <div className="h-28 animate-pulse rounded-2xl bg-forest-100" />
      </div>
    )
  }

  // The checklist we are looking at, the move-in one (to compare with), and the lease
  const current = data[kind]
  const before = isMoveOut ? data.move_in : null
  const lease = data.lease
  // Where the "back" link goes
  const backTo = isCaretaker ? '/' : `/tenants/${lease.tenant_id}`
  const locked = Boolean(current && current.finalized_at)

  // Change one area on the screen right away (the backend is told straight after)
  function patchItem(itemId, changes) {
    setData((previous) => ({
      ...previous,
      [kind]: {
        ...previous[kind],
        items: previous[kind].items.map((item) => (item.id === itemId ? { ...item, ...changes } : item)),
      },
    }))
  }

  // Start the checklist
  async function handleStart() {
    setError('')
    setStarting(true)
    try {
      await startInspection(lease.lease_id, kind, { done_on: startDate })
      await load(true)
    } catch (err) {
      setError(err.message)
    } finally {
      setStarting(false)
    }
  }

  // Rate an area (tap the same rating again to clear it)
  async function handleCondition(item, key) {
    const next = item.condition === key ? null : key
    patchItem(item.id, { condition: next })
    try {
      await updateInspectionItem(item.id, { condition: next })
    } catch (err) {
      setError(err.message)
      load(true)
    }
  }

  // Save an area's note
  async function handleNote(item, text) {
    if (text.trim() === (item.note || '')) return
    patchItem(item.id, { note: text.trim() || null })
    try {
      await updateInspectionItem(item.id, { note: text })
    } catch (err) {
      setError(err.message)
      load(true)
    }
  }

  // Remove an area
  async function handleRemove(item) {
    setError('')
    try {
      await deleteInspectionItem(item.id)
      await load(true)
    } catch (err) {
      setError(err.message)
    }
  }

  // Add an area
  async function handleAddArea(event) {
    event.preventDefault()
    if (newArea.trim().length < 2) return
    setError('')
    try {
      await addInspectionItem(current.id, newArea.trim())
      setNewArea('')
      await load(true)
    } catch (err) {
      setError(err.message)
    }
  }

  // Upload photos (for one area, or "general" photos when no area is given)
  async function handleAddPhotos(itemId, files) {
    setError('')
    setUploading(itemId ?? 'general')
    try {
      for (const file of files) {
        // Shrink big photos first, then send them
        const ready = await compressImage(file)
        const form = new FormData()
        form.append('file', ready)
        if (itemId) form.append('item_id', String(itemId))
        await uploadInspectionPhoto(current.id, form)
      }
      await load(true)
    } catch (err) {
      setError(err.message)
    } finally {
      setUploading(null)
    }
  }

  // Save the date, notes, or the tenant's details
  async function handleDetails(changes) {
    setError('')
    try {
      await updateInspection(current.id, changes)
      await load(true)
    } catch (err) {
      setError(err.message)
    }
  }

  // Lock or unlock the checklist
  async function handleLock(unlock) {
    setError('')
    setWorking(true)
    try {
      if (unlock) await unlockInspection(current.id)
      else await finalizeInspection(current.id)
      await load(true)
    } catch (err) {
      setError(err.message)
    } finally {
      setWorking(false)
    }
  }

  // The back link and the title
  const header = (
    <>
      <Link to={backTo} className="no-print inline-flex items-center gap-1 text-sm font-medium text-forest-700 hover:underline">
        <ArrowLeft size={16} /> {isCaretaker ? 'My properties' : lease.tenant_name}
      </Link>
      <h1 className="no-print mt-2 text-3xl font-extrabold text-forest-900">{title}</h1>
      <p className="no-print text-muted">
        {lease.tenant_name} · unit {lease.unit_number} · {lease.property_name}
      </p>
    </>
  )

  // If this checklist has not been started yet, show the start card
  if (!current) {
    return (
      <div className="mx-auto max-w-xl">
        {header}
        <div className="mt-6 rounded-3xl bg-paper p-6 shadow-sm">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-forest-100 text-forest-700">
            <ClipboardCheck size={26} />
          </div>
          <h2 className="mt-4 font-display text-xl font-bold text-forest-900">Start the {isMoveOut ? 'move-out' : 'move-in'} walkthrough</h2>
          <p className="mt-1 text-sm text-muted">
            Walk through the unit with the tenant. You will rate each area, add notes, and take photos.
            {isMoveOut && data.move_in ? ' Each area will show what it was at move-in, so changes are easy to see.' : ''}
          </p>
          {isMoveOut && !data.move_in && (
            <p className="mt-3 rounded-xl bg-amber/15 px-4 py-3 text-sm text-amber">There is no move-in checklist for this lease, so there is nothing to compare with.</p>
          )}
          <div className="mt-4">
            <Field label="Date of the walkthrough">
              <input className={inputClass} type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
            </Field>
          </div>
          {error && <p role="alert" className="mt-4 rounded-xl bg-terracotta/10 px-4 py-3 text-sm font-medium text-terracotta">{error}</p>}
          <button
            onClick={handleStart}
            disabled={starting || !startDate}
            className="mt-5 flex w-full items-center justify-center gap-2 rounded-xl bg-forest-900 py-3.5 font-semibold text-white hover:bg-forest-700 disabled:opacity-70"
          >
            {starting && <Loader2 size={18} className="animate-spin" />} Start checklist
          </button>
        </div>
      </div>
    )
  }

  // How many areas are rated, and which got worse since move-in
  const rated = current.items.filter((item) => item.condition).length
  const worse = before
    ? current.items.filter((item) => {
        const earlier = before.items.find((candidate) => candidate.area === item.area)
        const order = ['good', 'fair', 'poor', 'damaged']
        return earlier && earlier.condition && item.condition && order.indexOf(item.condition) > order.indexOf(earlier.condition)
      })
    : []

  return (
    <div className="mx-auto max-w-3xl">
      {/* The words at the top of the printed page */}
      <div className="print-only mb-4 border-b border-forest-200 pb-3">
        <p className="font-display text-2xl font-bold text-forest-900">M-nyumba {title.toLowerCase()}</p>
        <p className="text-sm text-muted">
          Tenant: {lease.tenant_name} · Unit {lease.unit_number}, {lease.property_name} · Walkthrough on {formatDate(current.done_on)}
          {current.tenant_present ? ' · tenant was present' : ''}
        </p>
      </div>

      {header}

      {/* The green summary card */}
      <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} className="mt-5 break-inside-avoid rounded-3xl bg-forest-900 p-6 text-white shadow-xl">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-sm text-forest-200">Walkthrough on {formatDate(current.done_on)}</p>
            <p className="mt-1 font-display text-3xl font-bold">
              {rated} of {current.items.length} <span className="text-lg font-medium text-forest-200">areas checked</span>
            </p>
            {current.created_by_name && <p className="mt-1 text-xs text-forest-200">Started by {current.created_by_name}</p>}
          </div>
          {locked && (
            <span className="flex shrink-0 items-center gap-1.5 rounded-full bg-gold px-3 py-1 text-xs font-bold text-forest-900">
              <Lock size={12} /> Locked
            </span>
          )}
        </div>
        {/* A bar that fills as areas are rated */}
        <div className="mt-4 h-2 overflow-hidden rounded-full bg-white/15">
          <motion.div className="h-full rounded-full bg-gold" initial={false} animate={{ width: `${(rated / Math.max(1, current.items.length)) * 100}%` }} transition={{ duration: 0.4 }} />
        </div>
        {locked && <p className="mt-3 text-xs text-forest-200">Locked on {formatDateTime(current.finalized_at)}. Nothing can be changed.</p>}
        {/* The buttons */}
        <div className="no-print mt-5 flex flex-wrap gap-2">
          {!locked && (
            <button
              onClick={() => handleLock(false)}
              disabled={working}
              className="flex items-center gap-2 rounded-xl bg-gold px-4 py-2.5 text-sm font-semibold text-forest-900 hover:brightness-95 disabled:opacity-70"
            >
              {working ? <Loader2 size={16} className="animate-spin" /> : <Lock size={16} />} Finish and lock
            </button>
          )}
          <button onClick={() => window.print()} className="flex items-center gap-2 rounded-xl bg-white/10 px-4 py-2.5 text-sm font-semibold hover:bg-white/20">
            <Printer size={16} /> Print or save as PDF
          </button>
          {locked && data.can_unlock && (
            <button onClick={() => handleLock(true)} disabled={working} className="rounded-xl bg-white/10 px-4 py-2.5 text-sm font-semibold hover:bg-white/20 disabled:opacity-70">
              Unlock
            </button>
          )}
          {data.can_unlock && (
            <button onClick={() => setDeleting(true)} aria-label="Delete this checklist" className="rounded-xl bg-white/10 px-3 py-2.5 hover:bg-terracotta">
              <Trash2 size={16} />
            </button>
          )}
        </div>
      </motion.div>

      {error && <p role="alert" className="no-print mt-4 rounded-xl bg-terracotta/10 px-4 py-3 text-sm font-medium text-terracotta">{error}</p>}

      {/* The move-out comparison */}
      {isMoveOut && before && (
        <div className={`mt-4 break-inside-avoid rounded-2xl p-4 ${worse.length > 0 ? 'bg-terracotta/10' : 'bg-forest-100'}`}>
          <p className={`flex items-center gap-2 font-semibold ${worse.length > 0 ? 'text-terracotta' : 'text-forest-700'}`}>
            {worse.length > 0 ? <TriangleAlert size={18} /> : <CheckCircle2 size={18} />}
            {worse.length > 0
              ? `${worse.length} area${worse.length === 1 ? '' : 's'} got worse since move-in`
              : rated === current.items.length
              ? 'Nothing got worse since move-in'
              : 'Compared with the move-in checklist as you rate each area'}
          </p>
          {worse.length > 0 && (
            <ul className="mt-2 list-disc pl-6 text-sm text-terracotta">
              {worse.map((item) => (
                <li key={item.id}>{item.area}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      {/* The areas */}
      <div className="mt-5 grid gap-3 md:grid-cols-2">
        {current.items.map((item) => (
          <InspectionItemRow
            key={item.id}
            item={item}
            before={before ? before.items.find((candidate) => candidate.area === item.area) || null : null}
            locked={locked}
            uploading={uploading === item.id}
            onCondition={handleCondition}
            onNote={handleNote}
            onRemove={handleRemove}
            onOpenPhoto={(photo, deletable) => setViewing({ photo, deletable })}
            onAddPhotos={handleAddPhotos}
          />
        ))}
      </div>

      {/* Add another area */}
      {!locked && (
        <form onSubmit={handleAddArea} className="no-print mt-4 flex gap-2">
          <input
            className={inputClass}
            value={newArea}
            onChange={(e) => setNewArea(e.target.value)}
            placeholder="Add an area, like Gate and compound"
            maxLength={80}
          />
          <button type="submit" disabled={newArea.trim().length < 2} className="flex shrink-0 items-center gap-1 rounded-xl bg-forest-100 px-4 font-semibold text-forest-700 hover:bg-forest-200 disabled:opacity-50">
            <Plus size={18} /> Add
          </button>
        </form>
      )}

      {/* Other photos, notes, and the tenant */}
      <div className="mt-6 space-y-4 break-inside-avoid rounded-3xl bg-paper p-5 shadow-sm">
        <h2 className="font-display text-lg font-bold text-forest-900">Other photos and notes</h2>
        <PhotoThumbs
          photos={current.general_photos}
          onOpen={(photo) => setViewing({ photo, deletable: !locked })}
          onAdd={(files) => handleAddPhotos(null, files)}
          canAdd={!locked}
          uploading={uploading === 'general'}
        />
        <p className="no-print text-xs text-muted">For things like meter readings, the keys, or the whole room.</p>

        {locked ? (
          <>
            {current.notes && <p className="text-sm text-ink/80">Notes: {current.notes}</p>}
            <p className="text-sm text-ink/80">{current.tenant_present ? 'The tenant was present.' : 'The tenant was not present.'}</p>
            {current.tenant_comment && <p className="text-sm text-ink/80">Tenant said: {current.tenant_comment}</p>}
          </>
        ) : (
          <div className="no-print space-y-4">
            <Field label="General notes">
              <textarea
                key={`notes-${current.notes || ''}`}
                defaultValue={current.notes || ''}
                onBlur={(e) => e.target.value.trim() !== (current.notes || '') && handleDetails({ notes: e.target.value })}
                maxLength={1000}
                className={`${inputClass} min-h-16`}
              />
            </Field>
            <button
              type="button"
              onClick={() => handleDetails({ tenant_present: !current.tenant_present })}
              className="flex w-full items-center justify-between rounded-xl bg-cream px-4 py-3 text-left"
            >
              <span className="text-sm font-semibold text-forest-900">The tenant was present for the walkthrough</span>
              <span className={`relative h-6 w-11 shrink-0 rounded-full transition ${current.tenant_present ? 'bg-forest-500' : 'bg-forest-200'}`}>
                <span className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-all ${current.tenant_present ? 'left-[22px]' : 'left-0.5'}`} />
              </span>
            </button>
            <Field label="What the tenant said (optional)">
              <textarea
                key={`comment-${current.tenant_comment || ''}`}
                defaultValue={current.tenant_comment || ''}
                onBlur={(e) => e.target.value.trim() !== (current.tenant_comment || '') && handleDetails({ tenant_comment: e.target.value })}
                maxLength={1000}
                className={`${inputClass} min-h-16`}
              />
            </Field>
          </div>
        )}
      </div>

      {/* The signature lines (only on paper) */}
      <div className="print-only mt-10 grid grid-cols-2 gap-10 text-sm">
        <div>
          <div className="border-b border-ink pt-10" />
          <p className="mt-1">Tenant: {lease.tenant_name}</p>
        </div>
        <div>
          <div className="border-b border-ink pt-10" />
          <p className="mt-1">Landlord or caretaker</p>
        </div>
      </div>

      {/* A photo, shown large */}
      <Modal open={viewing !== null} title="Photo" onClose={() => setViewing(null)}>
        {viewing && (
          <div>
            <AuthImage path={`/inspections/photos/${viewing.photo.id}/file`} alt="Photo" className="max-h-[60vh] w-full rounded-xl object-contain" />
            <p className="mt-3 text-xs text-muted">Uploaded {formatDateTime(viewing.photo.created_at)}</p>
            {viewing.deletable && !locked && (
              <button
                onClick={async () => {
                  const photoId = viewing.photo.id
                  setViewing(null)
                  try {
                    await deleteInspectionPhoto(photoId)
                    await load(true)
                  } catch (err) {
                    setError(err.message)
                  }
                }}
                className="mt-4 flex w-full items-center justify-center gap-2 rounded-xl bg-terracotta/10 py-3 text-sm font-semibold text-terracotta hover:bg-terracotta hover:text-white"
              >
                <Trash2 size={16} /> Delete this photo
              </button>
            )}
          </div>
        )}
      </Modal>

      {/* Delete the whole checklist */}
      <ConfirmDialog
        open={deleting}
        title="Delete this checklist?"
        message="The ratings, notes, and all the photos will be deleted. This cannot be undone."
        confirmLabel="Delete checklist"
        onClose={() => setDeleting(false)}
        onConfirm={async () => {
          await deleteInspection(current.id)
          setDeleting(false)
          await load(true)
        }}
      />
    </div>
  )
}