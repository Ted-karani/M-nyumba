// Import the React tool for remembering values
import { useState } from 'react'
// Import the icons we use
import { Check, Copy, ExternalLink, Eye, Link2, Loader2, MessageCircle, RefreshCw, Share2 } from 'lucide-react'
// Import our own files
import { API_URL, fetchBlob, newListingLink } from '../api'
import { money, phoneLocal } from '../format'
import ConfirmDialog from './ConfirmDialog'

// The panel for sharing a listing: copy the link, send it on WhatsApp, or send the photos too
export default function ShareSheet({ listing, onChanged }) {
  // True for a moment after the link was copied
  const [copied, setCopied] = useState(false)
  // True while the photos are being got ready
  const [preparing, setPreparing] = useState(false)
  // The error message to show (empty means none)
  const [error, setError] = useState('')
  // Whether the "make a new link" question is open
  const [asking, setAsking] = useState(false)

  // The link people open (it shows a preview card in WhatsApp)
  const link = `${API_URL}/share/${listing.token}`
  // The message that goes with it
  const lines = [
    listing.title,
    `${money(listing.rent_amount)} per month${listing.deposit_amount > 0 ? `, deposit ${money(listing.deposit_amount)}` : ''}`,
  ]
  if (listing.location) lines.push(listing.location)
  if (listing.contact_phone) lines.push(`Call or WhatsApp: ${phoneLocal(listing.contact_phone)}`)
  lines.push(`See the photos and details: ${link}`)
  const message = lines.join('\n')

  // Copy the link
  async function copyLink() {
    try {
      await navigator.clipboard.writeText(link)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      setError('Could not copy. Press and hold the link to copy it.')
    }
  }

  // Send the photos and the message together (this works on phones that support sharing files)
  async function shareWithPhotos() {
    setError('')
    setPreparing(true)
    try {
      // Get up to 4 photos ready as files
      const files = []
      for (const photo of listing.photos.slice(0, 4)) {
        const blob = await fetchBlob(`/listings/photos/${photo.id}/file`)
        files.push(new File([blob], `photo-${files.length + 1}.${blob.type === 'image/png' ? 'png' : 'jpg'}`, { type: blob.type }))
      }
      if (!navigator.canShare || !navigator.canShare({ files })) {
        setError('Sharing photos is not supported on this device. Use the WhatsApp button instead.')
        return
      }
      await navigator.share({ files, text: message, title: listing.title })
    } catch (err) {
      // Closing the share window is not an error
      if (err.name !== 'AbortError') setError(err.message || 'Could not share the photos.')
    } finally {
      setPreparing(false)
    }
  }

  // Is this a state where the link works?
  const works = listing.state === 'live'

  return (
    <div>
      {/* A warning when the link will not show an available unit */}
      {!works && (
        <p className="mb-4 rounded-xl bg-amber/15 px-4 py-3 text-sm text-amber">
          {listing.state === 'hidden'
            ? 'This listing is hidden, so the link says it is not available. Switch it on in Edit.'
            : 'This unit has been taken, so the page says so.'}
        </p>
      )}

      {/* The link */}
      <div className="flex items-center gap-2 rounded-xl bg-cream p-3">
        <Link2 size={18} className="shrink-0 text-forest-500" />
        <p className="min-w-0 flex-1 truncate font-mono text-xs text-forest-900">{link}</p>
      </div>
      <p className="mt-2 flex items-center gap-1.5 text-xs text-muted">
        <Eye size={13} /> Opened {listing.views} time{listing.views === 1 ? '' : 's'}
      </p>

      {/* The buttons */}
      <div className="mt-4 grid gap-2">
        <button onClick={copyLink} className="flex items-center justify-center gap-2 rounded-xl bg-forest-100 py-3 text-sm font-semibold text-forest-700 hover:bg-forest-200">
          {copied ? <Check size={16} /> : <Copy size={16} />} {copied ? 'Link copied' : 'Copy link'}
        </button>
        <a
          href={`https://wa.me/?text=${encodeURIComponent(message)}`}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center justify-center gap-2 rounded-xl bg-forest-500 py-3 text-sm font-semibold text-white hover:bg-forest-700"
        >
          <MessageCircle size={16} /> Send on WhatsApp
        </a>
        {listing.photos.length > 0 && (
          <button
            onClick={shareWithPhotos}
            disabled={preparing}
            className="flex items-center justify-center gap-2 rounded-xl bg-forest-900 py-3 text-sm font-semibold text-white hover:bg-forest-700 disabled:opacity-70"
          >
            {preparing ? <Loader2 size={16} className="animate-spin" /> : <Share2 size={16} />} Share with photos (phone)
          </button>
        )}
        <a href={`/l/${listing.token}`} target="_blank" rel="noopener noreferrer" className="flex items-center justify-center gap-2 rounded-xl py-3 text-sm font-semibold text-forest-700 hover:bg-forest-100">
          <ExternalLink size={16} /> See how it looks to others
        </a>
      </div>

      {error && (
        <p role="alert" className="mt-3 rounded-xl bg-terracotta/10 px-4 py-3 text-sm font-medium text-terracotta">
          {error}
        </p>
      )}

      {/* Make a new link */}
      <button onClick={() => setAsking(true)} className="mt-4 flex items-center gap-2 text-sm font-medium text-muted hover:text-terracotta">
        <RefreshCw size={14} /> Make a new link (the old one stops working)
      </button>
      <ConfirmDialog
        open={asking}
        title="Make a new link?"
        message="The old link will stop working straight away. Anyone who has it will see that the listing is not available."
        confirmLabel="Make new link"
        onClose={() => setAsking(false)}
        onConfirm={async () => {
          await newListingLink(listing.id)
          setAsking(false)
          onChanged()
        }}
      />
    </div>
  )
}