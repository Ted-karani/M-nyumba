// Import the React tools we need
import { useEffect, useState } from 'react'
// Import the icons we use
import { Trash2, TriangleAlert } from 'lucide-react'
// Import our own files
import { CONDITIONS, CONDITION_RANK, conditionLabel } from '../inspection'
import PhotoThumbs from './PhotoThumbs'

// One area on a checklist: its rating, note, and photos (and what it was at move-in, when we are at move-out)
export default function InspectionItemRow({ item, before, locked, uploading, onCondition, onNote, onRemove, onOpenPhoto, onAddPhotos }) {
  // The note as it is being typed (it is saved when the box loses focus)
  const [note, setNote] = useState(item.note || '')
  // Keep the box in step if the saved note changes
  useEffect(() => {
    setNote(item.note || '')
  }, [item.note])

  // Work out how this area changed since move-in
  let change = null
  if (before && before.condition && item.condition) {
    const difference = CONDITION_RANK[item.condition] - CONDITION_RANK[before.condition]
    change = difference > 0 ? 'worse' : difference < 0 ? 'better' : 'same'
  }

  return (
    <div className="break-inside-avoid rounded-2xl bg-paper p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <p className="font-semibold text-forest-900">{item.area}</p>
        <div className="flex shrink-0 items-center gap-2">
          {change === 'worse' && (
            <span className="flex items-center gap-1 rounded-full bg-terracotta/15 px-2 py-0.5 text-xs font-semibold text-terracotta">
              <TriangleAlert size={12} /> Got worse
            </span>
          )}
          {change === 'better' && <span className="rounded-full bg-forest-100 px-2 py-0.5 text-xs font-semibold text-forest-700">Better</span>}
          {!locked && (
            <button onClick={() => onRemove(item)} aria-label={`Remove ${item.area}`} className="no-print rounded-lg p-1.5 text-muted hover:bg-terracotta/10 hover:text-terracotta">
              <Trash2 size={15} />
            </button>
          )}
        </div>
      </div>

      {/* What it was at move-in (only on the move-out checklist) */}
      {before && (
        <div className="mt-2 rounded-xl bg-cream p-3">
          <p className="text-xs font-semibold text-muted">
            At move-in: <span className="text-forest-900">{conditionLabel(before.condition)}</span>
          </p>
          {before.note && <p className="mt-0.5 text-xs text-muted">{before.note}</p>}
          {before.photos.length > 0 && (
            <div className="mt-2">
              <PhotoThumbs photos={before.photos} onOpen={(photo) => onOpenPhoto(photo, false)} />
            </div>
          )}
        </div>
      )}

      {/* The four rating buttons (tap the chosen one again to clear it) */}
      <div className="mt-3 grid grid-cols-4 gap-2">
        {CONDITIONS.map((condition) => (
          <button
            key={condition.key}
            type="button"
            disabled={locked}
            onClick={() => onCondition(item, condition.key)}
            className={`rounded-xl py-2 text-xs font-semibold transition disabled:cursor-default ${item.condition === condition.key ? condition.on : condition.off} ${locked && item.condition !== condition.key ? 'opacity-40' : ''}`}
          >
            {condition.label}
          </button>
        ))}
      </div>

      {/* The note */}
      {locked ? (
        item.note && <p className="mt-3 text-sm text-ink/80">{item.note}</p>
      ) : (
        <textarea
          value={note}
          onChange={(e) => setNote(e.target.value)}
          onBlur={() => onNote(item, note)}
          maxLength={300}
          rows={1}
          placeholder="Add a note, for example: small crack near the window"
          className="no-print mt-3 w-full resize-none rounded-xl border border-forest-200 bg-paper px-3 py-2 text-sm outline-none transition focus:border-forest-500 focus:ring-4 focus:ring-forest-100"
        />
      )}

      {/* The photos */}
      <div className="mt-3">
        <PhotoThumbs
          photos={item.photos}
          onOpen={(photo) => onOpenPhoto(photo, !locked)}
          onAdd={(files) => onAddPhotos(item.id, files)}
          canAdd={!locked}
          uploading={uploading}
        />
      </div>
    </div>
  )
}