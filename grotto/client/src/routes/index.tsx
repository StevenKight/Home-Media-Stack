// src/routes/index.tsx
import { createBrowserRouter } from 'react-router'
import AppLayout from '@/routes/layouts/AppLayout'
import AuthLayout from '@/routes/layouts/AuthLayout'
import Login from '@/routes/auth/Login'
import Register from '@/routes/auth/Register'
import Dashboard from '@/routes/home/Dashboard'

export const router = createBrowserRouter([
  {
    element: <AuthLayout />,
    children: [
      { path: '/login', element: <Login /> },
      { path: '/register', element: <Register /> },
    ]
  },
  {
    element: <AppLayout />,   // protected routes go here
    children: [
      { path: '/', element: <Dashboard /> },
    ]
  }
])
