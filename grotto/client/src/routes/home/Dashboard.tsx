import { useAuth } from '@/context/AuthContext'
import './dashboard.css'

export default function Dashboard() {
  const { user, logout } = useAuth()

  const initials = user?.username
    ? user.username.slice(0, 2).toUpperCase()
    : '?'

  return (
    <div className="dashboard">
      <header className="dashboard-header">
        <div className="dashboard-brand">
          <div className="dashboard-brand-mark">G</div>
          <span className="dashboard-brand-name">Grotto</span>
        </div>
        <div className="dashboard-header-right">
          <div className="dashboard-avatar">{initials}</div>
          <button type="button" onClick={logout} className="dashboard-logout">
            Sign out
          </button>
        </div>
      </header>

      <main className="dashboard-main">
        <div className="dashboard-welcome">
          <h1>Welcome back, {user?.username}.</h1>
        </div>
      </main>
    </div>
  )
}
