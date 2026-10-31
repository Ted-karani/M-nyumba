// Import the page-switching tool
import { Link } from 'react-router-dom'
// Import the animation tool
import { motion } from 'framer-motion'
// Import the icon we use
import { ChevronRight } from 'lucide-react'
// Import the list of screens under "More"
import { MORE_ITEMS } from '../nav'

// How the list appears: the cards come in one after another
const listAnimation = { hidden: {}, show: { transition: { staggerChildren: 0.06 } } }
// How each card appears: fade in while sliding up
const itemAnimation = { hidden: { opacity: 0, y: 14 }, show: { opacity: 1, y: 0 } }

// The page that lists everything that does not fit in the phone's bottom bar
export default function More() {
  return (
    <div>
      <h1 className="text-3xl font-extrabold text-forest-900">More</h1>
      <p className="text-muted">Everything else in EstateLoom.</p>
      <motion.div variants={listAnimation} initial="hidden" animate="show" className="mt-6 grid gap-3 md:grid-cols-2">
        {MORE_ITEMS.map(({ to, label, icon: Icon, description }) => (
          <motion.div key={to} variants={itemAnimation}>
            <Link
              to={to}
              className="flex items-center gap-4 rounded-2xl bg-paper p-4 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md"
            >
              <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-forest-100 text-forest-700">
                <Icon size={22} />
              </span>
              <div className="min-w-0 flex-1">
                <p className="font-semibold text-forest-900">{label}</p>
                <p className="text-sm text-muted">{description}</p>
              </div>
              <ChevronRight size={18} className="shrink-0 text-muted" />
            </Link>
          </motion.div>
        ))}
      </motion.div>
    </div>
  )
}