import { useAuth } from '@/context/AuthContext'
import './dashboard.css'

export default function Dashboard() {
  const { user } = useAuth()

  return (
    <div className="dashboard">
      <main className="dashboard-main">
        <div className="dashboard-welcome">
          <h1>Welcome back, {user?.username}.</h1>
        </div>
      </main>
    </div>
  )
}
