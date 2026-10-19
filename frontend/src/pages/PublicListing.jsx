// Import the React tools we need
import { useEffect, useRef, useState } from 'react'
// Import the page-reading tool
import { useParams } from 'react-router-dom'
// Import the animation tool
import { motion } from 'framer-motion'
// Import the icons we use
import { BedDouble, Building2, CalendarDays, CheckCircle2, MapPin, MessageCircle, Phone } from 'lucide-react'
// Import our own files
import { API_URL, getPublicListing } from '../api'
import { formatDate, money, phoneLocal } from '../format'

// The page anyone with the link can open (no login)
export default function PublicListing() {
  // Read the secret code from the address, like /l/abc123
  const { token } = useParams()
  // The listing (nothing until it arrives)
  const [listing, setListing] = useState(null)
  // The error message, if it could not be loaded
  const [error, setError] = useState('')
  // Which photo is showing in the gallery
  const [current, setCurrent] = useState(0)
  // The gallery strip (so we can see how far it was scrolled)
  const strip = useRef(null)

  // Load the listing when the page opens
  useEffect(() => {
    getPublicListing(token)
      .then((data) => {
        setListing(data)
        document.title = `${data.title} · M-nyumba`
      })
      .catch(() => setError('This listing is not available. It may have been taken or switched off.'))
  }, [token])

  // If it could not be loaded, say so kindly
  if (error) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center bg-cream px-6 text-center">
        <div className="flex h-16 w-16 items-center justify-center rounded-3xl bg-forest-100 text-forest-700">
          <Building2 size={28} />
        </div>
        <h1 className="mt-5 text-2xl font-bold text-forest-900">Listing not available</h1>
        <p className="mt-2 max-w-sm text-muted">{error}</p>
      </div>
    )
  }

  // While waiting, show a grey placeholder
  if (!listing) {
    return (
      <div className="min-h-screen bg-cream">
        <div className="h-72 animate-pulse bg-forest-100" />
        <div className="mx-auto max-w-2xl space-y-3 p-6">
          <div className="h-8 w-2/3 animate-pulse rounded-xl bg-forest-100" />
          <div className="h-24 animate-pulse rounded-2xl bg-forest-100" />
        </div>
      </div>
    )
  }

  // Each photo's address (the photos are public, but only with the secret code)
  const photoUrl = (id) => `${API_URL}/public/listings/${token}/photos/${id}`
  // The message people send on WhatsApp
  const hello = `Hello${listing.contact_name ? ` ${listing.contact_name.split(' ')[0]}` : ''}, I saw "${listing.title}" on M-nyumba. Is it still available?`

  return (
    <div className="min-h-screen bg-cream pb-28">
      {/* The photos: swipe sideways */}
      {listing.photo_ids.length > 0 ? (
        <div className="relative bg-forest-900">
          <div
            ref={strip}
            onScroll={() => setCurrent(Math.round(strip.current.scrollLeft / strip.current.clientWidth))}
            className="mx-auto flex max-w-2xl snap-x snap-mandatory overflow-x-auto [scrollbar-width:none]"
          >
            {listing.photo_ids.map((id) => (
              <img key={id} src={photoUrl(id)} alt={listing.title} className="h-72 w-full shrink-0 snap-center object-cover sm:h-96" />
            ))}
          </div>
          {listing.photo_ids.length > 1 && (
            <span className="absolute bottom-3 right-3 rounded-full bg-forest-900/80 px-3 py-1 text-xs font-semibold text-white">
              {current + 1} / {listing.photo_ids.length}
            </span>
          )}
        </div>
      ) : (
        <div className="flex h-56 items-center justify-center bg-forest-900 text-forest-200">
          <BedDouble size={48} />
        </div>
      )}

      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} className="mx-auto max-w-2xl px-5">
        {/* If the unit has been taken */}
        {!listing.available && (
          <div className="-mt-5 mb-4 rounded-2xl bg-amber px-5 py-4 text-sm font-semibold text-white shadow-lg">This unit has been taken. Ask about other units that may be free.</div>
        )}

        {/* The price card */}
        <div className={`${listing.available ? '-mt-6' : ''} rounded-3xl bg-paper p-6 shadow-lg`}>
          <h1 className="text-2xl font-extrabold leading-tight text-forest-900">{listing.title}</h1>
          <p className="mt-3 font-display text-4xl font-bold text-forest-700">
            {money(listing.rent_amount)} <span className="text-base font-medium text-muted">per month</span>
          </p>
          {listing.deposit_amount > 0 && <p className="mt-1 text-sm text-muted">Deposit: {money(listing.deposit_amount)}</p>}

          <div className="mt-4 space-y-2 text-sm text-forest-900">
            {listing.unit_type && (
              <p className="flex items-center gap-2">
                <BedDouble size={16} className="text-forest-500" /> {listing.unit_type}
              </p>
            )}
            {listing.location && (
              <p className="flex items-center gap-2">
                <MapPin size={16} className="text-forest-500" /> {listing.location}
              </p>
            )}
            {listing.property_name && (
              <p className="flex items-center gap-2">
                <Building2 size={16} className="text-forest-500" /> {listing.property_name}
              </p>
            )}
            {listing.available_from && (
              <p className="flex items-center gap-2">
                <CalendarDays size={16} className="text-forest-500" /> Available from {formatDate(listing.available_from)}
              </p>
            )}
          </div>
        </div>

        {/* The description */}
        {listing.description && (
          <div className="mt-4 rounded-3xl bg-paper p-6 shadow-sm">
            <h2 className="font-display text-lg font-bold text-forest-900">About this place</h2>
            <p className="mt-2 whitespace-pre-line text-sm leading-relaxed text-ink/80">{listing.description}</p>
          </div>
        )}

        {/* The amenities */}
        {listing.amenities.length > 0 && (
          <div className="mt-4 rounded-3xl bg-paper p-6 shadow-sm">
            <h2 className="font-display text-lg font-bold text-forest-900">What comes with it</h2>
            <div className="mt-3 grid gap-2 sm:grid-cols-2">
              {listing.amenities.map((item) => (
                <p key={item} className="flex items-center gap-2 text-sm text-forest-900">
                  <CheckCircle2 size={16} className="shrink-0 text-forest-500" /> {item}
                </p>
              ))}
            </div>
          </div>
        )}

        <p className="mt-6 text-center text-xs text-muted">Listing made with M-nyumba</p>
      </motion.div>

      {/* The contact buttons stay at the bottom of the screen */}
      {listing.available && listing.contact_phone && (
        <div className="fixed inset-x-0 bottom-0 border-t border-forest-100 bg-paper/95 px-5 pb-[max(1rem,env(safe-area-inset-bottom))] pt-3 backdrop-blur">
          <div className="mx-auto flex max-w-2xl items-center gap-3">
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-semibold text-forest-900">{listing.contact_name || 'Contact'}</p>
              <p className="text-xs text-muted">{phoneLocal(listing.contact_phone)}</p>
            </div>
            <a href={`tel:+${listing.contact_phone}`} className="flex items-center gap-2 rounded-xl bg-forest-100 px-5 py-3 text-sm font-semibold text-forest-700 hover:bg-forest-200">
              <Phone size={16} /> Call
            </a>
            <a
              href={`https://wa.me/${listing.contact_phone}?text=${encodeURIComponent(hello)}`}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 rounded-xl bg-forest-500 px-5 py-3 text-sm font-semibold text-white hover:bg-forest-700"
            >
              <MessageCircle size={16} /> WhatsApp
            </a>
          </div>
        </div>
      )}
    </div>
  )
}