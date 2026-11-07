// register.js - starts offline mode when the app opens
// To switch everything off: set VITE_OFFLINE=off on the website service in Render, and redeploy.

import { installOfflineFetch } from './patchFetch'
import { startEngine } from './engine'
import './install'

if (import.meta.env.VITE_OFFLINE === 'off') {
  // Offline mode is switched off: remove the helper and everything it saved
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.getRegistrations().then((list) => list.forEach((item) => item.unregister())).catch(() => {})
  }
  if (window.caches) {
    caches.keys().then((names) => names.forEach((name) => name.startsWith('estateloom-') && caches.delete(name))).catch(() => {})
  }
} else {
  installOfflineFetch()
  startEngine()
  // The helper only runs in the real website (not while you are working on it)
  if ('serviceWorker' in navigator && import.meta.env.PROD) {
    window.addEventListener('load', () => navigator.serviceWorker.register('/sw.js').catch(() => {}))
  }
  // Ask the phone not to throw away what we saved when it runs low on space
  if (navigator.storage && navigator.storage.persist) navigator.storage.persist().catch(() => {})
}