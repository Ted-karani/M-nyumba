// The kinds of document, and the words we show for them
export const DOCUMENT_KINDS = [
  { key: 'lease_agreement', label: 'Lease agreement' },
  { key: 'title_deed', label: 'Title deed' },
  { key: 'permit', label: 'Permit or licence' },
  { key: 'insurance', label: 'Insurance' },
  { key: 'id_copy', label: 'ID copy' },
  { key: 'receipt', label: 'Receipt or invoice' },
  { key: 'other', label: 'Other' },
]

// Get the words for a kind (or the kind itself if we do not know it)
export function kindLabel(key) {
  const found = DOCUMENT_KINDS.find((kind) => kind.key === key)
  return found ? found.label : key
}

// The biggest file we accept: 10 MB (the backend checks this too)
export const MAX_FILE_BYTES = 10 * 1024 * 1024
// The file endings we accept (the backend checks the inside of the file too)
export const ACCEPT = '.pdf,.jpg,.jpeg,.png,.webp,.doc,.docx,.xls,.xlsx'

// Write a file size in words, like "240 KB" or "2.4 MB"
export function fileSize(bytes) {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

// Write how far away a date is, like "Expired 3 days ago" or "Expires in 12 days"
export function expiryText(days) {
  if (days === null || days === undefined) return ''
  if (days < 0) return `Expired ${-days} day${days === -1 ? '' : 's'} ago`
  if (days === 0) return 'Expires today'
  return `Expires in ${days} day${days === 1 ? '' : 's'}`
}