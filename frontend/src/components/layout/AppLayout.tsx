import { NavLink, Outlet } from 'react-router-dom'

const navItems = [
  { to: '/', label: 'Dashboard', icon: 'H' },
  { to: '/reports', label: 'Reports', icon: 'R' },
  { to: '/quick-assessment', label: 'Quick Assessment', icon: 'Q' },
  { to: '/pipeline', label: 'Dev Pipeline', icon: 'P' },
  { to: '/prompts', label: 'Prompt Editor', icon: 'E' },
  { to: '/examples', label: 'Examples', icon: 'X' },
  { to: '/history', label: 'Version History', icon: 'V' },
  { to: '/settings', label: 'Settings', icon: 'S' },
]

export default function AppLayout() {
  return (
    <div className="flex h-screen bg-gray-50">
      {/* Sidebar */}
      <nav className="w-56 bg-white border-r border-gray-200 flex flex-col">
        <div className="p-4 border-b border-gray-200">
          <h1 className="text-lg font-bold text-gray-800">Credit Paper</h1>
          <p className="text-xs text-gray-500">Assessment Agent</p>
        </div>
        <div className="flex-1 py-2">
          {navItems.map(item => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) =>
                `flex items-center px-4 py-2.5 text-sm transition-colors ${
                  isActive
                    ? 'bg-blue-50 text-blue-700 font-medium border-r-2 border-blue-700'
                    : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                }`
              }
            >
              <span className="w-6 h-6 rounded bg-gray-100 flex items-center justify-center text-xs font-mono mr-3">
                {item.icon}
              </span>
              {item.label}
            </NavLink>
          ))}
        </div>
      </nav>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  )
}
