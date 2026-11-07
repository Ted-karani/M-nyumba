// db.js - the phone's own storage: one box for remembered answers, one for the changes waiting to be sent

const DB_NAME = 'estateloom-offline'
let opening = null

// Open the storage (once)
function openDatabase() {
  if (opening) return opening
  opening = new Promise((resolve, reject) => {
    if (typeof indexedDB === 'undefined') {
      reject(new Error('This browser cannot save things on the phone'))
      return
    }
    const request = indexedDB.open(DB_NAME, 1)
    request.onupgradeneeded = () => {
      const db = request.result
      db.createObjectStore('cache')
      db.createObjectStore('outbox', { keyPath: 'id' })
    }
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => {
      opening = null
      reject(request.error)
    }
  })
  return opening
}

// Run one change in a transaction, and wait until it is fully saved
async function write(storeName, action) {
  const db = await openDatabase()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(storeName, 'readwrite')
    action(tx.objectStore(storeName))
    tx.oncomplete = () => resolve()
    tx.onerror = () => reject(tx.error)
    tx.onabort = () => reject(tx.error)
  })
}

// Read everything in a box
async function readAll(storeName) {
  const db = await openDatabase()
  return new Promise((resolve, reject) => {
    const request = db.transaction(storeName).objectStore(storeName).getAll()
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error)
  })
}

// The remembered answers: key looks like "userId|/address"
export async function cacheGet(key) {
  const db = await openDatabase()
  return new Promise((resolve, reject) => {
    const request = db.transaction('cache').objectStore('cache').get(key)
    request.onsuccess = () => resolve(request.result || null)
    request.onerror = () => reject(request.error)
  })
}
export const cachePut = (key, value) => write('cache', (box) => box.put({ value, savedAt: Date.now() }, key))

// The changes waiting to be sent (only the signed-in person's)
export async function outboxAll(userId) {
  const all = await readAll('outbox')
  return all.filter((entry) => entry.userId === userId)
}
export const outboxPut = (entry) => write('outbox', (box) => box.put(entry))
export const outboxDelete = (id) => write('outbox', (box) => box.delete(id))

// Forget everything saved for one person (when they log out)
export async function clearUser(userId) {
  const db = await openDatabase()
  const entries = await outboxAll(userId)
  await write('outbox', (box) => entries.forEach((entry) => box.delete(entry.id)))
  await new Promise((resolve, reject) => {
    const tx = db.transaction('cache', 'readwrite')
    const request = tx.objectStore('cache').openCursor()
    request.onsuccess = () => {
      const cursor = request.result
      if (!cursor) return
      if (String(cursor.key).startsWith(`${userId}|`)) cursor.delete()
      cursor.continue()
    }
    tx.oncomplete = () => resolve()
    tx.onerror = () => reject(tx.error)
  })
}