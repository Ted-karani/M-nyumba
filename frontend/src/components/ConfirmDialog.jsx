// Import the React tool for remembering values
import { useState } from 'react'
// Import the spinner icon
import { Loader2 } from 'lucide-react'
// Import our pop-up window
import Modal from './Modal'

// A pop-up that asks "are you sure?" before a risky action
export default function ConfirmDialog({ open, title, message, confirmLabel, onConfirm, onClose }) {
  // True while we wait for the backend
  const [busy, setBusy] = useState(false)
  // The error message to show (empty means none)
  const [error, setError] = useState('')

  // Run when the person confirms
  async function handleConfirm() {
    // Clear any old error and show the loading state
    setError('')
    setBusy(true)
    try {
      // Do the action (the screen that opened this pop-up supplies it)
      await onConfirm()
    } catch (err) {
      // Show why it was refused, like "This unit has lease history and cannot be deleted"
      setError(err.message)
    } finally {
      // Stop the loading state
      setBusy(false)
    }
  }

  // Close the pop-up and forget any error
  function handleClose() {
    setError('')
    onClose()
  }

  return (
    <Modal open={open} title={title} onClose={handleClose}>
      <p className="text-muted">{message}</p>
      {/* The error appears here if the backend refuses */}
      {error && (
        <div role="alert" className="mt-4 rounded-xl bg-terracotta/10 px-4 py-3 text-sm font-medium text-terracotta">
          {error}
        </div>
      )}
      <div className="mt-6 flex gap-3">
        <button
          type="button"
          onClick={handleClose}
          className="flex-1 rounded-xl bg-forest-100 py-3 font-semibold text-forest-700 hover:bg-forest-200"
        >
          Cancel
        </button>
        <button
          type="button"
          onClick={handleConfirm}
          disabled={busy}
          className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-terracotta py-3 font-semibold text-white hover:opacity-90 disabled:opacity-70"
        >
          {busy && <Loader2 size={18} className="animate-spin" />}
          {confirmLabel}
        </button>
      </div>
    </Modal>
  )
}