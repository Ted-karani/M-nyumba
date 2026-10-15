// Import the React tools we need
import { useEffect, useState } from 'react'
// Import the page-switching tool
import { Link } from 'react-router-dom'
// Import our own files
import { getDashboard } from '../api'
import SetupImport from '../components/SetupImport'
import SetupOne from '../components/SetupOne'

// The two ways to add tenants who already live in your properties
const TABS = [
  { key: 'one', label: 'Add one tenant' },
  { key: 'list', label: 'Import a list' },
]

// The page for setting up tenants who already live in your properties
export default function Setup() {
  // The list of properties (nothing until it arrives)
  const [properties, setProperties] = useState(null)
  // The error message, if loading failed
  const [error, setError] = useState('')
  // Which way is chosen
  const [tab, setTab] = useState('one')

  // Load the properties when the page opens
  useEffect(() => {
    getDashboard()
      .then((data) => setProperties(data.properties))
      .catch((err) => setError(err.message))
  }, [])

  return (
    <div className="mx-auto max-w-2xl">
      {/* The title */}
      <h1 className="text-3xl font-extrabold text-forest-900">Set up tenants</h1>
      <p className="text-muted">For people who already live in your properties. No deposit or past rent is charged.</p>

      {error && <p className="mt-6 rounded-2xl bg-terracotta/10 p-4 text-terracotta">{error}</p>}
      {!error && !properties && <div className="mt-6 h-40 animate-pulse rounded-3xl bg-forest-100" />}

      {/* If there are no properties yet, point to the Properties page */}
      {properties && properties.length === 0 && (
        <div className="mt-8 rounded-3xl bg-paper p-10 text-center shadow-sm">
          <p className="font-semibold text-forest-900">Add a property first</p>
          <p className="mt-1 text-sm text-muted">Tenants are added into properties, so create yours before setting them up.</p>
          <Link to="/properties" className="mt-4 inline-block rounded-xl bg-forest-900 px-5 py-3 text-sm font-semibold text-white hover:bg-forest-700">
            Go to properties
          </Link>
        </div>
      )}

      {properties && properties.length > 0 && (
        <>
          {/* The two tabs */}
          <div className="mt-6 grid grid-cols-2 gap-2 rounded-2xl bg-forest-100 p-1.5">
            {TABS.map((item) => (
              <button
                key={item.key}
                onClick={() => setTab(item.key)}
                className={`rounded-xl py-2.5 text-sm font-semibold transition ${
                  tab === item.key ? 'bg-paper text-forest-900 shadow-sm' : 'text-forest-700 hover:text-forest-900'
                }`}
              >
                {item.label}
              </button>
            ))}
          </div>
          {tab === 'one' ? <SetupOne properties={properties} /> : <SetupImport properties={properties} />}
        </>
      )}
    </div>
  )
}