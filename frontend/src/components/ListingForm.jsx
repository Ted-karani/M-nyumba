// Import the React tools we need
import { useEffect, useState } from 'react'
// Import the icons we use
import { Camera, Loader2, Plus, Trash2, X } from 'lucide-react'
// Import our own files
import { createListing, deleteListingPhoto, updateListing, uploadListingPhoto } from '../api'
import { compressImage } from '../inspection'
import { money, phoneLocal } from '../format'
import AuthImage from './AuthImage'
import { Field, inputClass } from './Field'

// Ideas for amenities (people can add their own too)
const PRESET_AMENITIES = [
  'Water available',
  '24-hour security',
  'Parking',
  'Tiled floors',
  'Own bathroom',
  'Fenced compound',
  'Near the matatu stage',
  'Wi-Fi ready',
]

// The most photos a listing can have
const MAX_PHOTOS = 10

// The form for making a listing for an empty unit, or editing one
export default function ListingForm({ unit, listing, user, onSaved, onCancel }) {
  // The id of the listing once it exists (it exists already when editing)
  const [savedId, setSavedId] = useState(listing ? listing.id : null)
  // What the person has typed so far
  const [title, setTitle] = useState(listing?.title ?? '')
  const [description, setDescription] = useState(listing?.description ?? '')
  const [amenities, setAmenities] = useState(listing?.amenities ?? [])
  const [custom, setCustom] = useState('')
  const [availableFrom, setAvailableFrom] = useState(listing?.available_from ?? '')
  const [contactName, setContactName] = useState(listing?.contact_name ?? user.full_name)
  const [contactPhone, setContactPhone] = useState(listing ? phoneLocal(listing.contact_phone) : phoneLocal(user.phone || ''))
  const [showAddress, setShowAddress] = useState(listing?.show_exact_address ?? false)
  const [active, setActive] = useState(listing?.is_active ?? true)
  // The photos already saved, and the new ones waiting to be sent
  const [photos, setPhotos] = useState(listing?.photos ?? [])
  const [newFiles, setNewFiles] = useState([])
  // The error message to show (empty means none)
  const [error, setError] = useState('')
  // True while we wait for the backend
  const [busy, setBusy] = useState(false)

  // The facts about the unit (when making a new listing they come from the unit, otherwise from the listing)
  const rent = listing ? listing.rent_amount : unit.rent_amount
  const unitName = listing ? `Unit ${listing.unit_number}` : `Unit ${unit.unit_number}`
  const where = listing ? listing.property_name : unit.property_name

  // Let go of the preview pictures when this form closes
  useEffect(() => {
    return () => newFiles.forEach((item) => URL.revokeObjectURL(item.preview))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Tick or untick an amenity
  function toggleAmenity(name) {
    setAmenities(amenities.includes(name) ? amenities.filter((item) => item !== name) : [...amenities, name].slice(0, 12))
  }

  // Add an amenity the person typed
  function addCustom() {
    const text = custom.trim().slice(0, 40)
    if (text && !amenities.some((item) => item.toLowerCase() === text.toLowerCase())) setAmenities([...amenities, text].slice(0, 12))
    setCustom('')
  }

  // Choose photos
  function handleFiles(event) {
    const chosen = Array.from(event.target.files)
    event.target.value = ''
    setError('')
    const room = MAX_PHOTOS - photos.length - newFiles.length
    if (chosen.length > room) setError(`A listing can have at most ${MAX_PHOTOS} photos.`)
    const added = chosen.slice(0, Math.max(0, room)).map((file) => ({ file, preview: URL.createObjectURL(file) }))
    setNewFiles([...newFiles, ...added])
  }

  // Remove a photo that was chosen but not sent yet
  function dropNew(index) {
    URL.revokeObjectURL(newFiles[index].preview)
    setNewFiles(newFiles.filter((_, i) => i !== index))
  }

  // Delete a photo that is already saved
  async function dropSaved(photo) {
    setError('')
    try {
      await deleteListingPhoto(photo.id)
      setPhotos(photos.filter((item) => item.id !== photo.id))
    } catch (err) {
      setError(err.message)
    }
  }

  // Run when the form is sent
  async function handleSubmit(event) {
    // Stop the page from reloading
    event.preventDefault()
    // Clear any old error and show the loading state
    setError('')
    // A title typed by hand must be long enough
    if (title.trim() !== '' && title.trim().length < 3) {
      setError('The title must be at least 3 characters.')
      return
    }
    setBusy(true)
    try {
      let id = savedId
      if (id === null) {
        // Make the listing
        const created = await createListing({
          unit_id: unit.unit_id,
          title: title.trim() || null,
          description: description.trim() || null,
          amenities,
          available_from: availableFrom || null,
          contact_name: contactName.trim() || null,
          contact_phone: contactPhone.trim() || null,
          show_exact_address: showAddress,
        })
        id = created.id
        setSavedId(id)
      } else {
        // Save the changes
        const body = {
          description: description.trim() || null,
          amenities,
          available_from: availableFrom || null,
          contact_name: contactName.trim() || null,
          contact_phone: contactPhone.trim() || null,
          show_exact_address: showAddress,
          is_active: active,
        }
        if (title.trim()) body.title = title.trim()
        await updateListing(id, body)
      }
      // Send the new photos one by one (the ones that went are removed from the waiting list)
      let waiting = [...newFiles]
      for (const item of newFiles) {
        const ready = await compressImage(item.file)
        const form = new FormData()
        form.append('file', ready)
        await uploadListingPhoto(id, form)
        URL.revokeObjectURL(item.preview)
        waiting = waiting.filter((other) => other !== item)
        setNewFiles(waiting)
      }
      onSaved(id)
    } catch (err) {
      // Show the error under the form (if the listing was made, a second press only saves and sends what is left)
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <p className="rounded-xl bg-forest-100 px-4 py-3 text-sm text-forest-700">
        {unitName} · {where} · <span className="font-semibold">{money(rent)}</span> a month
      </p>

      <Field label="Headline" hint="Leave empty and we will write one, like “Bedsitter for rent in Makutano”.">
        <input className={inputClass} value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Spacious bedsitter near the stage" maxLength={120} autoComplete="off" />
      </Field>

      <Field label="Description (optional)">
        <textarea className={`${inputClass} min-h-24`} value={description} onChange={(e) => setDescription(e.target.value)} maxLength={2000} placeholder="Quiet compound, water all day, 5 minutes from the main road..." />
      </Field>

      {/* The amenities */}
      <div>
        <span className="mb-2 block text-sm font-medium">What comes with it</span>
        <div className="flex flex-wrap gap-2">
          {[...PRESET_AMENITIES, ...amenities.filter((item) => !PRESET_AMENITIES.includes(item))].map((name) => (
            <button
              key={name}
              type="button"
              onClick={() => toggleAmenity(name)}
              className={`rounded-full px-3 py-1.5 text-xs font-semibold transition ${
                amenities.includes(name) ? 'bg-forest-900 text-white' : 'bg-forest-100 text-forest-700 hover:bg-forest-200'
              }`}
            >
              {name}
            </button>
          ))}
        </div>
        <div className="mt-2 flex gap-2">
          <input
            className={inputClass}
            value={custom}
            onChange={(e) => setCustom(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault()
                addCustom()
              }
            }}
            placeholder="Add your own"
            maxLength={40}
          />
          <button type="button" onClick={addCustom} aria-label="Add amenity" className="shrink-0 rounded-xl bg-forest-100 px-4 text-forest-700 hover:bg-forest-200">
            <Plus size={18} />
          </button>
        </div>
      </div>

      {/* The photos */}
      <div>
        <span className="mb-2 block text-sm font-medium">
          Photos ({photos.length + newFiles.length}/{MAX_PHOTOS})
        </span>
        <div className="flex flex-wrap gap-2">
          {photos.map((photo, index) => (
            <div key={photo.id} className="relative">
              <AuthImage path={`/listings/photos/${photo.id}/file`} alt="Listing photo" className="h-20 w-20 rounded-xl object-cover" />
              {index === 0 && <span className="absolute bottom-1 left-1 rounded bg-forest-900/80 px-1.5 py-0.5 text-[10px] font-bold text-white">Cover</span>}
              <button type="button" onClick={() => dropSaved(photo)} aria-label="Delete photo" className="absolute -right-1.5 -top-1.5 rounded-full bg-terracotta p-1 text-white shadow">
                <Trash2 size={12} />
              </button>
            </div>
          ))}
          {newFiles.map((item, index) => (
            <div key={item.preview} className="relative">
              <img src={item.preview} alt="New photo" className="h-20 w-20 rounded-xl object-cover" />
              <button type="button" onClick={() => dropNew(index)} aria-label="Remove photo" className="absolute -right-1.5 -top-1.5 rounded-full bg-forest-900 p-1 text-white shadow">
                <X size={12} />
              </button>
            </div>
          ))}
          {photos.length + newFiles.length < MAX_PHOTOS && (
            <label className="flex h-20 w-20 cursor-pointer items-center justify-center rounded-xl border-2 border-dashed border-forest-200 text-forest-500 transition hover:border-forest-500">
              <Camera size={22} />
              <input type="file" accept="image/*" multiple className="hidden" onChange={handleFiles} />
            </label>
          )}
        </div>
        <p className="mt-2 text-xs text-muted">The first photo is the cover. Good light and a clean room help a lot.</p>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <Field label="Contact name">
          <input className={inputClass} value={contactName} onChange={(e) => setContactName(e.target.value)} maxLength={80} autoComplete="off" />
        </Field>
        <Field label="Contact phone" hint="Shown publicly.">
          <input className={inputClass} type="tel" inputMode="tel" value={contactPhone} onChange={(e) => setContactPhone(e.target.value)} placeholder="0712 345 678" autoComplete="off" />
        </Field>
      </div>

      <Field label="Available from (optional)">
        <input className={inputClass} type="date" value={availableFrom} onChange={(e) => setAvailableFrom(e.target.value)} />
      </Field>

      {/* Privacy and visibility switches */}
      <button type="button" onClick={() => setShowAddress(!showAddress)} className="flex w-full items-center justify-between gap-3 rounded-xl bg-cream px-4 py-3 text-left">
        <span>
          <span className="block text-sm font-semibold text-forest-900">Show the building name and exact address</span>
          <span className="block text-xs text-muted">{showAddress ? 'Visible to everyone with the link.' : 'Hidden. People see only the area, like “Makutano, Meru”.'}</span>
        </span>
        <span className={`relative h-6 w-11 shrink-0 rounded-full transition ${showAddress ? 'bg-forest-500' : 'bg-forest-200'}`}>
          <span className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-all ${showAddress ? 'left-[22px]' : 'left-0.5'}`} />
        </span>
      </button>

      {savedId !== null && listing && (
        <button type="button" onClick={() => setActive(!active)} className="flex w-full items-center justify-between gap-3 rounded-xl bg-cream px-4 py-3 text-left">
          <span>
            <span className="block text-sm font-semibold text-forest-900">{active ? 'The link is on' : 'The link is switched off'}</span>
            <span className="block text-xs text-muted">{active ? 'People can see this listing.' : 'The link says the listing is not available.'}</span>
          </span>
          <span className={`relative h-6 w-11 shrink-0 rounded-full transition ${active ? 'bg-forest-500' : 'bg-forest-200'}`}>
            <span className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-all ${active ? 'left-[22px]' : 'left-0.5'}`} />
          </span>
        </button>
      )}

      {/* The error appears here if something goes wrong */}
      {error && (
        <div role="alert" className="rounded-xl bg-terracotta/10 px-4 py-3 text-sm font-medium text-terracotta">
          {error}
        </div>
      )}

      <div className="flex gap-3 pt-2">
        <button type="button" onClick={onCancel} className="flex-1 rounded-xl bg-forest-100 py-3 font-semibold text-forest-700 hover:bg-forest-200">
          Cancel
        </button>
        <button
          type="submit"
          disabled={busy}
          className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-forest-900 py-3 font-semibold text-white hover:bg-forest-700 disabled:opacity-70"
        >
          {busy && <Loader2 size={18} className="animate-spin" />}
          {listing || savedId !== null ? 'Save changes' : 'Make listing'}
        </button>
      </div>
    </form>
  )
}