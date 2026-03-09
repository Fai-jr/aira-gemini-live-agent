import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useAiraStore } from './store/useAiraStore'
import Home from './pages/Home'
import Auth from './pages/Auth'

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { token } = useAiraStore()
  return token ? <>{children}</> : <Navigate to="/auth" replace />
}

function PublicRoute({ children }: { children: React.ReactNode }) {
  const { token } = useAiraStore()
  return !token ? <>{children}</> : <Navigate to="/" replace />
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/auth" element={
          <PublicRoute><Auth /></PublicRoute>
        } />
        <Route path="/" element={
          <ProtectedRoute><Home /></ProtectedRoute>
        } />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}