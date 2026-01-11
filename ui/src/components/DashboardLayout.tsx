import { ReactNode } from 'react';
import { NavLink } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { fetchCurrentUser, fetchWallet } from '../services/api';
import { useAuth } from '../contexts/AuthContext';

interface Props {
  children: ReactNode;
}

function DashboardLayout({ children }: Props) {
  const { logout } = useAuth();
  const userQuery = useQuery({
    queryKey: ['layout-user'],
    queryFn: fetchCurrentUser,
  });
  const walletQuery = useQuery({
    queryKey: ['layout-wallet'],
    queryFn: fetchWallet,
  });
  const isAdmin = (userQuery.data?.role || '').toLowerCase() === 'admin';

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-brand">CodeReview 1C</div>
        <nav className="app-nav">
          <NavLink to="/runs" className={({ isActive }) => (isActive ? 'active-link' : undefined)}>
            Запуски
          </NavLink>
          <NavLink to="/account" className={({ isActive }) => (isActive ? 'active-link' : undefined)}>
            Личный кабинет
          </NavLink>
          {isAdmin && (
            <NavLink to="/admin" className={({ isActive }) => (isActive ? 'active-link' : undefined)}>
              Админка
            </NavLink>
          )}
        </nav>
        <div className="app-user">
          <div>
            <span>{userQuery.data?.email ?? '—'}</span>
            <span className="muted">
              Баланс:{' '}
              {walletQuery.isLoading
                ? '…'
                : typeof walletQuery.data?.balance === 'number'
                ? `${walletQuery.data.balance} баллов`
                : '—'}
            </span>
          </div>
          <button className="btn btn-ghost" onClick={logout}>
            Выйти
          </button>
        </div>
      </header>
      <main className="app-main">{children}</main>
    </div>
  );
}

export default DashboardLayout;
