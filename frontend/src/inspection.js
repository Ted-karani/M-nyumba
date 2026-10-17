// The four ratings, with their words and colors (the first color is for a rating that is not chosen, the second for one that is)
export const CONDITIONS = [
  { key: 'good', label: 'Good', off: 'bg-forest-100 text-forest-700 hover:bg-forest-200', on: 'bg-forest-500 text-white' },
  { key: 'fair', label: 'Fair', off: 'bg-amber/15 text-amber hover:bg-amber/25', on: 'bg-amber text-white' },
  { key: 'poor', label: 'Poor', off: 'bg-gold/20 text-forest-900 hover:bg-gold/30', on: 'bg-gold text-forest-900' },
  { key: 'damaged', label: 'Damaged', off: 'bg-terracotta/10 text-terracotta hover:bg-terracotta/20', on: 'bg-terracotta text-white' },
]

// How bad each rating is (a higher number is worse)
export const CONDITION_RANK = { good: 0, fair: 1, poor: 2, damaged: 3 }

// Get the word for a rating
export function conditionLabel(key) {
  const found = CONDITIONS.find((condition) => condition.key === key)
  return found ? found.label : 'Not checked'
}

// Write a time from the backend in words (it saves times in UTC without a "Z" on the end, so we add it)
export function formatDateTime(value) {
  const date = new Date(value.endsWith('Z') ? value : `${value}Z`)
  return date.toLocaleString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

// Shrink a photo before sending it: phone photos are often 4 to 8 MB, and about 300 KB is plenty to show a stain or a crack
export async function compressImage(file) {
  // Small pictures that are already in a normal format can go as they are
  const normal = ['image/jpeg', 'image/png', 'image/webp'].includes(file.type)
  if (normal && file.size < 600 * 1024) return file
  try {
    // Open the picture (the browser turns it the right way up for us)
    const bitmap = await createImageBitmap(file)
    // Work out the smaller size, with the longest side at most 1600 pixels
    const scale = Math.min(1, 1600 / Math.max(bitmap.width, bitmap.height))
    const canvas = document.createElement('canvas')
    canvas.width = Math.round(bitmap.width * scale)
    canvas.height = Math.round(bitmap.height * scale)
    canvas.getContext('2d').drawImage(bitmap, 0, 0, canvas.width, canvas.height)
    // Save it as a JPEG
    const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/jpeg', 0.82))
    if (!blob) throw new Error('Could not shrink the picture')
    return new File([blob], `${file.name.replace(/\.[^.]+$/, '')}.jpg`, { type: 'image/jpeg' })
  } catch {
    // If shrinking failed but the picture is a normal type, send it as it is
    if (normal) return file
    throw new Error('This kind of picture is not supported. Please use a JPG or PNG photo.')
  }
}