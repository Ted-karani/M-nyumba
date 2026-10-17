// Import the icons we use
import { Camera, Loader2 } from 'lucide-react'
// Import our picture loader
import AuthImage from './AuthImage'

// A row of small photos, and (when allowed) a button to add more
export default function PhotoThumbs({ photos, onOpen, onAdd, canAdd = false, uploading = false }) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      {photos.map((photo) => (
        <button key={photo.id} type="button" onClick={() => onOpen(photo)} aria-label="Open photo" className="overflow-hidden rounded-xl">
          <AuthImage path={`/inspections/photos/${photo.id}/file`} alt={photo.caption || 'Photo'} className="h-14 w-14 object-cover" />
        </button>
      ))}
      {/* The camera button: on a phone it offers the camera or the gallery */}
      {canAdd && (
        <label className="no-print flex h-14 w-14 cursor-pointer items-center justify-center rounded-xl border-2 border-dashed border-forest-200 text-forest-500 transition hover:border-forest-500">
          {uploading ? <Loader2 size={18} className="animate-spin" /> : <Camera size={20} />}
          <input
            type="file"
            accept="image/*"
            multiple
            className="hidden"
            disabled={uploading}
            onChange={(event) => {
              // Take the chosen pictures, and clear the box so the same one can be chosen again
              const files = Array.from(event.target.files)
              event.target.value = ''
              if (files.length > 0) onAdd(files)
            }}
          />
        </label>
      )}
    </div>
  )
}