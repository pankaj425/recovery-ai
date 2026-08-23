import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import {
  Activity, BarChart3, Bot, CreditCard, LayoutDashboard, LogOut, Moon,
  RefreshCcw, Settings as SettingsIcon, Sun, Users, Zap,
} from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { useTheme } from '../context/ThemeContext'

const NAV = [
  { to: '/', label: 'Overview', icon: LayoutDashboard },
  { to: '/opportunities', label: 'Revenue Recovery', icon: Zap },
  { to: '/transactions', label: 'Transactions', icon: CreditCard },
  { to: '/customers', label: 'Customers', icon: Users },
  { to: '/payment-methods', label: 'Payment Methods', icon: Activity },
  { to: '/assistant', label: 'AI Assistant', icon: Bot },
  { to: '/analytics', label: 'Analytics', icon: BarChart3 },
  { to: '/settings', label: 'Settings', icon: SettingsIcon },
]

export default function Layout() {
  const { user, logout } = useAuth()
  const { dark, toggle } = useTheme()
  const navigate = useNavigate()

  return (
    <div className="flex min-h-screen">
      <aside className="fixed inset-y-0 left-0 z-20 flex w-60 flex-col border-r border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900 max-lg:hidden">
        <div className="flex items-center gap-2.5 px-5 py-5">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-600 text-white">
            <RefreshCcw size={18} />
          </div>
          <div>
            <p className="text-sm font-bold tracking-tight">RecoveryAI</p>
            <p className="text-[11px] text-slate-500 dark:text-slate-400">Revenue Recovery Intelligence</p>
          </div>
        </div>
        <nav className="flex-1 space-y-0.5 px-3">
          {NAV.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition ${
                  isActive
                    ? 'bg-brand-50 text-brand-700 dark:bg-brand-600/15 dark:text-brand-300'
                    : 'text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800'
                }`
              }
            >
              <Icon size={17} />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-slate-200 p-4 dark:border-slate-800">
          <p className="truncate text-sm font-medium">{user?.name ?? 'Merchant'}</p>
          <p className="truncate text-xs text-slate-500 dark:text-slate-400">{user?.email}</p>
        </div>
      </aside>

      <div className="flex min-h-screen w-full flex-col lg:pl-60">
        <header className="sticky top-0 z-10 flex items-center justify-between border-b border-slate-200 bg-white/80 px-6 py-3 backdrop-blur dark:border-slate-800 dark:bg-slate-900/80">
          <div className="flex items-center gap-3 lg:hidden">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600 text-white"><RefreshCcw size={16} /></div>
            <span className="font-bold">RecoveryAI</span>
          </div>
          <div className="hidden text-xs text-slate-500 dark:text-slate-400 lg:block">
            Payments recovered intelligently — every number on this dashboard is computed live from your transaction data.
          </div>
          <div className="flex items-center gap-2">
            <button onClick={toggle} className="btn-secondary !px-2.5" title="Toggle theme">
              {dark ? <Sun size={16} /> : <Moon size={16} />}
            </button>
            <nav className="flex items-center gap-1 lg:hidden">
              {NAV.slice(0, 4).map(({ to, icon: Icon }) => (
                <NavLink key={to} to={to} end={to === '/'} className="btn-secondary !px-2.5"><Icon size={16} /></NavLink>
              ))}
            </nav>
            <button
              onClick={() => { logout(); navigate('/login') }}
              className="btn-secondary"
              title="Sign out"
            >
              <LogOut size={16} /> Sign out
            </button>
          </div>
        </header>
        <main className="flex-1 p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
