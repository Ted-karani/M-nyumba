// rules.js - which requests can wait on the phone until there is signal, and which answers the phone remembers
// (plain functions with no browser parts, so they can be tested)

// Requests saved on the phone when there is no signal, and sent later.
// Money is never in this list: a payment must always be confirmed by the server.
// "key: true" means the phone also sends a secret number, so the server can ignore a repeat.
export const QUEUEABLE = [
  { kind: 'repair', method: 'POST', pattern: /^\/maintenance$/, label: 'New repair report', key: true },
  { kind: 'repair_update', method: 'PUT', pattern: /^\/maintenance\/(\d+)$/, label: 'Repair update' },
  { kind: 'unit_status', method: 'PUT', pattern: /^\/work\/units\/(\d+)\/status$/, label: 'Unit status change' },
  { kind: 'item', method: 'PUT', pattern: /^\/inspections\/items\/(\d+)$/, label: 'Checklist rating or note', merge: true },
  { kind: 'photo', method: 'POST', pattern: /^\/inspections\/(\d+)\/photos$/, label: 'Checklist photo', key: true, multipart: true },
]

// Locking a checklist always needs the server (it checks that every area is rated)
export const GUARDED = [{ method: 'POST', pattern: /^\/inspections\/(\d+)\/(finalize|lock|complete)$/ }]

// Pages whose last answer the phone remembers, so they open without signal (the path includes any ?question)
export const CACHEABLE = [
  /^\/auth\/me$/,
  /^\/setup\/status$/,
  /^\/legal\/status$/,
  /^\/work\/properties$/,
  /^\/maintenance(\?.*)?$/,
  /^\/inspections\/lease\/\d+$/,
]

// A photo that is still on the phone has an id like local-abc123, and these addresses
export const LOCAL_PHOTO = /^\/inspections\/photos\/(local-[\w-]+)(\/file)?$/

// Find the rule for a request (or nothing)
export function matchQueueable(method, path) {
  const clean = path.split('?')[0]
  return QUEUEABLE.find((rule) => rule.method === method && rule.pattern.test(clean)) || null
}

// Is this request one that always needs the server, but must wait for waiting changes first?
export function isGuarded(method, path) {
  const clean = path.split('?')[0]
  return GUARDED.some((rule) => rule.method === method && rule.pattern.test(clean))
}

// Does the phone remember the answer to this address?
export function isCacheable(path) {
  return CACHEABLE.some((pattern) => pattern.test(path))
}