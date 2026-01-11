import { Routes, Route, Navigate, Outlet } from 'react-router-dom';
import RunListPage from './pages/RunList';
import RunDetailsPage from './pages/RunDetails';
import AccountPage from './pages/Account';
import AdminPage from './pages/Admin';
import LoginPage from './pages/Login';
import { useAuth } from './contexts/AuthContext';
import DashboardLayout from './components/DashboardLayout';

function RequireAuth({ children }: { children: JSX.Element }) {
  const { token } = useAuth();
  if (!token) {
    return <Navigate to="/login" replace />;
  }
  return children;
}

function ProtectedRoutes() {
  return (
    <RequireAuth>
      <DashboardLayout>
        <Outlet />
      </DashboardLayout>
    </RequireAuth>
  );
}

function App() {
  const { token } = useAuth();
  const fallbackPath = token ? '/runs' : '/login';

  return (
    <Routes>
      <Route path="/" element={<Navigate to={fallbackPath} replace />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<LoginPage initialMode="register" />} />
      <Route element={<ProtectedRoutes />}>
        <Route path="/runs" element={<RunListPage />} />
        <Route path="/runs/:id" element={<RunDetailsPage />} />
        <Route path="/account" element={<AccountPage />} />
        <Route path="/admin" element={<AdminPage />} />
      </Route>
      <Route path="*" element={<Navigate to={fallbackPath} replace />} />
    </Routes>
  );
}

export default App;
