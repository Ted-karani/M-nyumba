// Import the React tools we need
import { useCallback, useEffect, useState } from 'react'
// Import the animation tool
import { motion } from 'framer-motion'
// Import the icons we use
import { Eye, ImageOff, Megaphone, Pencil, Plus, RefreshCw, Share2, Trash2 } from 'lucide-react'
// Import our own files
import { useAuth } from '../AuthContext'
import { deleteListing, getListings } from '../api'
import { money } from '../format'
import AuthImage from '../components/AuthImage'
import ConfirmDialog from '../components/ConfirmDialog'
import ListingForm from '../components/ListingForm'
import Modal from '../components/Modal'
import ShareSheet from '../components/ShareSheet'

// How the list appears: the cards come in one after another
const listAnimation = { hidden: {}, show: { transition: { staggerChildren: 0.05 } } }
// How each card appears: fade in while sliding up
const itemAnimation = { hidden: { opacity: 0, y: 14 }, show: { opacity: 1, y: 0 } }

// The words and colors for each state
const STATES = {
  live: { label: 'Live', style: 'bg-forest-100 text-forest-700' },
  taken: { label: 'Taken', style: 'bg-amber/20 text-amber' },
  hidden: { label: 'Hidden', style: 'bg-ink/10 text-muted' },
}

// The page where owners advertise empty units
export default function Listings() {
  // The logged-in user (their name and phone are suggested as the contact)
  const { user } = useAuth()
  // The data from the backend (nothing until it arrives)
  const [data, setData] = useState(null)
  // The error message, if loading failed
  const [error, setError] = useState('')
  // Which pop-ups are open (each holds the thing it is about)
  const [creatingFor, setCreatingFor] = useState(null)
  const [editing, setEditing] = useState(null)
  const [sharing, setSharing] = useState(null)
  const [deleting, setDeleting] = useState(null)

  // Load the listings (a quiet reload keeps what is on the screen)
  const load = useCallback(async () => {
    setError('')
    try {
      const result = await getListings()
      setData(result)
      return result
    } catch (err) {
      setError(err.message)
      return null
    }
  }, [])

  // Load them when the page opens
  useEffect(() => {
    load()
  }, [load])

  // Count the live listings
  const liveCount = data ? data.listings.filter((item) => item.state === 'live').length : 0

  return (
    <div>
      {/* The title */}
      <h1 className="text-3xl font-extrabold text-forest-900">Vacancy listings</h1>
      <p className="text-muted">Fill empty units faster: share a photo page on WhatsApp in a few taps.</p>

      {/* If loading failed, show the message and a retry button */}
      {error && (
        <div className="mt-6 rounded-3xl bg-terracotta/10 p-6 text-terracotta">
          <p className="font-semibold">Could not load your listings</p>
          <p className="mt-1 text-sm">{error}</p>
          <button onClick={load} className="mt-4 flex items-center gap-2 rounded-xl bg-terracotta px-4 py-2 text-sm font-semibold text-white">
            <RefreshCw size={16} /> Try again
          </button>
        </div>
      )}

      {/* While waiting, show grey placeholder boxes */}
      {!error && !data && (
        <div className="mt-6 space-y-3">
          <div className="h-24 animate-pulse rounded-2xl bg-forest-100" />
          <div className="h-24 animate-pulse rounded-2xl bg-forest-100" />
        </div>
      )}

      {data && (
        <>
          {/* A small summary */}
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="mt-6 grid grid-cols-3 gap-3 rounded-3xl bg-forest-900 p-5 text-white shadow-xl">
            <div>
              <p className="text-xs text-forest-200">Empty units</p>
              <p className="font-display text-3xl font-bold">{data.vacant_units.length + data.listings.filter((item) => item.state === 'live').length}</p>
            </div>
            <div>
              <p className="text-xs text-forest-200">Listed and live</p>
              <p className="font-display text-3xl font-bold">{liveCount}</p>
            </div>
            <div>
              <p className="text-xs text-forest-200">Not listed yet</p>
              <p className="font-display text-3xl font-bold">{data.vacant_units.length}</p>
            </div>
          </motion.div>

          {/* The empty units that have no listing */}
          {data.vacant_units.length > 0 && (
            <div className="mt-8">
              <h2 className="mb-3 text-xl font-bold text-forest-900">Empty units with no listing</h2>
              <motion.div variants={listAnimation} initial="hidden" animate="show" className="grid gap-3 md:grid-cols-2">
                {data.vacant_units.map((unit) => (
                  <motion.div key={unit.unit_id} variants={itemAnimation} className="flex items-center justify-between gap-3 rounded-2xl bg-paper p-4 shadow-sm">
                    <div className="min-w-0">
                      <p className="font-display text-lg font-bold text-forest-900">{unit.unit_number}</p>
                      <p className="truncate text-sm text-muted">
                        {unit.unit_type ? `${unit.unit_type} · ` : ''}
                        {unit.property_name} · {money(unit.rent_amount)}
                      </p>
                    </div>
                    <button onClick={() => setCreatingFor(unit)} className="flex shrink-0 items-center gap-1.5 rounded-xl bg-forest-900 px-4 py-2.5 text-sm font-semibold text-white hover:bg-forest-700">
                      <Plus size={16} /> List it
                    </button>
                  </motion.div>
                ))}
              </motion.div>
            </div>
          )}

          {/* Nothing at all to show */}
          {data.vacant_units.length === 0 && data.listings.length === 0 && (
            <div className="mt-8 flex flex-col items-center rounded-3xl bg-paper p-10 text-center shadow-sm">
              <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-forest-100 text-forest-700">
                <Megaphone size={26} />
              </div>
              <p className="mt-4 font-semibold text-forest-900">No empty units right now</p>
              <p className="mt-1 max-w-xs text-sm text-muted">When a unit becomes vacant, it appears here so you can advertise it.</p>
            </div>
          )}

          {/* The listings */}
          {data.listings.length > 0 && (
            <div className="mt-8">
              <h2 className="mb-3 text-xl font-bold text-forest-900">Your listings</h2>
              <motion.div variants={listAnimation} initial="hidden" animate="show" className="grid gap-3 md:grid-cols-2">
                {data.listings.map((item) => {
                  const state = STATES[item.state]
                  return (
                    <motion.div key={item.id} variants={itemAnimation} className="overflow-hidden rounded-2xl bg-paper shadow-sm">
                      {/* The cover photo */}
                      {item.photos.length > 0 ? (
                        <AuthImage path={`/listings/photos/${item.photos[0].id}/file`} alt={item.title} className="h-40 w-full object-cover" />
                      ) : (
                        <div className="flex h-40 w-full items-center justify-center bg-forest-100 text-forest-500">
                          <ImageOff size={28} />
                        </div>
                      )}
                      <div className="p-4">
                        <div className="flex items-start justify-between gap-3">
                          <p className="font-semibold text-forest-900">{item.title}</p>
                          <span className={`shrink-0 rounded-full px-2.5 py-0.5 text-xs font-semibold ${state.style}`}>{state.label}</span>
                        </div>
                        <p className="mt-1 truncate text-sm text-muted">
                          Unit {item.unit_number} · {item.property_name} · {money(item.rent_amount)}
                        </p>
                        <p className="mt-1 flex items-center gap-1.5 text-xs text-muted">
                          <Eye size={13} /> {item.views} view{item.views === 1 ? '' : 's'} · {item.photos.length} photo{item.photos.length === 1 ? '' : 's'}
                        </p>
                        <div className="mt-3 flex gap-2">
                          <button onClick={() => setSharing(item)} className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-forest-500 py-2.5 text-sm font-semibold text-white hover:bg-forest-700">
                            <Share2 size={16} /> Share
                          </button>
                          <button onClick={() => setEditing(item)} aria-label="Edit listing" className="rounded-xl bg-forest-100 px-3.5 text-forest-700 hover:bg-forest-200">
                            <Pencil size={16} />
                          </button>
                          <button onClick={() => setDeleting(item)} aria-label="Delete listing" className="rounded-xl bg-terracotta/10 px-3.5 text-terracotta hover:bg-terracotta hover:text-white">
                            <Trash2 size={16} />
                          </button>
                        </div>
                      </div>
                    </motion.div>
                  )
                })}
              </motion.div>
            </div>
          )}
        </>
      )}

      {/* Make a listing */}
      <Modal open={creatingFor !== null} title="Make a listing" onClose={() => setCreatingFor(null)}>
        {creatingFor && (
          <ListingForm
            unit={creatingFor}
            user={user}
            onCancel={() => setCreatingFor(null)}
            onSaved={async (id) => {
              setCreatingFor(null)
              // Reload, then open the share panel for the new listing straight away
              const result = await load()
              const made = result && result.listings.find((item) => item.id === id)
              if (made) setSharing(made)
            }}
          />
        )}
      </Modal>

      {/* Edit a listing */}
      <Modal open={editing !== null} title="Edit listing" onClose={() => setEditing(null)}>
        {editing && (
          <ListingForm
            key={editing.id}
            listing={editing}
            user={user}
            onCancel={() => setEditing(null)}
            onSaved={() => {
              setEditing(null)
              load()
            }}
          />
        )}
      </Modal>

      {/* Share a listing */}
      <Modal open={sharing !== null} title="Share this listing" onClose={() => setSharing(null)}>
        {sharing && (
          <ShareSheet
            listing={sharing}
            onChanged={async () => {
              // Reload, and show the fresh link
              const result = await load()
              setSharing(result ? result.listings.find((item) => item.id === sharing.id) || null : null)
            }}
          />
        )}
      </Modal>

      {/* Delete a listing */}
      <ConfirmDialog
        open={deleting !== null}
        title="Delete this listing?"
        message={deleting ? `Delete "${deleting.title}" and its photos? The link will stop working. The unit itself is not affected.` : ''}
        confirmLabel="Delete"
        onClose={() => setDeleting(null)}
        onConfirm={async () => {
          await deleteListing(deleting.id)
          setDeleting(null)
          load()
        }}
      />
    </div>
  )
}