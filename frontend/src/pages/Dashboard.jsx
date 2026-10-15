// Import the React tools we need
import { useCallback, useEffect, useState } from 'react'
// Import the page-switching tool
import { Link } from 'react-router-dom'
// Import the animation tool
import { motion } from 'framer-motion'
// Import the icons we use
import {
  Building2,
  CalendarClock,
  CheckCircle2,
  ChevronRight,
  DoorOpen,
  MessageCircle,
  RefreshCw,
  TriangleAlert,
  Wallet,
  Wrench,
} from 'lucide-react'
// Import our own files
import { useAuth } from '../AuthContext'
import { getDashboard } from '../api'
import { formatDate, money, whatsappLink } from '../format'
import CountUp from '../components/CountUp'
import OccupancyRing from '../components/OccupancyRing'
import RentBanner from '../components/RentBanner'

// How the whole page appears: the cards come in one after another
const listAnimation = { hidden: {}, show: { transition: { staggerChildren: 0.08 } } }
// How each card appears: fade in while sliding up
const itemAnimation = { hidden: { opacity: 0, y: 18 }, show: { opacity: 1, y: 0 } }

// Pick a greeting based on the time of day
function greeting() {
  // The current hour, from 0 to 23
  const hour = new Date().getHours()
  if (hour < 12) return 'Good morning'
  if (hour < 17) return 'Good afternoon'
  return 'Good evening'
}

// Say how long ago something was reported, like "3 days ago"
function age(createdAt) {
  // The backend saves times in UTC without a "Z" on the end, so we add it
  const created = new Date(createdAt.endsWith('Z') ? createdAt : `${createdAt}Z`)
  // How many whole days have passed
  const days = Math.floor((Date.now() - created.getTime()) / 86400000)
  if (days <= 0) return 'Today'
  if (days === 1) return '1 day ago'
  return `${days} days ago`
}

// A grey pulsing box shown while the data loads
function Skeleton({ className }) {
  return <div className={`animate-pulse rounded-3xl bg-forest-100 ${className}`} />
}

// The heading above each section, with an optional count and an optional "see all" link
function SectionTitle({ icon: Icon, color, title, count, to, linkLabel }) {
  return (
    <motion.div variants={itemAnimation} className="mt-8 flex items-center justify-between gap-2">
      <div className="flex items-center gap-2">
        <Icon size={20} className={color} />
        <h2 className="text-xl font-bold text-forest-900">{title}</h2>
        {count > 0 && (
          <span className="rounded-full bg-forest-100 px-2.5 py-0.5 text-sm font-semibold text-forest-700">{count}</span>
        )}
      </div>
      {to && (
        <Link to={to} className="flex items-center gap-1 text-sm font-medium text-forest-700 hover:underline">
          {linkLabel} <ChevronRight size={16} />
        </Link>
      )}
    </motion.div>
  )
}

// One overdue tenant, with a button to remind them on WhatsApp
function OverdueCard({ item }) {
  // Use only the first name in the message
  const firstName = item.tenant_name.split(' ')[0]
  // The message that will be typed in WhatsApp for us
  const message =
    `Hello ${firstName}, a friendly reminder that ${money(item.amount_overdue)} for house ` +
    `${item.unit_number} at ${item.property_name} is overdue by ${item.days_late} days. ` +
    `Kindly clear it as soon as you can. Thank you.`

  return (
    <motion.div variants={itemAnimation} className="rounded-2xl bg-paper p-4 shadow-sm">
      {/* The top part opens the tenant's page, where payments can be recorded */}
      <Link to={`/tenants/${item.tenant_id}`} className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate font-semibold text-forest-900">{item.tenant_name}</p>
          <p className="truncate text-sm text-muted">
            {item.unit_number} · {item.property_name}
          </p>
          {/* Tenants who already left but still owe money get a small label */}
          {item.lease_status === 'ended' && (
            <span className="mt-1 inline-block rounded-full bg-amber/20 px-2 py-0.5 text-xs font-semibold text-amber">
              Moved out
            </span>
          )}
        </div>
        <div className="text-right">
          <p className="font-display text-lg font-bold text-terracotta">{money(item.amount_overdue)}</p>
          <p className="text-xs text-muted">{item.days_late} days late</p>
        </div>
      </Link>
      {/* This button opens WhatsApp with the reminder already written */}
      <motion.a
        whileTap={{ scale: 0.97 }}
        href={whatsappLink(item.tenant_phone, message)}
        target="_blank"
        rel="noopener noreferrer"
        className="mt-3 flex items-center justify-center gap-2 rounded-xl bg-forest-500 py-2.5 text-sm font-semibold text-white transition hover:bg-forest-700"
      >
        <MessageCircle size={16} /> Remind on WhatsApp
      </motion.a>
    </motion.div>
  )
}

// The dashboard screen
export default function Dashboard() {
  // Get the logged-in user
  const { user } = useAuth()
  // The numbers from the backend (nothing until they arrive)
  const [data, setData] = useState(null)
  // The error message, if loading failed
  const [error, setError] = useState('')

  // Load the dashboard numbers from the backend (a quiet reload keeps the old numbers on screen)
  const load = useCallback((quiet = false) => {
    setError('')
    if (!quiet) setData(null)
    getDashboard()
      .then(setData)
      .catch((err) => setError(err.message))
  }, [])

  // Load them when the screen first opens
  useEffect(() => {
    load()
  }, [load])

  // Use only the first name in the greeting
  const firstName = user.full_name.split(' ')[0]
  // Today's date, written out nicely
  const today = new Date().toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long' })

  // The greeting at the top (shown while loading too)
  const header = (
    <div className="mb-6">
      <p className="text-muted">
        {greeting()} · {today}
      </p>
      <h1 className="text-3xl font-extrabold text-forest-900">{firstName}</h1>
    </div>
  )

  // If loading failed, show the message and a retry button
  if (error) {
    return (
      <div>
        {header}
        <div className="rounded-3xl bg-terracotta/10 p-6 text-terracotta">
          <p className="font-semibold">Could not load your dashboard</p>
          <p className="mt-1 text-sm">{error}</p>
          <motion.button
            whileTap={{ scale: 0.97 }}
            onClick={() => load()}
            className="mt-4 flex items-center gap-2 rounded-xl bg-terracotta px-4 py-2 text-sm font-semibold text-white"
          >
            <RefreshCw size={16} /> Try again
          </motion.button>
        </div>
      </div>
    )
  }

  // While waiting for the numbers, show grey placeholder boxes
  if (!data) {
    return (
      <div>
        {header}
        <div className="grid gap-4 lg:grid-cols-3">
          <Skeleton className="h-56 lg:col-span-2" />
          <Skeleton className="h-56" />
        </div>
        <Skeleton className="mt-4 h-40" />
      </div>
    )
  }

  // Shortcuts for the unit numbers and the repairs
  const units = data.units
  const repairs = data.repairs
  const repairCount = repairs.open_count + repairs.in_progress_count

  return (
    <motion.div variants={listAnimation} initial="hidden" animate="show">
      {header}

      {/* The card that offers to add this month's rent (only shows when rent is missing) */}
      <RentBanner onDone={() => load(true)} />

      {/* The top row: the money card and the occupancy card */}
      <div className="grid gap-4 lg:grid-cols-3">
        {/* The green money card */}
        <motion.div variants={itemAnimation} className="rounded-3xl bg-forest-900 p-6 text-white shadow-xl lg:col-span-2">
          <div className="flex items-center gap-2 text-forest-200">
            <Wallet size={18} />
            <span className="text-sm">Collected this month</span>
          </div>
          <div className="mt-2 font-display text-5xl font-bold">
            <CountUp value={data.collected_this_month} format={money} />
          </div>
          <div className="mt-6 grid grid-cols-2 gap-3">
            <div className="rounded-2xl bg-white/10 p-4">
              <p className="text-xs text-forest-200">Still owed (all charges)</p>
              <p className="mt-1 font-display text-xl font-bold">{money(data.total_outstanding)}</p>
            </div>
            <div className="rounded-2xl bg-terracotta/30 p-4">
              <p className="text-xs text-forest-100">Overdue now</p>
              <p className="mt-1 font-display text-xl font-bold">{money(data.total_overdue)}</p>
            </div>
          </div>
        </motion.div>

        {/* The occupancy card */}
        <motion.div variants={itemAnimation} className="flex flex-col items-center rounded-3xl bg-paper p-6 shadow-sm">
          <OccupancyRing percent={units.occupancy_percent} />
          <div className="mt-4 grid w-full grid-cols-3 gap-2 text-center">
            <div>
              <p className="font-display text-xl font-bold text-forest-700">{units.occupied}</p>
              <p className="text-xs text-muted">Occupied</p>
            </div>
            <div>
              <p className="font-display text-xl font-bold text-amber">{units.vacant}</p>
              <p className="text-xs text-muted">Vacant</p>
            </div>
            <div>
              <p className="font-display text-xl font-bold text-muted">{units.maintenance}</p>
              <p className="text-xs text-muted">Repairs</p>
            </div>
          </div>
        </motion.div>
      </div>

      {/* The overdue tenants */}
      <SectionTitle icon={TriangleAlert} color="text-terracotta" title="Overdue" count={data.overdue_count} />
      {data.overdue.length === 0 ? (
        // Nobody is late: show good news
        <motion.div
          variants={itemAnimation}
          className="mt-3 flex items-center gap-3 rounded-2xl bg-forest-100 p-5 text-forest-700"
        >
          <CheckCircle2 size={22} />
          <p className="font-medium">Everyone is up to date. Nothing overdue.</p>
        </motion.div>
      ) : (
        // Show one card for each overdue tenant
        <div className="mt-3 grid gap-3 md:grid-cols-2">
          {data.overdue.map((item) => (
            <OverdueCard key={item.lease_id} item={item} />
          ))}
        </div>
      )}

      {/* The problems that need fixing */}
      <SectionTitle
        icon={Wrench}
        color="text-amber"
        title="Needs fixing"
        count={repairCount}
        to={repairCount > 0 ? '/repairs' : null}
        linkLabel="See all"
      />
      {repairs.items.length === 0 ? (
        <motion.div
          variants={itemAnimation}
          className="mt-3 flex items-center gap-3 rounded-2xl bg-forest-100 p-5 text-forest-700"
        >
          <CheckCircle2 size={22} />
          <p className="font-medium">Nothing is broken right now.</p>
        </motion.div>
      ) : (
        <div className="mt-3 grid gap-3 md:grid-cols-2">
          {repairs.items.map((repair) => (
            <motion.div key={repair.id} variants={itemAnimation}>
              {/* Each card opens the repairs page */}
              <Link
                to="/repairs"
                className="block rounded-2xl bg-paper p-4 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md"
              >
                <div className="flex items-start justify-between gap-3">
                  <p className="font-semibold text-forest-900">{repair.title}</p>
                  <span
                    className={`shrink-0 rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                      repair.status === 'in_progress' ? 'bg-gold/25 text-forest-900' : 'bg-amber/20 text-amber'
                    }`}
                  >
                    {repair.status === 'in_progress' ? 'In progress' : 'Open'}
                  </span>
                </div>
                <p className="mt-1 truncate text-sm text-muted">
                  {repair.unit_number ? `Unit ${repair.unit_number}` : 'Whole property'} · {repair.property_name}
                </p>
                <div className="mt-2 flex items-center gap-2 text-xs text-muted">
                  {repair.priority === 'urgent' && (
                    <span className="rounded-full bg-terracotta/15 px-2 py-0.5 font-semibold text-terracotta">Urgent</span>
                  )}
                  <span>Reported {age(repair.created_at)}</span>
                </div>
              </Link>
            </motion.div>
          ))}
        </div>
      )}
      {/* If there are more problems than the cards show, say so */}
      {repairCount > repairs.items.length && (
        <motion.p variants={itemAnimation} className="mt-3 text-center text-sm text-muted">
          Showing the {repairs.items.length} most pressing of {repairCount}.
        </motion.p>
      )}

      {/* The empty units */}
      <SectionTitle icon={DoorOpen} color="text-forest-500" title="Vacant units" count={units.vacant} />
      {data.vacant_units.length === 0 ? (
        <motion.div
          variants={itemAnimation}
          className="mt-3 flex items-center gap-3 rounded-2xl bg-forest-100 p-5 text-forest-700"
        >
          <CheckCircle2 size={22} />
          <p className="font-medium">Every unit is occupied or under repair.</p>
        </motion.div>
      ) : (
        <div className="mt-3 grid gap-3 md:grid-cols-2">
          {data.vacant_units.map((unit) => (
            <motion.div key={unit.unit_id} variants={itemAnimation}>
              {/* Each card opens the property it is in */}
              <Link
                to={`/properties/${unit.property_id}`}
                className="flex items-center justify-between gap-3 rounded-2xl bg-paper p-4 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md"
              >
                <div className="min-w-0">
                  <p className="font-display text-lg font-bold text-forest-900">{unit.unit_number}</p>
                  <p className="truncate text-sm text-muted">
                    {unit.unit_type ? `${unit.unit_type} · ` : ''}
                    {unit.property_name}
                  </p>
                </div>
                <div className="text-right">
                  <p className="font-semibold text-forest-900">{money(unit.rent_amount)}</p>
                  <p className="text-xs text-muted">per month</p>
                </div>
              </Link>
            </motion.div>
          ))}
        </div>
      )}

      {/* Leases ending soon */}
      {data.ending_soon.length > 0 && (
        <>
          <SectionTitle icon={CalendarClock} color="text-gold" title="Leaving soon" count={data.ending_soon.length} />
          <div className="mt-3 grid gap-3 md:grid-cols-2">
            {data.ending_soon.map((item) => (
              <motion.div key={item.lease_id} variants={itemAnimation}>
                {/* Each card opens the tenant's page */}
                <Link
                  to={`/tenants/${item.tenant_id}`}
                  className="flex items-center justify-between gap-3 rounded-2xl bg-paper p-4 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md"
                >
                  <div className="min-w-0">
                    <p className="truncate font-semibold text-forest-900">{item.tenant_name}</p>
                    <p className="truncate text-sm text-muted">
                      {item.unit_number} · {item.property_name}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-semibold text-forest-900">{formatDate(item.end_date)}</p>
                    <p className="text-xs text-muted">
                      {item.days_left === 0 ? 'Today' : `in ${item.days_left} days`}
                    </p>
                  </div>
                </Link>
              </motion.div>
            ))}
          </div>
        </>
      )}

      {/* Each property */}
      <SectionTitle icon={Building2} color="text-forest-500" title="Your properties" count={0} to="/properties" linkLabel="Manage" />
      {data.properties.length === 0 ? (
        // No properties yet
        <motion.p variants={itemAnimation} className="mt-3 rounded-2xl bg-paper p-5 text-muted shadow-sm">
          No properties yet. Add one from the Properties page.
        </motion.p>
      ) : (
        <div className="mt-3 grid gap-3 md:grid-cols-2">
          {data.properties.map((prop) => (
            <motion.div key={prop.property_id} variants={itemAnimation}>
              {/* The whole card opens the property's page */}
              <Link
                to={`/properties/${prop.property_id}`}
                className="block rounded-2xl bg-paper p-4 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate font-semibold text-forest-900">{prop.name}</p>
                    <p className="truncate text-sm text-muted">
                      {[prop.town, prop.county].filter(Boolean).join(', ') || 'No location yet'}
                    </p>
                  </div>
                  <p className="text-sm font-semibold text-forest-700">
                    {prop.units.occupied}/{prop.units.total} occupied
                  </p>
                </div>
                {/* A bar that fills up to show how full the property is */}
                <div className="mt-3 h-2 overflow-hidden rounded-full bg-forest-100">
                  <motion.div
                    className="h-full rounded-full bg-forest-500"
                    initial={{ width: 0 }}
                    animate={{ width: `${prop.units.occupancy_percent}%` }}
                    transition={{ duration: 0.9, ease: 'easeOut', delay: 0.3 }}
                  />
                </div>
                <p className="mt-2 text-xs text-muted">
                  {prop.units.vacant} vacant · {prop.units.maintenance} under repair
                </p>
              </Link>
            </motion.div>
          ))}
        </div>
      )}
    </motion.div>
  )
}