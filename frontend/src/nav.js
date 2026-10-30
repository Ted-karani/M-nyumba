// Import the icons we use
import {
  Bell,
  BellRing,
  Building2,
  CalendarCheck,
  ClipboardList,
  Coins,
  FileText,
  FolderOpen,
  History,
  Home,
  LayoutDashboard,
  LayoutGrid,
  Megaphone,
  Newspaper,
  Receipt,
  Smartphone,
  Sparkles,
  UserCog,
  Users,
  Wallet,
  Wrench,
} from 'lucide-react'

// The four main screens that always sit in the phone's bottom bar
export const DASHBOARD = { to: '/', label: 'Dashboard', short: 'Home', icon: LayoutDashboard }
export const PROPERTIES = { to: '/properties', label: 'Properties', icon: Building2 }
export const TENANTS = { to: '/tenants', label: 'Tenants', icon: Users }
export const PAYMENTS = { to: '/payments', label: 'Payments', icon: Wallet }

// Everything else lives under "More" (add new screens here)
export const MORE_ITEMS = [
  { to: '/quick-setup', label: 'Quick setup', icon: Sparkles, description: 'Add a whole building and all its units in a minute' },
  { to: '/owing', label: 'Who owes me', icon: BellRing, description: 'Remind everyone who is late, in a few taps' },
  { to: '/listings', label: 'Vacancy listings', icon: Megaphone, description: 'Advertise empty units with photos and a link' },
  { to: '/notices', label: 'Notice board', icon: Newspaper, description: 'Announcements your tenants can read' },
  { to: '/portal-access', label: 'Tenant portal', icon: Smartphone, description: 'Let tenants see their balance and report problems' },
  { to: '/bills', label: 'Bills', icon: Receipt, description: 'Water, electricity and Wi-Fi' },
  { to: '/repairs', label: 'Repairs', icon: Wrench, description: 'Problems that need fixing' },
  { to: '/expenses', label: 'Expenses', icon: Coins, description: 'Caretaker pay, taxes, security and more' },
  { to: '/reports', label: 'Reports', icon: FileText, description: 'Monthly statement with PDF and Excel' },
  { to: '/documents', label: 'Documents', icon: FolderOpen, description: 'Leases, title deeds, permits and photos' },
  { to: '/tasks', label: 'Tasks', icon: CalendarCheck, description: 'Tax dates, renewals and recurring jobs' },
  { to: '/team', label: 'Team', icon: UserCog, description: 'Caretakers and what they can see' },
  { to: '/activity', label: 'Activity log', icon: History, description: 'Who changed what, and when' },
  { to: '/setup', label: 'Set up tenants', icon: ClipboardList, description: 'Add current tenants or import your notebook' },
]

// The "More" button in the phone's bottom bar (it also lights up on any screen inside it)
export const MORE_TAB = {
  to: '/more',
  label: 'More',
  icon: LayoutGrid,
  matches: ['/more', ...MORE_ITEMS.map((item) => item.to)],
}

// What an owner sees in the phone's bottom bar, and in the desktop sidebar
export const OWNER_BAR = [DASHBOARD, PROPERTIES, TENANTS, PAYMENTS, MORE_TAB]
export const OWNER_SIDEBAR = [DASHBOARD, PROPERTIES, TENANTS, PAYMENTS, ...MORE_ITEMS]

// What a caretaker sees (in both places)
export const CARETAKER_ITEMS = [
  { to: '/', label: 'My properties', short: 'Properties', icon: Building2 },
  { to: '/repairs', label: 'Repairs', icon: Wrench },
]

// What a tenant sees (in both places)
export const TENANT_ITEMS = [
  { to: '/', label: 'My rent', short: 'My rent', icon: Home },
  { to: '/repairs', label: 'Report a problem', short: 'Problems', icon: Wrench },
  { to: '/notices', label: 'Notices', icon: Bell },
]

// What the admin sees (in both places)
export const ADMIN_ITEMS = [
  { to: '/', label: 'Overview', icon: LayoutDashboard },
  { to: '/accounts', label: 'Landlords', icon: Users },
  { to: '/records', label: 'Payments and log', short: 'Records', icon: History },
]