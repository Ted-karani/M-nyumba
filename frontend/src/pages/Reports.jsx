// Import the React tools we need
import { useEffect, useState } from 'react'
// Import the animation tool
import { motion } from 'framer-motion'
// Import the icons we use
import { ChevronLeft, ChevronRight, Download, Loader2, Printer, RefreshCw } from 'lucide-react'
// Import the chart tools
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
// Import our own files
import { useAuth } from '../AuthContext'
import { downloadFile, getDashboard, getMonthlyReport } from '../api'
import { categoryLabel } from '../categories'
import { METHOD_LABELS, currentPeriod, formatDate, money, monthLabel, shiftPeriod } from '../format'
import CountUp from '../components/CountUp'
import { inputClass } from '../components/Field'
import OccupancyRing from '../components/OccupancyRing'

// A white card with a title, used for each part of the report
function Section({ title, children }) {
  return (
    <section className="break-inside-avoid rounded-3xl bg-paper p-5 shadow-sm">
      <h2 className="font-display text-lg font-bold text-forest-900">{title}</h2>
      <div className="mt-3">{children}</div>
    </section>
  )
}

// One line with a label on the left and an amount on the right
function Line({ label, value, bold = false, muted = false }) {
  return (
    <div className={`flex justify-between gap-3 py-1.5 text-sm ${bold ? 'font-bold text-forest-900' : muted ? 'text-muted' : 'text-ink'}`}>
      <span>{label}</span>
      <span>{money(value)}</span>
    </div>
  )
}

// The page that shows the monthly statement
export default function Reports() {
  // Who is logged in (their name is printed on the report)
  const { user } = useAuth()
  // The choices: which month and which property
  const [month, setMonth] = useState(currentPeriod())
  const [propertyId, setPropertyId] = useState('')
  // The properties for the dropdown, and the report itself
  const [properties, setProperties] = useState([])
  const [report, setReport] = useState(null)
  // True while we are fetching (we keep showing the old report, slightly faded)
  const [loading, setLoading] = useState(true)
  // The error message, if loading failed
  const [error, setError] = useState('')
  // True while the Excel file is being made, and its error message
  const [downloading, setDownloading] = useState(false)
  const [downloadError, setDownloadError] = useState('')
  // Changing this number makes the report load again (used by the "try again" button)
  const [reloadKey, setReloadKey] = useState(0)

  // Load the properties once, for the dropdown
  useEffect(() => {
    getDashboard()
      .then((data) => setProperties(data.properties))
      .catch(() => setProperties([]))
  }, [])

  // Load the report whenever the month or property changes
  useEffect(() => {
    // Set to true if the choices change again before this request finishes
    let cancelled = false
    setLoading(true)
    getMonthlyReport(month, propertyId)
      .then((data) => {
        if (cancelled) return
        setReport(data)
        setError('')
      })
      .catch((err) => {
        if (!cancelled) setError(err.message)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    // Clean up if the choices change or the page closes
    return () => {
      cancelled = true
    }
  }, [month, propertyId, reloadKey])

  // Download the report as an Excel file
  async function handleExcel() {
    setDownloadError('')
    setDownloading(true)
    try {
      const path = `/reports/monthly/excel?month=${month}${propertyId ? `&property_id=${propertyId}` : ''}`
      await downloadFile(path, `mnyumba-report-${month}.xlsx`)
    } catch (err) {
      setDownloadError(err.message)
    } finally {
      setDownloading(false)
    }
  }

  // The data for the chart (short month names)
  const chartData = report
    ? report.trend.map((point) => ({
        name: monthLabel(point.month).slice(0, 3),
        Collected: point.collected,
        Spent: point.spent,
      }))
    : []
  // The name of the property on the report
  const scopeName = report && report.property_name ? report.property_name : 'All properties'
  // The biggest money-in method, so the bars can be drawn in proportion
  const methodTotal = report ? report.collected || 1 : 1

  return (
    <div>
      {/* The words that appear at the top of the printed page */}
      <div className="print-only mb-4 border-b border-forest-200 pb-3">
        <p className="font-display text-2xl font-bold text-forest-900">M-nyumba monthly statement</p>
        <p className="text-sm text-muted">
          {monthLabel(month)} · {scopeName} · prepared for {user.full_name}
          {report ? ` · made on ${formatDate(report.generated_on)}` : ''}
        </p>
      </div>

      {/* The title, and the buttons for Excel and PDF */}
      <div className="no-print flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-extrabold text-forest-900">Reports</h1>
          <p className="text-muted">What came in, what went out, and what is left.</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={handleExcel}
            disabled={downloading || !report}
            className="flex items-center gap-2 rounded-xl bg-forest-100 px-4 py-2.5 text-sm font-semibold text-forest-700 hover:bg-forest-200 disabled:opacity-60"
          >
            {downloading ? <Loader2 size={16} className="animate-spin" /> : <Download size={16} />} Excel
          </button>
          <button
            onClick={() => window.print()}
            disabled={!report}
            className="flex items-center gap-2 rounded-xl bg-forest-900 px-4 py-2.5 text-sm font-semibold text-white hover:bg-forest-700 disabled:opacity-60"
          >
            <Printer size={16} /> PDF
          </button>
        </div>
      </div>
      {downloadError && (
        <p role="alert" className="no-print mt-3 rounded-xl bg-terracotta/10 px-4 py-3 text-sm font-medium text-terracotta">
          {downloadError}
        </p>
      )}

      {/* The month and property controls */}
      <div className="no-print mt-6 flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="flex w-fit items-center rounded-xl bg-paper shadow-sm">
          <button onClick={() => setMonth(shiftPeriod(month, -1))} aria-label="Previous month" className="rounded-l-xl p-3 text-forest-700 hover:bg-forest-100">
            <ChevronLeft size={18} />
          </button>
          <span className="min-w-36 px-2 text-center text-sm font-semibold text-forest-900">{monthLabel(month)}</span>
          <button onClick={() => setMonth(shiftPeriod(month, 1))} aria-label="Next month" className="rounded-r-xl p-3 text-forest-700 hover:bg-forest-100">
            <ChevronRight size={18} />
          </button>
        </div>
        {properties.length > 1 && (
          <select value={propertyId} onChange={(e) => setPropertyId(e.target.value)} className={`${inputClass} sm:w-64`} aria-label="Choose a property">
            <option value="">All properties</option>
            {properties.map((prop) => (
              <option key={prop.property_id} value={prop.property_id}>
                {prop.name}
              </option>
            ))}
          </select>
        )}
      </div>

      {/* If loading failed, show the message and a retry button */}
      {error && (
        <div className="mt-6 rounded-3xl bg-terracotta/10 p-6 text-terracotta">
          <p className="font-semibold">Could not load the report</p>
          <p className="mt-1 text-sm">{error}</p>
          <button onClick={() => setReloadKey(reloadKey + 1)} className="mt-4 flex items-center gap-2 rounded-xl bg-terracotta px-4 py-2 text-sm font-semibold text-white">
            <RefreshCw size={16} /> Try again
          </button>
        </div>
      )}

      {/* While the very first load is running, show grey placeholder boxes */}
      {!error && !report && (
        <div className="mt-6 space-y-3">
          <div className="h-40 animate-pulse rounded-3xl bg-forest-100" />
          <div className="h-40 animate-pulse rounded-3xl bg-forest-100" />
        </div>
      )}

      {report && !error && (
        <div className={`mt-6 space-y-4 transition-opacity ${loading ? 'opacity-50' : 'opacity-100'}`}>
          {/* The green card: collected, spent, and what is left */}
          <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} className="break-inside-avoid rounded-3xl bg-forest-900 p-6 text-white shadow-xl">
            <p className="text-sm text-forest-200">
              {report.net >= 0 ? 'Left over in' : 'Overspent in'} {monthLabel(month)}
            </p>
            <p className="font-display text-5xl font-bold">
              <CountUp value={Math.abs(report.net)} format={money} />
            </p>
            <div className="mt-5 grid grid-cols-2 gap-3">
              <div className="rounded-2xl bg-white/10 p-4">
                <p className="text-xs text-forest-200">Collected</p>
                <p className="mt-1 font-display text-xl font-bold">{money(report.collected)}</p>
              </div>
              <div className="rounded-2xl bg-white/10 p-4">
                <p className="text-xs text-forest-200">Spent</p>
                <p className="mt-1 font-display text-xl font-bold">{money(report.expenses_total)}</p>
              </div>
            </div>
          </motion.div>

          <div className="grid gap-4 md:grid-cols-2">
            {/* Money in */}
            <Section title="Money in">
              <Line label="Collected this month" value={report.collected} bold />
              {/* How it was paid */}
              <div className="my-2 space-y-2">
                {Object.keys(METHOD_LABELS).map((key) => (
                  <div key={key}>
                    <div className="flex justify-between text-xs text-muted">
                      <span>{METHOD_LABELS[key]}</span>
                      <span>{money(report.by_method[key])}</span>
                    </div>
                    <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-forest-100">
                      <div className="h-full rounded-full bg-forest-500" style={{ width: `${(report.by_method[key] / methodTotal) * 100}%` }} />
                    </div>
                  </div>
                ))}
              </div>
              <div className="mt-3 border-t border-forest-100 pt-2">
                <Line label="Charges that fell due this month" value={report.billed} />
                <Line label="Still owed at month end" value={report.owed_at_month_end} />
              </div>
            </Section>

            {/* Money out */}
            <Section title="Money out">
              {report.expenses_by_category.map((item) => (
                <Line key={item.category} label={categoryLabel(item.category)} value={item.total} />
              ))}
              <Line label="Repairs (from the Repairs page)" value={report.repairs_cost} />
              <div className="mt-2 border-t border-forest-100 pt-2">
                <Line label="Total spent" value={report.expenses_total} bold />
                {report.general_expenses > 0 && <Line label="of which general (not one property)" value={report.general_expenses} muted />}
              </div>
            </Section>
          </div>

          {/* Occupancy and empty units */}
          <div className="grid gap-4 md:grid-cols-2">
            <Section title="Occupancy">
              <div className="flex items-center gap-5">
                <div className="scale-75">
                  <OccupancyRing percent={report.occupancy_percent} />
                </div>
                <div>
                  <p className="font-display text-2xl font-bold text-forest-900">
                    {report.units_occupied} of {report.units_total}
                  </p>
                  <p className="text-sm text-muted">units occupied</p>
                  <p className="mt-1 text-xs text-muted">
                    {report.occupancy_basis === 'now' ? 'As of today' : `Worked out from lease dates, on the last day of ${monthLabel(month)}`}
                  </p>
                </div>
              </div>
            </Section>

            <Section title="Empty right now">
              {report.vacant_now.length === 0 ? (
                <p className="text-sm text-muted">No empty units.</p>
              ) : (
                <div className="divide-y divide-forest-100">
                  {report.vacant_now.slice(0, 8).map((unit) => (
                    <div key={unit.unit_id} className="flex items-center justify-between gap-3 py-2 text-sm">
                      <div className="min-w-0">
                        <p className="font-semibold text-forest-900">
                          {unit.unit_number} <span className="font-normal text-muted">· {unit.property_name}</span>
                        </p>
                        <p className="text-xs text-muted">{money(unit.rent_amount)} a month</p>
                      </div>
                      <p className={`shrink-0 font-semibold ${unit.vacant_days > 30 ? 'text-terracotta' : 'text-forest-700'}`}>
                        {unit.vacant_days} day{unit.vacant_days === 1 ? '' : 's'}
                      </p>
                    </div>
                  ))}
                  {report.vacant_now.length > 8 && <p className="pt-2 text-xs text-muted">and {report.vacant_now.length - 8} more (all of them are in the Excel file)</p>}
                </div>
              )}
            </Section>
          </div>

          {/* One line for each property */}
          {report.properties.length > 1 && (
            <Section title="By property">
              <div className="overflow-x-auto">
                <table className="w-full min-w-[30rem] text-left text-sm">
                  <thead className="text-xs text-muted">
                    <tr>
                      <th className="pb-2 font-medium">Property</th>
                      <th className="pb-2 text-right font-medium">Collected</th>
                      <th className="pb-2 text-right font-medium">Spent</th>
                      <th className="pb-2 text-right font-medium">Left over</th>
                      <th className="pb-2 text-right font-medium">Occupied</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-forest-100">
                    {report.properties.map((row) => (
                      <tr key={row.property_id}>
                        <td className="py-2 font-semibold text-forest-900">{row.name}</td>
                        <td className="py-2 text-right">{money(row.collected)}</td>
                        <td className="py-2 text-right">{money(row.expenses)}</td>
                        <td className={`py-2 text-right font-semibold ${row.net < 0 ? 'text-terracotta' : 'text-forest-700'}`}>{money(row.net)}</td>
                        <td className="py-2 text-right">
                          {row.units_occupied}/{row.units_total}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Section>
          )}

          {/* The last six months */}
          <Section title="Last 6 months">
            <div className="h-56">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData} margin={{ top: 8, right: 8, left: -12, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#ddefe5" vertical={false} />
                  <XAxis dataKey="name" tickLine={false} axisLine={false} fontSize={12} />
                  <YAxis tickLine={false} axisLine={false} fontSize={12} tickFormatter={(value) => (value >= 1000 ? `${Math.round(value / 1000)}k` : value)} />
                  <Tooltip formatter={(value) => money(value)} />
                  <Legend iconType="circle" />
                  <Bar dataKey="Collected" fill="#2f7d5b" radius={[6, 6, 0, 0]} isAnimationActive={false} />
                  <Bar dataKey="Spent" fill="#c4533a" radius={[6, 6, 0, 0]} isAnimationActive={false} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Section>
        </div>
      )}
    </div>
  )
}