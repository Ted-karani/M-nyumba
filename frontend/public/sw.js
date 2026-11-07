// sw.js - lets EstateLoom open without signal (it only saves the app's own files, never anyone's data)
// If you change this file, change the version number below too.

const VERSION = 'v1'
// Three small stores: the page itself, the app's code files, and the fonts
const SHELL = `estateloom-shell-${VERSION}`
const ASSETS = `estateloom-assets-${VERSION}`
const FONTS = `estateloom-fonts-${VERSION}`
// We keep only this many code files (new versions of the app make old ones useless)
const MAX_ASSETS = 80

// When the helper is installed, save the front page and the icons
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches
      .open(SHELL)
      .then((cache) => cache.addAll(['/', '/favicon.svg', '/manifest.webmanifest', '/icon-192.png']))
      .then(() => self.skipWaiting())
  )
})

// When a new version takes over, throw away the stores of old versions
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((names) => Promise.all(names.filter((name) => name.startsWith('estateloom-') && ![SHELL, ASSETS, FONTS].includes(name)).map((name) => caches.delete(name))))
      .then(() => self.clients.claim())
  )
})

// Ask the network, but give up after a few seconds (a slow signal is as bad as none)
function fetchWithTimeout(request, ms) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('slow')), ms)
    fetch(request).then(
      (response) => {
        clearTimeout(timer)
        resolve(response)
      },
      (error) => {
        clearTimeout(timer)
        reject(error)
      }
    )
  })
}

// Opening a page: use the network, but fall back to the saved page
async function pageRequest(request) {
  const cache = await caches.open(SHELL)
  try {
    const response = await fetchWithTimeout(request, 4000)
    const type = response.headers.get('content-type') || ''
    if (response.ok && type.includes('text/html')) cache.put('/', response.clone())
    return response
  } catch {
    const saved = await cache.match('/')
    if (saved) return saved
    return new Response('EstateLoom needs a signal the first time it opens. Please try again.', { status: 503, headers: { 'Content-Type': 'text/plain' } })
  }
}

// The app's code files have a fingerprint in their name, so a saved copy never goes stale
async function assetRequest(request) {
  const cache = await caches.open(ASSETS)
  const saved = await cache.match(request)
  if (saved) return saved
  const response = await fetch(request)
  if (response.ok) {
    await cache.put(request, response.clone())
    const keys = await cache.keys()
    if (keys.length > MAX_ASSETS) await Promise.all(keys.slice(0, keys.length - MAX_ASSETS).map((key) => cache.delete(key)))
  }
  return response
}

// Fonts: save them the first time
async function fontRequest(request) {
  const cache = await caches.open(FONTS)
  const saved = await cache.match(request)
  if (saved) return saved
  const response = await fetch(request)
  if (response.ok || response.status === 0) cache.put(request, response.clone())
  return response
}

// Other files of the site (icons and so on): show the saved copy, and refresh it quietly
async function otherRequest(request) {
  const cache = await caches.open(SHELL)
  const saved = await cache.match(request)
  const update = fetch(request)
    .then((response) => {
      if (response.ok) cache.put(request, response.clone())
      return response
    })
    .catch(() => null)
  return saved || (await update) || new Response('', { status: 504 })
}

self.addEventListener('fetch', (event) => {
  const request = event.request
  if (request.method !== 'GET') return
  const url = new URL(request.url)
  if (request.mode === 'navigate' && url.origin === self.location.origin) {
    event.respondWith(pageRequest(request))
  } else if (url.origin === self.location.origin && url.pathname.startsWith('/assets/')) {
    event.respondWith(assetRequest(request))
  } else if (url.origin === self.location.origin) {
    event.respondWith(otherRequest(request))
  } else if (url.hostname === 'fonts.googleapis.com' || url.hostname === 'fonts.gstatic.com') {
    event.respondWith(fontRequest(request))
  }
  // Everything else (all the requests to the EstateLoom server) is left alone: the app handles those itself
})