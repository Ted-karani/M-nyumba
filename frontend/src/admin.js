// The words and colors for each state of a landlord's account
export const STATE_STYLES = {
  active: { label: 'Active', style: 'bg-forest-100 text-forest-700' },
  read_only: { label: 'Read-only', style: 'bg-amber/20 text-amber' },
  suspended: { label: 'Suspended', style: 'bg-terracotta/15 text-terracotta' },
  closed: { label: 'Closed', style: 'bg-ink/10 text-muted' },
}

// The words for each plan
export const PLAN_LABELS = { pilot: 'Pilot', paid: 'Paid' }

// The ways a landlord can pay you
export const METHOD_OPTIONS = [
  { value: 'mpesa', label: 'M-Pesa' },
  { value: 'cash', label: 'Cash' },
  { value: 'bank', label: 'Bank' },
  { value: 'other', label: 'Other' },
]

// Say in words how long a landlord's access lasts
export function accessText(account) {
  if (!account.paid_until || account.days_left === null) return 'No end date'
  if (account.days_left < 0) return `Ended ${-account.days_left} day${account.days_left === -1 ? '' : 's'} ago`
  if (account.days_left === 0) return 'Ends today'
  return `${account.days_left} day${account.days_left === 1 ? '' : 's'} left`
}

// A date some days from today, in the form a date box needs
export function daysFromToday(days) {
  return new Date(Date.now() + days * 86400000).toISOString().slice(0, 10)
}