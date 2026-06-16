import { useAuth } from '@/context/AuthContext'
import './navbar.css'

export default function NavBar() {
  const { user, logout } = useAuth()

  const initials = user?.username
    ? user.username.slice(0, 2).toUpperCase()
    : '?'

  return (
    <header className="navbar">
      <div className="navbar-brand">
        <div className="navbar-brand-mark">G</div>
        <span className="navbar-brand-name">Grotto</span>
      </div>
      <div className="navbar-right">
        <div className="navbar-avatar">{initials}</div>
        <button type="button" onClick={logout} className="navbar-logout">
          Sign out
        </button>
      </div>
    </header>
  )
}
