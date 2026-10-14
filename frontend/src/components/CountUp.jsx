// Import the React tools we need
import { useEffect, useState } from 'react'
// Import the animation function
import { animate } from 'framer-motion'

// Shows a number that counts up from zero when it appears
export default function CountUp({ value, format = (n) => n.toLocaleString('en-US') }) {
  // The number being shown right now
  const [shown, setShown] = useState(0)

  // Whenever the target number changes, run the counting animation
  useEffect(() => {
    // Count from 0 to the target over just over a second
    const controls = animate(0, value, {
      duration: 1.1,
      ease: 'easeOut',
      onUpdate: (latest) => setShown(Math.round(latest)),
    })
    // Stop the animation if the screen closes early
    return () => controls.stop()
  }, [value])

  // Show the current number, formatted
  return <>{format(shown)}</>
}