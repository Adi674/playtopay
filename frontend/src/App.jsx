import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext'
import Login from './pages/Login'
import Register from './pages/Register'
import KYCForm from './pages/KYCForm'
import ReviewerDashboard from './pages/ReviewerDashboard'

function ProtectedRoute({ children, requiredRole }) {
  const { user, isLoggedIn } = useAuth()
  if (!isLoggedIn) return <Navigate to="/login" replace />
  if (requiredRole && user?.role !== requiredRole) {
    return <Navigate to={user?.role === 'reviewer' ? '/reviewer' : '/kyc'} replace />
  }
  return children
}

function HomeRedirect() {
  const { user, isLoggedIn } = useAuth()
  if (!isLoggedIn) return <Navigate to="/login" replace />
  return <Navigate to={user?.role === 'reviewer' ? '/reviewer' : '/kyc'} replace />
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<HomeRedirect />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/kyc" element={
            <ProtectedRoute requiredRole="merchant"><KYCForm /></ProtectedRoute>
          } />
          <Route path="/reviewer" element={
            <ProtectedRoute requiredRole="reviewer"><ReviewerDashboard /></ProtectedRoute>
          } />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
