import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './context/AuthContext'
import Layout from './components/Layout'
import Login from './pages/Login'
import Overview from './pages/Overview'
import Opportunities from './pages/Opportunities'
import OpportunityDetail from './pages/OpportunityDetail'
import Transactions from './pages/Transactions'
import Customers from './pages/Customers'
import PaymentMethods from './pages/PaymentMethods'
import Assistant from './pages/Assistant'
import Analytics from './pages/Analytics'
import Settings from './pages/Settings'

function Protected({ children }) {
  const { isAuthenticated } = useAuth()

  return isAuthenticated ? children : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />

      <Route
        path="/"
        element={
          <Protected>
            <Layout />
          </Protected>
        }
      >
        <Route index element={<Overview />} />
        <Route path="opportunities" element={<Opportunities />} />
        <Route path="opportunities/:id" element={<OpportunityDetail />} />
        <Route path="transactions" element={<Transactions />} />
        <Route path="customers" element={<Customers />} />
        <Route path="payment-methods" element={<PaymentMethods />} />
        <Route path="assistant" element={<Assistant />} />
        <Route path="analytics" element={<Analytics />} />
        <Route path="settings" element={<Settings />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}