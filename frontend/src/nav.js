// Import the icons we use
import { Building2, ClipboardList, LayoutDashboard, LayoutGrid, Receipt, UserCog, Users, Wallet, Wrench } from 'lucide-react'

// The four main screens that always sit in the phone's bottom bar
export const DASHBOARD = { to: '/', label: 'Dashboard', short: 'Home', icon: LayoutDashboard }
export const PROPERTIES = { to: '/properties', label: 'Properties', icon: Building2 }
export const TENANTS = { to: '/tenants', label: 'Tenants', icon: Users }
export const PAYMENTS = { to: '/payments', label: 'Payments', icon: Wallet }

// Everything else lives under "More" (add new screens here)
export const MORE_ITEMS = [
  { to: '/bills', label: 'Bills', icon: Receipt, description: 'Water, electricity and Wi-Fi' },
  { to: '/repairs', label: 'Repairs', icon: Wrench, description: 'Problems that need fixing' },
  { to: '/team', label: 'Team', icon: UserCog, description: 'Caretakers and what they can see' },
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