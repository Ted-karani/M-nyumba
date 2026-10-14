// Import our money formatter
import { money } from '../format'

// A small colored label showing what a tenant owes
export default function BalanceBadge({ amount, size = 'sm' }) {
  // Bigger labels get more padding
  const sizing = size === 'lg' ? 'px-4 py-1.5 text-sm' : 'px-2.5 py-0.5 text-xs'
  // Owes money: red
  if (amount > 0) {
    return <span className={`whitespace-nowrap rounded-full bg-terracotta/15 font-semibold text-terracotta ${sizing}`}>Owes {money(amount)}</span>
  }
  // Paid more than they owe: gold
  if (amount < 0) {
    return <span className={`whitespace-nowrap rounded-full bg-gold/25 font-semibold text-forest-900 ${sizing}`}>Credit {money(-amount)}</span>
  }
  // Nothing owed: green
  return <span className={`whitespace-nowrap rounded-full bg-forest-100 font-semibold text-forest-700 ${sizing}`}>Paid up</span>
}