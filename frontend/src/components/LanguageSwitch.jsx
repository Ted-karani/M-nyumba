// Import our own files
import { getLang, setLang, useT } from '../i18n'

// The little switch between English and Kiswahili
export default function LanguageSwitch({ className = '', compact = false }) {
  // This makes the switch redraw when the language changes
  useT()
  const current = getLang()
  const options = compact
    ? [
        ['en', 'EN'],
        ['sw', 'SW'],
      ]
    : [
        ['en', 'English'],
        ['sw', 'Kiswahili'],
      ]
  return (
    <div role="group" aria-label="Language / Lugha" className={`inline-flex rounded-xl bg-forest-100 p-1 text-xs font-bold ${className}`}>
      {options.map(([code, label]) => (
        <button
          key={code}
          type="button"
          onClick={() => setLang(code)}
          aria-pressed={current === code}
          className={`rounded-lg px-3 py-1.5 transition ${current === code ? 'bg-paper text-forest-900 shadow-sm' : 'text-forest-700'}`}
        >
          {label}
        </button>
      ))}
    </div>
  )
}