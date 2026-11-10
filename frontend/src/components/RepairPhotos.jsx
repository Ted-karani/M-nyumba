// Import the React tools we need
import { useCallback, useEffect, useRef, useState } from 'react'
// Import the icons we use
import { Camera, Loader2, Trash2, X } from 'lucide-react'
// Import our own files
import { deletePortalRepairPhoto, deleteRepairPhoto, getPortalRepairPhotos, getRepairPhotos, uploadRepairPhoto } from '../api'
import { useT } from '../i18n'
import { shrinkImage } from '../imageTools'
import AuthImage from './AuthImage'

// The photos of one repair: a grid, a way to add more, and a way to look at one up close.
// mode is "staff" (landlords and caretakers) or "tenant".
export default function RepairPhotos({ repairId, mode, canAdd = true }) {
  const t = useT()
  const tenant = mode === 'tenant'
  const base = tenant ? '/portal/repairs' : '/maintenance'
  // The photos (nothing until they arrive), an error, whether we are sending, and the one being looked at
  const [photos, setPhotos] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [viewing, setViewing] = useState(null)
  const picker = useRef(null)

  // Load the photos
  const load = useCallback(() => {
    ;(tenant ? getPortalRepairPhotos : getRepairPhotos)(repairId)
      .then(setPhotos)
      .catch(() => setError(t('Could not load the photos.')))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [repairId, tenant])
  useEffect(() => {
    load()
  }, [load])

  // Send the pictures that were chosen, one by one
  async function handleFiles(event) {
    const files = Array.from(event.target.files || [])
    // Allow choosing the same picture again later
    event.target.value = ''
    if (files.length === 0) return
    setError('')
    setBusy(true)
    try {
      for (const file of files) await uploadRepairPhoto(`${base}/${repairId}/photos`, await shrinkImage(file))
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
      load()
    }
  }

  // Remove a photo
  async function remove(photo) {
    if (!window.confirm(t('Delete this photo?'))) return
    setError('')
    try {
      await (tenant ? deletePortalRepairPhoto : deleteRepairPhoto)(photo.id)
      setViewing(null)
      load()
    } catch (err) {
      setError(err.message)
    }
  }

  const fileOf = (photo) => `${base}/photos/${photo.id}/file`

  return (
    <div>
      <div className="flex items-center justify-between gap-3">
        <p className="flex items-center gap-1.5 text-sm font-semibold text-forest-900">
          <Camera size={15} className="text-gold" /> {t('Photos')}
        </p>
        {canAdd && (
          <>
            <input ref={picker} type="file" accept="image/*" multiple onChange={handleFiles} className="hidden" />
            <button type="button" onClick={() => picker.current && picker.current.click()} disabled={busy} className="flex items-center gap-1.5 rounded-lg bg-forest-100 px-3 py-1.5 text-xs font-semibold text-forest-700 hover:bg-forest-200 disabled:opacity-60">
              {busy ? <Loader2 size={13} className="animate-spin" /> : <Camera size={13} />} {busy ? t('Sending...') : t('Add a photo')}
            </button>
          </>
        )}
      </div>

      {error && (
        <div role="alert" className="mt-2 rounded-xl bg-terracotta/10 px-3 py-2 text-xs font-medium text-terracotta">
          {error}
        </div>
      )}
      {!photos && !error && <div className="mt-2 h-16 animate-pulse rounded-xl bg-forest-100" />}
      {photos && photos.length === 0 && <p className="mt-2 text-xs text-muted">{t('No photos yet.')}</p>}
      {photos && photos.length > 0 && (
        <div className="mt-2 grid grid-cols-4 gap-2">
          {photos.map((photo) => (
            <button key={photo.id} type="button" onClick={() => setViewing(photo)} className="relative overflow-hidden rounded-xl bg-forest-100" aria-label={t('Photo')}>
              <AuthImage path={fileOf(photo)} alt={t('Photo')} className="h-20 w-full object-cover" />
              {!tenant && photo.by_tenant && <span className="absolute inset-x-0 bottom-0 bg-forest-900/70 px-1 py-0.5 text-[9px] font-semibold text-white">{t('From the tenant')}</span>}
            </button>
          ))}
        </div>
      )}

      {/* A photo up close */}
      {viewing && (
        <div className="fixed inset-0 z-[60] flex flex-col bg-forest-900/90 p-4" onClick={() => setViewing(null)}>
          <div className="flex justify-end gap-2" onClick={(event) => event.stopPropagation()}>
            {viewing.can_delete && (
              <button type="button" onClick={() => remove(viewing)} aria-label={t('Remove this photo')} className="rounded-xl bg-terracotta p-2.5 text-white">
                <Trash2 size={18} />
              </button>
            )}
            <button type="button" onClick={() => setViewing(null)} aria-label={t('Close')} className="rounded-xl bg-white/20 p-2.5 text-white">
              <X size={18} />
            </button>
          </div>
          <div className="flex min-h-0 flex-1 items-center justify-center" onClick={(event) => event.stopPropagation()}>
            <AuthImage path={fileOf(viewing)} alt={t('Photo')} className="max-h-full max-w-full rounded-xl object-contain" />
          </div>
        </div>
      )}
    </div>
  )
}