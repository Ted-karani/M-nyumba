// Import the React tools we need
import { useEffect, useState } from 'react'
// Import the icons we use
import { CheckCircle2, CloudDownload, Download, Loader2, Smartphone } from 'lucide-react'
// Import our own files
import { canInstall, install, isInstalled, onInstallChange } from '../offline/install'
import { lastPrepared, prepareOffline } from '../offline/prepare'

// The card on the Account page: install the app on this phone, and save work for offline
export default function OfflineCard() {
  // Whether the browser lets us show an install button (it changes when the browser decides)
  const [installable, setInstallable] = useState(canInstall())
  const [installed, setInstalled] = useState(isInstalled())
  // The last time work was saved for offline, and how the saving is going
  const [saved, setSaved] = useState(null)
  const [busy, setBusy] = useState(false)
  const [progress, setProgress] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    lastPrepared().then(setSaved)
    return onInstallChange(() => {
      setInstallable(canInstall())
      setInstalled(isInstalled())
    })
  }, [])

  // Save the units and checklists on this phone
  async function handleSave() {
    setError('')
    setBusy(true)
    setProgress('')
    try {
      const result = await prepareOffline((done, total) => setProgress(`${done} of ${total}`))
      setSaved(result)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mt-5 rounded-3xl bg-paper p-6 shadow-sm">
      <h2 className="flex items-center gap-2 font-display text-lg font-bold text-forest-900">
        <Smartphone size={20} className="text-gold" /> Use it without signal
      </h2>
      <p className="mt-3 text-sm text-muted">
        Install EstateLoom on this phone so it opens like any other app. When you have no signal, you can still look at your units, rate checklist areas, take photos and report repairs. Everything is sent when the signal returns.
      </p>

      {installed ? (
        <p className="mt-4 flex items-center gap-2 text-sm font-semibold text-forest-700">
          <CheckCircle2 size={18} /> Installed on this phone.
        </p>
      ) : installable ? (
        <button onClick={install} className="mt-4 flex items-center gap-2 rounded-xl bg-forest-900 px-5 py-3 text-sm font-semibold text-white hover:bg-forest-700">
          <Download size={16} /> Install EstateLoom
        </button>
      ) : (
        <p className="mt-4 rounded-xl bg-cream px-4 py-3 text-xs text-muted">
          To install: in Chrome, tap the three dots at the top right, then “Install app” or “Add to Home screen”.
        </p>
      )}

      <div className="mt-5 border-t border-forest-100 pt-5">
        <p className="text-sm font-semibold text-forest-900">Save my work for offline</p>
        <p className="mt-1 text-xs text-muted">Do this when you have a good signal, before you go into the buildings. It saves your units and every checklist on this phone.</p>
        {saved && (
          <p className="mt-2 text-xs text-forest-700">
            Last saved {new Date(saved.at).toLocaleString('en-GB', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })} ({saved.checklists} checklist{saved.checklists === 1 ? '' : 's'}).
          </p>
        )}
        {error && (
          <div role="alert" className="mt-3 rounded-xl bg-terracotta/10 px-4 py-3 text-sm font-medium text-terracotta">
            {error}
          </div>
        )}
        <button onClick={handleSave} disabled={busy} className="mt-3 flex items-center gap-2 rounded-xl bg-forest-100 px-5 py-3 text-sm font-semibold text-forest-700 hover:bg-forest-200 disabled:opacity-70">
          {busy ? <Loader2 size={16} className="animate-spin" /> : <CloudDownload size={16} />} {busy ? `Saving ${progress}` : 'Save now'}
        </button>
      </div>
    </div>
  )
}