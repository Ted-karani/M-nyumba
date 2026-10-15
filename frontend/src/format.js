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

// Today's date as "2026-10-14", using the phone's own clock and time zone
export function todayISO() {
  // The current date and time
  const now = new Date()
  // Month and day need a zero in front when they are a single digit
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  // Put the three parts together
  return `${now.getFullYear()}-${month}-${day}`
}

// This month as "2026-10"
export function currentPeriod() {
  return todayISO().slice(0, 7)
}

// Move a month forwards or backwards: shiftPeriod("2026-10", 1) is "2026-11", and -1 gives "2026-09"
export function shiftPeriod(period, change) {
  // Split "2026-10" into the year and the month number
  const [year, month] = period.split('-').map(Number)
  // JavaScript counts months from 0, so we take one off the month number before adding the change
  const moved = new Date(year, month - 1 + change, 1)
  // Write it back as "YYYY-MM"
  return `${moved.getFullYear()}-${String(moved.getMonth() + 1).padStart(2, '0')}`
}

// The month after a given one: "2026-10" becomes "2026-11" (and "2026-12" becomes "2027-01")
export function nextPeriod(period) {
  return shiftPeriod(period, 1)
}

// Write a month out in words: "2026-10" becomes "October 2026"
export function monthLabel(period) {
  // Split "2026-10" into the year and the month number
  const [year, month] = period.split('-').map(Number)
  return new Date(year, month - 1, 1).toLocaleDateString('en-GB', { month: 'long', year: 'numeric' })
}

// Show a saved phone number the way people write it: 254712345678 becomes "0712 345 678"
export function phoneLocal(phone) {
  // Nothing to show
  if (!phone) return ''
  // Swap the 254 at the front for a 0
  const local = phone.startsWith('254') ? `0${phone.slice(3)}` : phone
  // Add spaces so it is easy to read
  if (local.length === 10) return `${local.slice(0, 4)} ${local.slice(4, 7)} ${local.slice(7)}`
  return local
}

// Get the first letters of a name, like "Grace Njeri" becomes "GN"
export function initials(name) {
  return name
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0].toUpperCase())
    .join('')
}

// The words we show for each kind of charge
export const CHARGE_LABELS = {
  rent: 'Rent',
  deposit: 'Deposit',
  water: 'Water',
  wifi: 'Wi-Fi',
  electricity: 'Electricity',
  other: 'Other',
}

// The words we show for each way of paying
export const METHOD_LABELS = { mpesa: 'M-Pesa', cash: 'Cash', bank: 'Bank' }