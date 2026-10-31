// Import the brand settings
import { BRAND } from '../brand'

// The small picture: a roof over woven threads (the "loom" in the name)
export function LogoMark({ className = 'h-10 w-10', onDark = false }) {
  // The colours change a little, so the picture stands out on a dark background and on a light one
  const frame = onDark ? 'fill-gold' : 'fill-forest-900'
  const roof = onDark ? 'stroke-forest-900' : 'stroke-gold'
  const warp = onDark ? 'stroke-forest-900' : 'stroke-cream'
  const weft = onDark ? 'stroke-cream' : 'stroke-gold'
  return (
    <svg viewBox="0 0 48 48" className={className} role="img" aria-label={BRAND.name} xmlns="http://www.w3.org/2000/svg">
      {/* The rounded square behind it */}
      <rect width="48" height="48" rx="12" className={frame} />
      {/* The roof */}
      <path d="M9 23 L24 9.5 L39 23" className={roof} fill="none" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round" />
      {/* The threads running up and down */}
      <g className={warp} fill="none" strokeWidth="3" strokeLinecap="round">
        <line x1="16" y1="25" x2="16" y2="40" />
        <line x1="24" y1="25" x2="24" y2="40" />
        <line x1="32" y1="25" x2="32" y2="40" />
      </g>
      {/* The threads running across */}
      <g className={weft} fill="none" strokeWidth="3" strokeLinecap="round">
        <line x1="11" y1="30" x2="37" y2="30" />
        <line x1="11" y1="36" x2="37" y2="36" />
      </g>
      {/* Short pieces of the up-and-down threads drawn on top, so the across threads weave over and under */}
      <g className={warp} fill="none" strokeWidth="3" strokeLinecap="round">
        <line x1="24" y1="27.5" x2="24" y2="32.5" />
        <line x1="16" y1="33.5" x2="16" y2="38.5" />
        <line x1="32" y1="33.5" x2="32" y2="38.5" />
      </g>
    </svg>
  )
}

// The logo picture together with the name
export default function Wordmark({ onDark = false, size = 'md', className = '' }) {
  // The three sizes
  const sizes = {
    sm: { box: 'h-8 w-8', text: 'text-lg' },
    md: { box: 'h-10 w-10', text: 'text-xl' },
    lg: { box: 'h-11 w-11', text: 'text-2xl' },
  }
  const chosen = sizes[size] || sizes.md
  return (
    <span className={`flex items-center gap-3 ${className}`}>
      <LogoMark className={`${chosen.box} shrink-0`} onDark={onDark} />
      <span className={`font-display ${chosen.text} font-bold tracking-tight ${onDark ? 'text-white' : 'text-forest-900'}`}>
        {BRAND.nameParts[0]}
        <span className={onDark ? 'text-gold' : 'text-forest-500'}>{BRAND.nameParts[1]}</span>
      </span>
    </span>
  )
}