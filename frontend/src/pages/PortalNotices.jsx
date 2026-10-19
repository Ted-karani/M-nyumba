// Import the React tools we need
import { useEffect, useState } from 'react'
// Import the animation tool
import { motion } from 'framer-motion'
// Import the icons we use
import { Bell, Pin } from 'lucide-react'
// Import our own files
import { getPortalNotices } from '../api'
import { formatDate } from '../format'

// The page where a tenant reads the notices from their landlord
export default function PortalNotices() {
  // The notices (nothing until they arrive)
  const [notices, setNotices] = useState(null)
  // The error message, if loading failed
  const [error, setError] = useState('')

  // Load them when the page opens
  useEffect(() => {
    getPortalNotices()
      .then(setNotices)
      .catch((err) => setError(err.message))
  }, [])

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="text-3xl font-extrabold text-forest-900">Notices</h1>
      <p className="text-muted">News and announcements from your landlord.</p>

      {error && <p className="mt-6 rounded-2xl bg-terracotta/10 p-4 text-terracotta">{error}</p>}
      {!notices && !error && <div className="mt-6 h-28 animate-pulse rounded-2xl bg-forest-100" />}

      {notices && notices.length === 0 && (
        <div className="mt-6 flex flex-col items-center rounded-3xl bg-paper p-10 text-center shadow-sm">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-forest-100 text-forest-700">
            <Bell size={26} />
          </div>
          <p className="mt-4 font-semibold text-forest-900">No notices right now</p>
          <p className="mt-1 text-sm text-muted">When your landlord posts something, you will see it here.</p>
        </div>
      )}

      <div className="mt-6 space-y-3">
        {notices &&
          notices.map((notice) => (
            <motion.div key={notice.id} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="rounded-3xl bg-paper p-5 shadow-sm">
              <div className="flex items-start justify-between gap-3">
                <p className="font-display text-lg font-bold text-forest-900">{notice.title}</p>
                {notice.pinned && <Pin size={16} className="mt-1 shrink-0 text-gold" />}
              </div>
              <p className="mt-2 whitespace-pre-line text-sm leading-relaxed text-ink/80">{notice.body}</p>
              <p className="mt-3 text-xs text-muted">
                {formatDate(notice.posted_on)}
                {notice.property_name ? ` · ${notice.property_name}` : ''}
                {notice.expires_on ? ` · until ${formatDate(notice.expires_on)}` : ''}
              </p>
            </motion.div>
          ))}
      </div>
    </div>
  )
}