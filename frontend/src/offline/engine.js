// engine.js - keeps the list of changes waiting to be sent, and sends them when there is signal

// Import our own files
import { API_URL, getToken } from '../api'
import * as store from './db'
import { mergeBodies } from './overlay'

// The browser's real "fetch", saved before we replace it (this file is loaded before that happens)
export const rawFetch = window.fetch.bind(window)

// What the screens show: are we offline, how many changes wait, and so on
let state = { offline: !navigator.onLine, pending: 0, failed: 0, syncing: false, needsSignIn: false, justSynced: false }
const listeners = new Set()
export const getState = () => state
export function subscribe(listener) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}
// Change the state, and tell the screens (only if something really changed)
function publish(patch) {
  const next = { ...state, ...patch }
  if (JSON.stringify(next) === JSON.stringify(state)) return
  state = next
  listeners.forEach((listener) => listener(state))
}

// Things we remember while the app is open: the changes being sent now, the real ids of photos we sent, and the pictures themselves
const inFlight = new Set()
const serverPhotoIds = new Map()
const recentBlobs = new Map()

// A random id for a waiting change or a secret number
export function uuid() {
  if (window.crypto && window.crypto.randomUUID) return window.crypto.randomUUID()
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (letter) => {
    const number = (Math.random() * 16) | 0
    return (letter === 'x' ? number : (number & 3) | 8).toString(16)
  })
}

// Who is signed in (read from the sign-in token; this is only used to keep people's saved things apart)
export function currentUserId() {
  const token = getToken()
  if (!token) return null
  try {
    const part = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')
    return String(JSON.parse(atob(part)).sub)
  } catch {
    return null
  }
}

// A request that gives up after some seconds
export async function fetchWithTimeout(url, init, ms) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), ms)
  try {
    return await rawFetch(url, { ...init, signal: controller.signal })
  } finally {
    clearTimeout(timer)
  }
}

// The screens learn whether we are online from how requests go
export function noteOnline() {
  if (state.offline) {
    publish({ offline: false })
    syncNow()
  }
}
export function noteOffline() {
  if (!state.offline) publish({ offline: true })
}

// Count what is waiting
export async function refreshCounts() {
  const userId = currentUserId()
  if (!userId) {
    publish({ pending: 0, failed: 0 })
    return
  }
  try {
    const entries = await store.outboxAll(userId)
    publish({ pending: entries.filter((entry) => entry.status === 'pending').length, failed: entries.filter((entry) => entry.status === 'failed').length })
  } catch {
    publish({ pending: 0, failed: 0 })
  }
}

// Save a change on the phone, to be sent later
export async function enqueueRequest({ rule, path, method, body, fields, file, fileName, key }) {
  const userId = currentUserId()
  if (!userId) throw new Error('Not signed in')
  const cleanPath = path.split('?')[0]
  let entry = null
  // A newer rating of the same area replaces the waiting one, so only the latest is sent
  if (rule.merge) {
    const all = await store.outboxAll(userId)
    entry = all.find((row) => row.status === 'pending' && row.method === method && row.path === cleanPath && !inFlight.has(row.id)) || null
    if (entry) {
      entry.body = mergeBodies(entry.body, body)
      await store.outboxPut(entry)
    }
  }
  if (!entry) {
    entry = { id: uuid(), userId, method, path: cleanPath, kind: rule.kind, label: rule.label, createdAt: Date.now(), status: 'pending', attempts: 0, error: null, body: body ?? null, fields: fields ?? null, file: file ?? null, fileName: fileName ?? null, key: key ?? null }
    await store.outboxPut(entry)
  }
  await refreshCounts()
  return entry
}

// Change one waiting entry
async function mark(entry, patch) {
  Object.assign(entry, patch)
  await store.outboxPut(entry).catch(() => {})
}

// Send one waiting change. The answer is: "sent", "failed" (the server refused it), "later" (try again), or "sign-in"
async function sendEntry(entry, token) {
  const headers = { Authorization: `Bearer ${token}` }
  let body
  if (entry.file) {
    body = new FormData()
    Object.entries(entry.fields || {}).forEach(([name, value]) => body.append(name, value))
    body.append('file', entry.file, entry.fileName || 'photo.jpg')
  } else if (entry.body !== null && entry.body !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(entry.body)
  }
  if (entry.key) headers['Idempotency-Key'] = entry.key
  let response
  try {
    response = await fetchWithTimeout(API_URL + entry.path, { method: entry.method, headers, body }, entry.file ? 60000 : 25000)
  } catch {
    noteOffline()
    await mark(entry, { attempts: entry.attempts + 1 })
    return 'later'
  }
  noteOnline()
  if (response.ok) {
    // Remember the real id of a photo we sent, so a photo shown from the phone can still be opened and removed
    if (entry.kind === 'photo') {
      try {
        const data = await response.json()
        if (data && data.id) {
          serverPhotoIds.set(`local-${entry.id}`, data.id)
          recentBlobs.set(entry.id, entry.file)
        }
      } catch {
        // The photo was sent; we just could not read the answer
      }
    }
    await store.outboxDelete(entry.id).catch(() => {})
    return 'sent'
  }
  if (response.status === 401) {
    publish({ needsSignIn: true })
    return 'sign-in'
  }
  let detail = ''
  try {
    const data = await response.clone().json()
    detail = typeof data.detail === 'string' ? data.detail : ''
  } catch {
    // No readable reason
  }
  if (response.status === 429 || response.status >= 500 || (response.status === 409 && detail.includes('still being processed'))) {
    await mark(entry, { attempts: entry.attempts + 1 })
    return 'later'
  }
  await mark(entry, { status: 'failed', error: detail || `The server did not accept this (code ${response.status})` })
  return 'failed'
}

// Send everything that is waiting, one by one, in the order it happened
async function runSync() {
  const userId = currentUserId()
  const token = getToken()
  if (!userId || !token || navigator.onLine === false) return
  let entries
  try {
    entries = (await store.outboxAll(userId)).filter((entry) => entry.status === 'pending').sort((a, b) => a.createdAt - b.createdAt)
  } catch {
    return
  }
  if (entries.length === 0) {
    await refreshCounts()
    return
  }
  publish({ syncing: true, needsSignIn: false })
  let sent = 0
  for (const entry of entries) {
    inFlight.add(entry.id)
    let outcome
    try {
      outcome = await sendEntry(entry, token)
    } finally {
      inFlight.delete(entry.id)
    }
    if (outcome === 'sent') {
      sent += 1
      continue
    }
    if (outcome === 'failed') continue
    // No signal, or the sign-in ran out: stop and try again later
    break
  }
  await refreshCounts()
  publish({ syncing: false })
  if (sent > 0 && state.pending === 0) {
    publish({ justSynced: true })
    setTimeout(() => publish({ justSynced: false }), 10000)
  }
}

// Only one sending at a time (asking again while it runs just waits for the same one)
let currentRun = null
export function syncNow() {
  if (!currentRun) currentRun = runSync().finally(() => (currentRun = null))
  return currentRun
}

// How many waiting changes of these kinds there are
export async function pendingOfKinds(kinds) {
  const userId = currentUserId()
  if (!userId) return 0
  const entries = await store.outboxAll(userId).catch(() => [])
  return entries.filter((entry) => entry.status === 'pending' && kinds.includes(entry.kind)).length
}

// For the "waiting to be sent" panel
export async function getEntries() {
  const userId = currentUserId()
  if (!userId) return []
  const entries = await store.outboxAll(userId).catch(() => [])
  return entries.sort((a, b) => a.createdAt - b.createdAt)
}
export async function discardEntry(id) {
  await store.outboxDelete(id).catch(() => {})
  await refreshCounts()
}
export async function retryEntry(id) {
  const entries = await getEntries()
  const entry = entries.find((row) => row.id === id)
  if (entry) await mark(entry, { status: 'pending', error: null, attempts: 0 })
  await refreshCounts()
  syncNow()
}
export async function retryAll() {
  const entries = await getEntries()
  for (const entry of entries) if (entry.status === 'failed') await mark(entry, { status: 'pending', error: null, attempts: 0 })
  await refreshCounts()
  syncNow()
}

// The picture of a photo that is still on the phone
export async function localPhotoBlob(localId) {
  const id = localId.slice(6)
  const entries = await getEntries()
  const entry = entries.find((row) => row.id === id)
  return entry ? entry.file : recentBlobs.get(id) || null
}

// Remove a photo that was taken without signal (waiting, or already sent)
export async function deleteLocalPhoto(localId) {
  const id = localId.slice(6)
  const entries = await getEntries()
  const entry = entries.find((row) => row.id === id)
  if (entry && !inFlight.has(id)) {
    await store.outboxDelete(id)
    await refreshCounts()
    return true
  }
  const serverId = serverPhotoIds.get(localId)
  if (!serverId) return false
  try {
    const response = await fetchWithTimeout(`${API_URL}/inspections/photos/${serverId}`, { method: 'DELETE', headers: { Authorization: `Bearer ${getToken()}` } }, 25000)
    return response.ok
  } catch {
    return false
  }
}

// Before logging out: send what waits, warn if anything is left, and forget this person's saved things
export async function beforeSignOut() {
  const userId = currentUserId()
  if (!userId) return true
  await refreshCounts()
  if (state.pending > 0 && navigator.onLine !== false) await syncNow()
  const left = state.pending + state.failed
  if (left > 0) {
    const one = left === 1
    const sure = window.confirm(`${left} change${one ? ' has' : 's have'} not been sent yet. If you log out now, ${one ? 'it' : 'they'} will be lost. Log out anyway?`)
    if (!sure) return false
  }
  await store.clearUser(userId).catch(() => {})
  await refreshCounts()
  return true
}

// Start watching the signal, and sending whenever it comes back
let started = false
export function startEngine() {
  if (started) return
  started = true
  window.addEventListener('online', () => {
    publish({ offline: false })
    syncNow()
  })
  window.addEventListener('offline', () => publish({ offline: true }))
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') syncNow()
  })
  // Every 20 seconds: check the signal if we think we are offline, and send what waits
  setInterval(async () => {
    if (state.offline && navigator.onLine !== false) {
      try {
        const response = await fetchWithTimeout(`${API_URL}/health`, {}, 8000)
        if (response.ok) noteOnline()
      } catch {
        // Still no signal
      }
    }
    syncNow()
  }, 20000)
  refreshCounts().then(syncNow)
}