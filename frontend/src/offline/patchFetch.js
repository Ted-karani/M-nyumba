// patchFetch.js - replaces the app's "fetch" with one that copes with a missing or slow signal.
// Every screen keeps working exactly as before: this layer saves changes for later and remembers answers.

// Import our own files
import { API_URL } from '../api'
import * as engine from './engine'
import * as store from './db'
import { LOCAL_PHOTO, isCacheable, isGuarded, matchQueueable } from './rules'
import { overlayInspections, overlayRepairs, overlayWork } from './overlay'

const NO_SIGNAL = 'There is no signal right now. Please try again when you are back online.'

// Make an answer that looks like the server's
const reply = (data, status = 200, extra = {}) => new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json', ...extra } })

// Show waiting changes on top of what the server said
async function withOverlays(path, data, userId) {
  try {
    const entries = await store.outboxAll(userId)
    if (!entries.some((entry) => entry.status === 'pending')) return data
    const clean = path.split('?')[0]
    if (/^\/inspections\/lease\/\d+$/.test(clean)) return overlayInspections(data, entries)
    if (clean === '/work/properties') return overlayWork(data, entries)
    if (clean === '/maintenance') return overlayRepairs(data, entries)
  } catch {
    // If the waiting changes cannot be read, show the data as it is
  }
  return data
}

// A photo that is still on this phone
async function handleLocalPhoto(method, localId, isFile) {
  if (method === 'GET' && isFile) {
    const blob = await engine.localPhotoBlob(localId)
    return blob ? new Response(blob, { status: 200, headers: { 'Content-Type': blob.type || 'image/jpeg' } }) : reply({ detail: 'This photo is not on this phone any more' }, 404)
  }
  if (method === 'DELETE') {
    const removed = await engine.deleteLocalPhoto(localId)
    return removed ? new Response(null, { status: 204 }) : reply({ detail: 'Could not remove this photo. Please try again when you are online.' }, 409)
  }
  return reply({ detail: 'Not available' }, 404)
}

// Reading something the phone remembers: ask the server, and use the saved copy if there is no answer in time
async function readRemembered(url, init, path, userId) {
  try {
    const response = await engine.fetchWithTimeout(url, init, 12000)
    if (!response.ok) {
      engine.noteOnline()
      return response
    }
    const data = await response.json()
    engine.noteOnline()
    store.cachePut(`${userId}|${path}`, data).catch(() => {})
    return reply(await withOverlays(path, data, userId))
  } catch {
    engine.noteOffline()
    const saved = await store.cacheGet(`${userId}|${path}`).catch(() => null)
    if (saved) return reply(await withOverlays(path, saved.value, userId), 200, { 'X-From-Phone': '1' })
    return reply({ detail: 'This is not saved on your phone yet. Open it once when you have signal.' }, 503)
  }
}

// Saving something for later: send it now if there is signal, and keep it on the phone if not
async function saveForLater(rule, url, init, path) {
  const headers = new Headers(init.headers || {})
  let key = null
  if (rule.key) {
    key = engine.uuid()
    headers.set('Idempotency-Key', key)
  }
  const keep = async () => {
    let body = null
    let fields = null
    let file = null
    let fileName = null
    if (init.body instanceof FormData) {
      fields = {}
      for (const [name, value] of init.body.entries()) {
        if (value instanceof Blob) {
          file = value
          fileName = value.name || 'photo.jpg'
        } else {
          fields[name] = value
        }
      }
    } else if (typeof init.body === 'string') {
      try {
        body = JSON.parse(init.body)
      } catch {
        body = null
      }
    }
    const entry = await engine.enqueueRequest({ rule, path, method: rule.method, body, fields, file, fileName, key })
    // An answer that looks like success, so the screen carries on
    const answer = rule.kind === 'photo' ? { id: `local-${entry.id}`, queued: true } : rule.kind === 'repair' ? { id: -1, queued: true, ...(body || {}) } : { queued: true }
    return reply(answer, 202, { 'X-Saved-On-Phone': '1' })
  }
  if (navigator.onLine === false) {
    try {
      return await keep()
    } catch {
      return reply({ detail: NO_SIGNAL }, 503)
    }
  }
  try {
    const response = await engine.fetchWithTimeout(url, { ...init, headers }, rule.multipart ? 60000 : 25000)
    engine.noteOnline()
    return response
  } catch {
    engine.noteOffline()
    try {
      return await keep()
    } catch {
      return reply({ detail: NO_SIGNAL }, 503)
    }
  }
}

// Locking a checklist: needs the server, and the waiting ratings and photos must go first
async function finishChecklist(input, init) {
  if (navigator.onLine === false) return reply({ detail: 'Locking a checklist needs signal. Your ratings are saved on this phone and will be sent first.' }, 503)
  await engine.syncNow()
  if ((await engine.pendingOfKinds(['item', 'photo'])) > 0) return reply({ detail: 'Your latest ratings and photos are still being sent. Please try again in a moment.' }, 409)
  try {
    const response = await engine.rawFetch(input, init)
    engine.noteOnline()
    return response
  } catch {
    engine.noteOffline()
    return reply({ detail: NO_SIGNAL }, 503)
  }
}

// Switch it on (once)
export function installOfflineFetch() {
  if (window.__estateloomFetch) return
  window.__estateloomFetch = true
  window.fetch = async function estateloomFetch(input, init = {}) {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url
    // Anything that is not a request to the EstateLoom server is left alone
    if (!url || !url.startsWith(API_URL)) return engine.rawFetch(input, init)
    const path = url.slice(API_URL.length)
    const method = String(init.method || 'GET').toUpperCase()
    const userId = engine.currentUserId()

    if (userId) {
      const local = path.match(LOCAL_PHOTO)
      if (local) return handleLocalPhoto(method, local[1], Boolean(local[2]))
      if (method === 'GET' && isCacheable(path)) return readRemembered(url, init, path, userId)
      if (isGuarded(method, path)) return finishChecklist(input, init)
      const rule = matchQueueable(method, path)
      if (rule) return saveForLater(rule, url, init, path)
    }

    // Everything else: normal, but a missing signal gives a friendly message
    try {
      const response = await engine.rawFetch(input, init)
      engine.noteOnline()
      return response
    } catch {
      engine.noteOffline()
      return reply({ detail: NO_SIGNAL }, 503)
    }
  }
}