// The look shared by every text box
export const inputClass =
  'w-full rounded-xl border border-forest-200 bg-paper px-4 py-3 outline-none transition focus:border-forest-500 focus:ring-4 focus:ring-forest-100'

// A label with a text box under it, and an optional small hint below
export function Field({ label, hint, children }) {
  return (
    <label className="block">
      <span className="mb-1 block text-sm font-medium">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-xs text-muted">{hint}</span>}
    </label>
  )
}