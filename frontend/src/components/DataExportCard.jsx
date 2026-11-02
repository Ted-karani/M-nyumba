// Import the React tool for remembering values
import { useState } from 'react'
// Import the icons we use
import { CheckCircle2, Download, Loader2 } from 'lucide-react'
// Import our own files
import { downloadFile } from '../api'

// The card on a landlord's account page for downloading a copy of all their data
export default function DataExportCard() {
  // Whether we are preparing the download, the error message, and whether it worked
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [done, setDone] = useState(false)

  // Prepare and download the copy
  async function handleDownload() {
    setError('')
    setDone(false)
    setBusy(true)
    try {
      await downloadFile('/account/export', `estateloom-data-${new Date().toISOString().slice(0, 10)}.zip`)
      setDone(true)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mt-5 rounded-3xl bg-paper p-6 shadow-sm">
      <h2 className="flex items-center gap-2 font-display text-lg font-bold text-forest-900">
        <Download size={20} className="text-gold" /> Download my data
      </h2>
      <p className="mt-3 text-sm text-muted">
        Get a copy of everything you have in EstateLoom: an Excel file with all your records (tenants, units, leases, payments, repairs and more), plus the documents and photos you uploaded.
      </p>
      <p className="mt-2 text-xs text-muted">The copy contains your tenants’ personal information, so please keep it safe. Big copies are best downloaded on a computer.</p>
      {error && (
        <div role="alert" className="mt-4 rounded-xl bg-terracotta/10 px-4 py-3 text-sm font-medium text-terracotta">
          {error}
        </div>
      )}
      {done && (
        <div role="status" className="mt-4 flex items-center gap-2 rounded-xl bg-forest-100 px-4 py-3 text-sm font-medium text-forest-700">
          <CheckCircle2 size={18} /> Your copy was downloaded.
        </div>
      )}
      <button onClick={handleDownload} disabled={busy} className="mt-4 flex items-center justify-center gap-2 rounded-xl bg-forest-900 px-5 py-3 text-sm font-semibold text-white hover:bg-forest-700 disabled:opacity-70">
        {busy ? <Loader2 size={16} className="animate-spin" /> : <Download size={16} />} {busy ? 'Preparing your copy...' : 'Download my data'}
      </button>
    </div>
  )
}