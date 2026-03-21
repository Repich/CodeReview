import { ReactNode } from 'react';
import { NavLink } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { fetchCurrentUser, fetchModelLabConfig, fetchWallet } from '../services/api';
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
  const role = (userQuery.data?.role || '').toLowerCase();
  const isAdmin = role === 'admin';
  const isTeacher = role === 'teacher';
  const canManage = isAdmin || isTeacher;
  const showTeacherDocs = canManage;
  const modelLabConfigQuery = useQuery({
    queryKey: ['layout-model-lab-config'],
    queryFn: fetchModelLabConfig,
    enabled: isAdmin,
    retry: false,
  });
  const showModelLab = isAdmin && Boolean(modelLabConfigQuery.data?.enabled);

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
          {canManage && (
            <NavLink to="/admin" className={({ isActive }) => (isActive ? 'active-link' : undefined)}>
              {isAdmin ? 'Админка' : 'Обучение'}
            </NavLink>
          )}
          {showModelLab && (
            <NavLink to="/model-lab" className={({ isActive }) => (isActive ? 'active-link' : undefined)}>
              Model Lab
            </NavLink>
          )}
          {showTeacherDocs && (
            <a href="/help/teacher" target="_blank" rel="noreferrer">
              Документация учителя
            </a>
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
