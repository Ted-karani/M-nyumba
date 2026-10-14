// Import the React tool that runs code when something changes
import { useEffect } from 'react'
// Import the animation tools
import { AnimatePresence, motion } from 'framer-motion'
// Import the close icon
import { X } from 'lucide-react'

// A pop-up window: slides up from the bottom on phones, sits in the middle on desktop
export default function Modal({ open, title, onClose, children }) {
  // Close the pop-up when the Escape key is pressed
  useEffect(() => {
    // Do nothing while it is closed
    if (!open) return
    // The function that checks for the Escape key
    const onKey = (event) => {
      if (event.key === 'Escape') onClose()
    }
    // Start listening, and stop listening when the pop-up closes
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  return (
    <AnimatePresence>
      {open && (
        // The dark background: clicking it closes the pop-up
        <motion.div
          className="fixed inset-0 z-50 flex items-end justify-center bg-forest-900/50 backdrop-blur-sm sm:items-center sm:p-6"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onMouseDown={onClose}
        >
          {/* The white window itself: clicking inside it does not close it */}
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-label={title}
            onMouseDown={(event) => event.stopPropagation()}
            initial={{ y: 40, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 40, opacity: 0 }}
            transition={{ type: 'spring', stiffness: 380, damping: 34 }}
            className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-t-3xl bg-paper p-6 shadow-2xl sm:rounded-3xl"
          >
            {/* The title and the close button */}
            <div className="mb-5 flex items-center justify-between">
              <h2 className="text-2xl font-bold text-forest-900">{title}</h2>
              <button
                type="button"
                onClick={onClose}
                aria-label="Close"
                className="rounded-xl p-2 text-muted hover:bg-forest-100 hover:text-forest-900"
              >
                <X size={20} />
              </button>
            </div>
            {children}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}