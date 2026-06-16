// src/routes/layouts/AppLayout.tsx
import { Navigate, Outlet } from 'react-router'
import { useAuth } from '@/context/AuthContext'
import NavBar from '@/components/NavBar'

export default function AppLayout() {
  const { isAuthenticated, loading } = useAuth()

  if (loading) return null

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  return (
    <div>
      <NavBar />
      <Outlet />
    </div>
  )
}
