// Import the React tools we need
import { useEffect, useState } from 'react'
// Import the page-switching tool
import { Link } from 'react-router-dom'
// Import the icons we use
import { ChevronLeft, ChevronRight, Droplets, Wifi, Zap } from 'lucide-react'
// Import our own files
import { getDashboard } from '../api'
import { currentPeriod, monthLabel, shiftPeriod } from '../format'
import MeterSheet from '../components/MeterSheet'
import WifiSheet from '../components/WifiSheet'
import { inputClass } from '../components/Field'

// The three kinds of bill
const TABS = [
  { key: 'water', label: 'Water', icon: Droplets },
  { key: 'electricity', label: 'Electricity', icon: Zap },
  { key: 'wifi', label: 'Wi-Fi', icon: Wifi },
]

// The page for adding water, electricity, and Wi-Fi bills
export default function Bills() {
  // The list of properties (nothing until it arrives)
  const [properties, setProperties] = useState(null)
  // The error message, if loading failed
  const [error, setError] = useState('')
  // The chosen property, kind of bill, and month
  const [propertyId, setPropertyId] = useState('')
  const [tab, setTab] = useState('water')
  const [month, setMonth] = useState(currentPeriod())

  // Load the properties when the page first opens
  useEffect(() => {
    getDashboard()
      .then((data) => {
        setProperties(data.properties)
        // Start on the first property
        if (data.properties.length > 0) setPropertyId(String(data.properties[0].property_id))
      })
      .catch((err) => setError(err.message))
  }, [])

  return (
    <div>
      {/* The title */}
      <h1 className="text-3xl font-extrabold text-forest-900">Bills</h1>
      <p className="text-muted">Water, electricity, and Wi-Fi on top of rent.</p>

      {/* If loading failed, show the message */}
      {error && <p className="mt-6 rounded-2xl bg-terracotta/10 p-4 text-terracotta">{error}</p>}

      {/* While waiting, show a grey placeholder box */}
      {!error && !properties && <div className="mt-6 h-40 animate-pulse rounded-3xl bg-forest-100" />}

      {/* If there are no properties yet, point to the Properties page */}
      {properties && properties.length === 0 && (
        <div className="mt-8 rounded-3xl bg-paper p-10 text-center shadow-sm">
          <p className="font-semibold text-forest-900">No properties yet</p>
          <p className="mt-1 text-sm text-muted">Add a property and move tenants in before adding bills.</p>
          <Link to="/properties" className="mt-4 inline-block rounded-xl bg-forest-900 px-5 py-3 text-sm font-semibold text-white hover:bg-forest-700">
            Go to properties
          </Link>
        </div>
      )}

      {properties && properties.length > 0 && (
        <>
          {/* The property and month controls */}
          <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:items-center">
            {properties.length > 1 && (
              <select
                value={propertyId}
                onChange={(e) => setPropertyId(e.target.value)}
                className={`${inputClass} sm:w-64`}
                aria-label="Choose a property"
              >
                {properties.map((prop) => (
                  <option key={prop.property_id} value={prop.property_id}>
                    {prop.name}
                  </option>
                ))}
              </select>
            )}
            <div className="flex w-fit items-center rounded-xl bg-paper shadow-sm">
              <button
                onClick={() => setMonth(shiftPeriod(month, -1))}
                aria-label="Previous month"
                className="rounded-l-xl p-3 text-forest-700 hover:bg-forest-100"
              >
                <ChevronLeft size={18} />
              </button>
              <span className="min-w-36 px-2 text-center text-sm font-semibold text-forest-900">{monthLabel(month)}</span>
              <button
                onClick={() => setMonth(shiftPeriod(month, 1))}
                aria-label="Next month"
                className="rounded-r-xl p-3 text-forest-700 hover:bg-forest-100"
              >
                <ChevronRight size={18} />
              </button>
            </div>
          </div>

          {/* The three tabs */}
          <div className="mt-4 grid grid-cols-3 gap-2 rounded-2xl bg-forest-100 p-1.5">
            {TABS.map(({ key, label, icon: Icon }) => (
              <button
                key={key}
                onClick={() => setTab(key)}
                className={`flex items-center justify-center gap-2 rounded-xl py-2.5 text-sm font-semibold transition ${
                  tab === key ? 'bg-paper text-forest-900 shadow-sm' : 'text-forest-700 hover:text-forest-900'
                }`}
              >
                <Icon size={16} />
                {label}
              </button>
            ))}
          </div>

          {/* The sheet for the chosen tab (the key makes it start fresh when anything changes) */}
          {tab === 'wifi' ? (
            <WifiSheet key={`wifi-${propertyId}-${month}`} propertyId={propertyId} period={month} />
          ) : (
            <MeterSheet key={`${tab}-${propertyId}-${month}`} propertyId={propertyId} utility={tab} period={month} />
          )}
        </>
      )}
    </div>
  )
}