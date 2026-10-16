// Import the React tools we need
import { useEffect, useState } from 'react'
// Import the page-switching tool
import { Link } from 'react-router-dom'
// Import the animation tool
import { motion } from 'framer-motion'
// Import the icons we use
import { CalendarCheck, ChevronRight, FileText } from 'lucide-react'
// Import our own files
import { getUpcoming } from '../api'
import { formatDate } from '../format'

// Write how far away a date is, in a way that fits a task or a document
function whenText(item) {
  const days = item.days_left
  if (item.kind === 'document') {
    if (days < 0) return `Expired ${-days} day${days === -1 ? '' : 's'} ago`
    if (days === 0) return 'Expires today'
    return `Expires in ${days} day${days === 1 ? '' : 's'}`
  }
  if (days < 0) return `${-days} day${days === -1 ? '' : 's'} overdue`
  if (days === 0) return 'Due today'
  return `Due in ${days} day${days === 1 ? '' : 's'}`
}

// The card on the dashboard that lists tasks due soon and documents about to expire
export default function UpcomingCard() {
  // What is coming up (nothing until it arrives)
  const [items, setItems] = useState(null)

  // Ask the backend when the card first appears
  useEffect(() => {
    getUpcoming()
      .then(setItems)
      // If this fails, we simply show nothing
      .catch(() => setItems([]))
  }, [])

  // If nothing is coming up, show nothing at all
  if (!items || items.length === 0) return null

  return (
    <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} className="mb-6 rounded-3xl bg-paper p-5 shadow-sm">
      <div className="flex items-center justify-between">
        <h2 className="flex items-center gap-2 font-display text-lg font-bold text-forest-900">
          <CalendarCheck size={20} className="text-gold" /> Coming up
        </h2>
        <Link to="/tasks" className="flex items-center gap-1 text-sm font-medium text-forest-700 hover:underline">
          All tasks <ChevronRight size={16} />
        </Link>
      </div>
      <ul className="mt-3 divide-y divide-forest-100">
        {items.slice(0, 5).map((item) => (
          <li key={`${item.kind}-${item.id}`}>
            <Link to={item.link} className="flex items-center gap-3 py-3 hover:opacity-80">
              <span className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ${item.days_left < 0 ? 'bg-terracotta/15 text-terracotta' : 'bg-gold/20 text-forest-900'}`}>
                {item.kind === 'document' ? <FileText size={18} /> : <CalendarCheck size={18} />}
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate font-semibold text-forest-900">{item.title}</p>
                <p className="truncate text-xs text-muted">
                  {formatDate(item.due_date)}
                  {item.detail ? ` · ${item.detail}` : ''}
                </p>
              </div>
              <p className={`shrink-0 text-xs font-semibold ${item.days_left < 0 ? 'text-terracotta' : 'text-forest-700'}`}>{whenText(item)}</p>
            </Link>
          </li>
        ))}
      </ul>
      {items.length > 5 && <p className="mt-2 text-xs text-muted">and {items.length - 5} more</p>}
    </motion.div>
  )
}