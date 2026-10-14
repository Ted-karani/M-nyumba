// Import the icon
import { Hammer } from 'lucide-react'

// A simple page for screens we have not built yet
export default function ComingSoon({ title }) {
  return (
    <div className="flex flex-col items-center py-24 text-center">
      <div className="flex h-16 w-16 items-center justify-center rounded-3xl bg-forest-100 text-forest-700">
        <Hammer size={28} />
      </div>
      <h1 className="mt-6 text-3xl font-extrabold text-forest-900">{title}</h1>
      <p className="mt-2 max-w-xs text-muted">This screen is coming in a later step.</p>
    </div>
  )
}