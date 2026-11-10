// Import the React tools we need
import { useEffect, useState } from 'react'
// Import the icons we use
import { AlertTriangle, CheckCircle2, CloudDownload, CloudOff, Loader2, RefreshCw } from 'lucide-react'
// Import our own files
import { useAuth } from '../AuthContext'
import { retryAll, syncNow } from '../offline/engine'
import { lastPrepared, prepareOffline } from '../offline/prepare'
import { useOfflineState } from '../offline/useOffline'
import { useT } from '../i18n'
import SyncPanel from './SyncPanel'

// The slim bar at the top: says when there is no signal, and what is waiting to be sent
export default function OfflineBar() {
  const { user } = useAuth()
  const state = useOfflineState()
  const t = useT()
  const [panel, setPanel] = useState(false)
  // The one-time tip for caretakers, to save their checklists on the phone
  const [tip, setTip] = useState(false)
  const [saving, setSaving] = useState(false)

  // Show the tip to a caretaker who has never saved for offline (and has not closed the tip)
  useEffect(() => {
    if (user.role !== 'caretaker' || localStorage.getItem('estateloom_tip_hidden')) return
    lastPrepared().then((done) => setTip(!done))
  }, [user.role])

  // Save for offline from the tip
  async function saveNow() {
    setSaving(true)
    try {
      await prepareOffline()
      setTip(false)
    } catch {
      // The Account page shows the reason; here we just stop
    } finally {
      setSaving(false)
    }
  }

  // A tenant has nothing that waits to be sent: only say when there is no signal
  if (user.role === 'tenant') {
    return state.offline ? (
      <div role="status" className="sticky top-0 z-20 flex items-center gap-3 bg-amber px-4 py-2.5 text-sm font-medium text-white">
        <CloudOff size={18} className="shrink-0" />
        <p className="flex-1">{t('No signal right now. Some things may not load until it returns.')}</p>
      </div>
    ) : null
  }

  const waiting = state.pending + state.failed
  const base = 'sticky top-0 z-20 flex items-center gap-3 px-4 py-2.5 text-sm font-medium text-white'
  const button = 'shrink-0 rounded-lg bg-white/20 px-3 py-1 text-xs font-semibold hover:bg-white/30'
  let bar = null

  if (state.needsSignIn) {
    bar = (
      <div role="status" className={`${base} bg-terracotta`}>
        <AlertTriangle size={18} className="shrink-0" />
        <p className="flex-1">Please log out and sign in again to send your {waiting} waiting change{waiting === 1 ? '' : 's'}. They are safe on this phone.</p>
      </div>
    )
  } else if (state.offline) {
    bar = (
      <div role="status" className={`${base} bg-amber`}>
        <CloudOff size={18} className="shrink-0" />
        <p className="flex-1">No signal. Keep working: your changes are saved on this phone and will be sent when the signal returns.{waiting > 0 ? ` (${waiting} waiting)` : ''}</p>
        {waiting > 0 && (
          <button onClick={() => setPanel(true)} className={button}>
            See
          </button>
        )}
      </div>
    )
  } else if (state.failed > 0) {
    bar = (
      <div role="status" className={`${base} bg-terracotta`}>
        <AlertTriangle size={18} className="shrink-0" />
        <p className="flex-1">
          {state.failed} change{state.failed === 1 ? '' : 's'} could not be sent.
        </p>
        <button onClick={() => retryAll()} className={button}>
          Try again
        </button>
        <button onClick={() => setPanel(true)} className={button}>
          Review
        </button>
      </div>
    )
  } else if (state.pending > 0) {
    bar = (
      <div role="status" className={`${base} bg-forest-700`}>
        {state.syncing ? <Loader2 size={18} className="shrink-0 animate-spin" /> : <RefreshCw size={18} className="shrink-0" />}
        <p className="flex-1">
          {state.syncing ? 'Sending' : 'Waiting to send'} {state.pending} change{state.pending === 1 ? '' : 's'}...
        </p>
        {!state.syncing && (
          <button onClick={() => syncNow()} className={button}>
            Send now
          </button>
        )}
        <button onClick={() => setPanel(true)} className={button}>
          See
        </button>
      </div>
    )
  } else if (state.justSynced) {
    bar = (
      <div role="status" className={`${base} bg-forest-500`}>
        <CheckCircle2 size={18} className="shrink-0" />
        <p className="flex-1">All changes were sent.</p>
        <button onClick={() => window.location.reload()} className={button}>
          Refresh
        </button>
      </div>
    )
  } else if (tip) {
    bar = (
      <div role="status" className={`${base} bg-forest-900`}>
        <CloudDownload size={18} className="shrink-0 text-gold" />
        <p className="flex-1">Going into buildings with a weak signal? Save your units and checklists on this phone first.</p>
        <button onClick={saveNow} disabled={saving} className={button}>
          {saving ? 'Saving...' : 'Save now'}
        </button>
        <button
          onClick={() => {
            localStorage.setItem('estateloom_tip_hidden', '1')
            setTip(false)
          }}
          aria-label="Close"
          className={button}
        >
          Later
        </button>
      </div>
    )
  }

  return (
    <>
      {bar}
      <SyncPanel open={panel} onClose={() => setPanel(false)} />
    </>
  )
}