// prepare.js - "Save for offline": remember a caretaker's units and checklists while there is signal

// Import our own files
import { API_URL, getToken } from '../api'
import * as store from './db'
import { currentUserId } from './engine'

// When it was last done (nothing if never)
export async function lastPrepared() {
  const userId = currentUserId()
  if (!userId) return null
  const saved = await store.cacheGet(`${userId}|__prepared`).catch(() => null)
  return saved ? saved.value : null
}

// Download the lists and every checklist (they are remembered by the layer in patchFetch.js)
export async function prepareOffline(onProgress) {
  const userId = currentUserId()
  const token = getToken()
  if (!userId || !token) throw new Error('Please sign in first')
  const headers = { Authorization: `Bearer ${token}` }
  const get = async (path) => {
    const response = await window.fetch(API_URL + path, { headers })
    if (!response.ok) throw new Error('Could not save everything. Check your signal and try again.')
    return response.json()
  }
  await get('/auth/me')
  await get('/setup/status')
  const data = await get('/work/properties')
  const properties = Array.isArray(data) ? data : data.properties || []
  const leaseIds = [...new Set(properties.flatMap((property) => (property.units || []).map((unit) => unit.lease_id ?? unit.active_lease_id ?? (unit.lease ? unit.lease.id : null))).filter(Boolean))]
  let done = 0
  for (const id of leaseIds) {
    await get(`/inspections/lease/${id}`)
    done += 1
    if (onProgress) onProgress(done, leaseIds.length)
  }
  const result = { at: Date.now(), checklists: leaseIds.length }
  await store.cachePut(`${userId}|__prepared`, result).catch(() => {})
  return result
}