// src/routes/layouts/AppLayout.tsx
import { Navigate, Outlet } from 'react-router'
import { useAuth } from '@/context/AuthContext'

export default function AppLayout() {
  const { isAuthenticated, loading } = useAuth()

  if (loading) return null

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  return (
    <div>
      {/* TODO: Shared nav/sidebar goes here */}
      <Outlet />
    </div>
  )
}
