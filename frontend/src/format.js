// Turn a number into shillings, like 48000 becomes "KSh 48,000"
export function money(amount) {
  return `KSh ${Number(amount).toLocaleString('en-US')}`
}

// Turn a date like "2026-10-14" into "14 Oct 2026"
export function formatDate(isoDate) {
  // Adding a time stops the date from shifting by a day in some time zones
  return new Date(`${isoDate}T00:00:00`).toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })
}

// Make a link that opens WhatsApp with a message already typed
export function whatsappLink(phone, message) {
  // Our saved phone numbers are already in the 254... format that WhatsApp needs
  return `https://wa.me/${phone}?text=${encodeURIComponent(message)}`
}