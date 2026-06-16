// src/routes/layouts/AuthLayout.tsx
import { Navigate, Outlet } from 'react-router'
import { useAuth } from '@/context/AuthContext'

export default function AuthLayout() {
  const { isAuthenticated, loading } = useAuth()

  if (loading) return null

  if (isAuthenticated) {
    return <Navigate to="/" replace />
  }

  return (
    <div>
      <Outlet />
    </div>
  )
}
