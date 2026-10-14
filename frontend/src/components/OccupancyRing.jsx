// Import the animation tool
import { motion } from 'framer-motion'
// Import our counting number
import CountUp from './CountUp'

// A circle that fills up to show a percentage
export default function OccupancyRing({ percent }) {
  // The size of the circle and the line thickness
  const radius = 52
  // The distance around the circle (this is what we animate)
  const circumference = 2 * Math.PI * radius
  // How much of the line to hide so only the right amount shows
  const hidden = circumference * (1 - percent / 100)

  return (
    <div className="relative h-40 w-40">
      <svg viewBox="0 0 120 120" className="h-full w-full -rotate-90">
        {/* The faint full circle behind */}
        <circle cx="60" cy="60" r={radius} fill="none" strokeWidth="12" stroke="currentColor" className="text-forest-100" />
        {/* The green circle that fills up */}
        <motion.circle
          cx="60"
          cy="60"
          r={radius}
          fill="none"
          strokeWidth="12"
          strokeLinecap="round"
          stroke="currentColor"
          className="text-forest-500"
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: hidden }}
          transition={{ duration: 1.1, ease: 'easeOut', delay: 0.2 }}
        />
      </svg>
      {/* The percentage in the middle */}
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="font-display text-3xl font-extrabold text-forest-900">
          <CountUp value={Math.round(percent)} format={(n) => `${n}%`} />
        </span>
        <span className="text-xs text-muted">occupied</span>
      </div>
    </div>
  )
}