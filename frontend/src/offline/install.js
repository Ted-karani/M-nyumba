// install.js - catches the browser's "this app can be installed" message, so a button can use it later

let saved = null
const listeners = new Set()
const tell = () => listeners.forEach((listener) => listener())

window.addEventListener('beforeinstallprompt', (event) => {
  event.preventDefault()
  saved = event
  tell()
})
window.addEventListener('appinstalled', () => {
  saved = null
  tell()
})

export const canInstall = () => saved !== null
export const isInstalled = () => window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true
export function onInstallChange(listener) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}
// Show the browser's install window
export async function install() {
  if (!saved) return false
  saved.prompt()
  const choice = await saved.userChoice
  saved = null
  tell()
  return choice.outcome === 'accepted'
}