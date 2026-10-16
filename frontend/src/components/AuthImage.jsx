// Import the React tools we need
import { useEffect, useState } from 'react'
// Import our file fetcher
import { fetchBlob } from '../api'

// Shows a picture from the backend (a plain picture tag cannot send the login token, so we fetch it ourselves)
export default function AuthImage({ path, alt, className }) {
  // The address of the picture in the browser's memory (nothing until it arrives)
  const [src, setSrc] = useState('')

  // Fetch the picture when this appears
  useEffect(() => {
    let url = ''
    // Set to true if this goes away before the picture arrives
    let cancelled = false
    fetchBlob(path)
      .then((blob) => {
        if (cancelled) return
        url = URL.createObjectURL(blob)
        setSrc(url)
      })
      // If it fails we simply keep showing the grey box
      .catch(() => {})
    // Clean up: let go of the picture in memory
    return () => {
      cancelled = true
      if (url) URL.revokeObjectURL(url)
    }
  }, [path])

  // While waiting, show a grey pulsing box
  if (!src) return <div className={`animate-pulse bg-forest-100 ${className}`} />
  return <img src={src} alt={alt} className={className} />
}