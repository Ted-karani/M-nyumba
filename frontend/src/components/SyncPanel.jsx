// Import the React tools we need
import { useCallback, useEffect, useState } from 'react'
// Import the icons we use
import { AlertCircle, Clock, RefreshCw, Trash2 } from 'lucide-react'
// Import our own files
import { discardEntry, getEntries, retryEntry } from '../offline/engine'
import { useOfflineState } from '../offline/useOffline'
import Modal from './Modal'

// The window that lists what is waiting to be sent, with a way to retry or discard each one
export default function SyncPanel({ open, onClose }) {
  const state = useOfflineState()
  const [entries, setEntries] = useState([])

  // Read the list
  const load = useCallback(() => {
    getEntries().then(setEntries)
  }, [])

  // Read it when the window opens, and whenever the counts change
  useEffect(() => {
    if (open) load()
  }, [open, load, state.pending, state.failed])

  return (
    <Modal open={open} title="Waiting to be sent" onClose={onClose}>
      {entries.length === 0 ? (
        <p className="text-sm text-muted">Nothing is waiting. Everything has been sent.</p>
      ) : (
        <ul className="divide-y divide-forest-100">
          {entries.map((entry) => (
            <li key={entry.id} className="flex items-start gap-3 py-3">
              {entry.status === 'failed' ? <AlertCircle size={18} className="mt-0.5 shrink-0 text-terracotta" /> : <Clock size={18} className="mt-0.5 shrink-0 text-amber" />}
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold text-forest-900">{entry.label}</p>
                <p className="text-xs text-muted">
                  {new Date(entry.createdAt).toLocaleString('en-GB', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}
                  {entry.status === 'pending' ? ' · waiting for signal' : ''}
                </p>
                {entry.status === 'failed' && <p className="mt-1 text-xs text-terracotta">{entry.error}</p>}
              </div>
              <div className="flex shrink-0 gap-1">
                {entry.status === 'failed' && (
                  <button onClick={() => retryEntry(entry.id)} aria-label="Try again" className="rounded-lg p-2 text-forest-700 hover:bg-forest-100">
                    <RefreshCw size={16} />
                  </button>
                )}
                <button
                  onClick={() => window.confirm('Throw this away? It has not been sent and cannot be brought back.') && discardEntry(entry.id).then(load)}
                  aria-label="Discard"
                  className="rounded-lg p-2 text-muted hover:bg-terracotta/10 hover:text-terracotta"
                >
                  <Trash2 size={16} />
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Modal>
  )
}