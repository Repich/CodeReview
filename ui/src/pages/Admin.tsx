import { FormEvent, useMemo, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import {
  AccessLogEntry,
  CaddyAccessLogEntry,
  ReviewRun,
  adjustWalletBalance,
  createCompany,
  fetchAccessLogs,
  fetchCaddyLogs,
  fetchCompanies,
  fetchCurrentUser,
  fetchRuns,
  fetchUsers,
  forceFailReviewRun,
  requeueReviewRun,
  updateUserStatus,
  updateUserCompany,
  UserProfile,
} from '../services/api';

function AdminPage() {
  const userQuery = useQuery({ queryKey: ['admin-me'], queryFn: fetchCurrentUser });
  const isAdmin = (userQuery.data?.role || '').toLowerCase() === 'admin';
  const [userEmailFilter, setUserEmailFilter] = useState('');
  const [userStatusFilter, setUserStatusFilter] = useState('');
  const [usersLimit, setUsersLimit] = useState('100');
  const [companyName, setCompanyName] = useState('');
  const [companyMessage, setCompanyMessage] = useState<string | null>(null);
  const [companyState, setCompanyState] = useState<'idle' | 'success' | 'error'>('idle');
  const [isSubmittingCompany, setSubmittingCompany] = useState(false);

  const [logIpFilter, setLogIpFilter] = useState('');
  const [logPathFilter, setLogPathFilter] = useState('');
  const [logUserIdFilter, setLogUserIdFilter] = useState('');
  const [logLimit, setLogLimit] = useState('100');

  const [caddyHostFilter, setCaddyHostFilter] = useState('');
  const [caddyIpFilter, setCaddyIpFilter] = useState('');
  const [caddyPathFilter, setCaddyPathFilter] = useState('');
  const [caddyStatusFilter, setCaddyStatusFilter] = useState('');
  const [caddyLimit, setCaddyLimit] = useState('200');
  const [adjustEmail, setAdjustEmail] = useState('');
  const [adjustAmount, setAdjustAmount] = useState('0');
  const [adjustReason, setAdjustReason] = useState('Admin top-up');
  const [adjustMessage, setAdjustMessage] = useState<string | null>(null);
  const [adjustState, setAdjustState] = useState<'idle' | 'success' | 'error'>('idle');
  const [isSubmittingAdjust, setSubmittingAdjust] = useState(false);
  const [runsLimit, setRunsLimit] = useState('100');
  const [runsStatusFilter, setRunsStatusFilter] = useState('');
  const [runsUserFilter, setRunsUserFilter] = useState('');

  const usersQuery = useQuery({
    queryKey: ['admin-users', userEmailFilter, userStatusFilter, usersLimit],
    queryFn: () =>
      fetchUsers({
        email: userEmailFilter || undefined,
        status: userStatusFilter || undefined,
        limit: Number(usersLimit) || 100,
      }),
    enabled: isAdmin,
  });

  const companiesQuery = useQuery({
    queryKey: ['admin-companies'],
    queryFn: () => fetchCompanies({ limit: 500 }),
    enabled: isAdmin,
  });

  const accessLogsQuery = useQuery({
    queryKey: ['admin-access-logs', logIpFilter, logPathFilter, logUserIdFilter, logLimit],
    queryFn: () =>
      fetchAccessLogs({
        ip: logIpFilter || undefined,
        path: logPathFilter || undefined,
        user_id: logUserIdFilter || undefined,
        limit: Number(logLimit) || 100,
      }),
    enabled: isAdmin,
  });

  const caddyLogsQuery = useQuery({
    queryKey: ['admin-caddy-logs', caddyHostFilter, caddyIpFilter, caddyPathFilter, caddyStatusFilter, caddyLimit],
    queryFn: () =>
      fetchCaddyLogs({
        host: caddyHostFilter || undefined,
        ip: caddyIpFilter || undefined,
        path: caddyPathFilter || undefined,
        status: caddyStatusFilter ? Number(caddyStatusFilter) : undefined,
        limit: Number(caddyLimit) || 200,
      }),
    enabled: isAdmin,
  });

  const runsQuery = useQuery({
    queryKey: ['admin-runs', runsLimit],
    queryFn: () => fetchRuns({ limit: Number(runsLimit) || 100 }),
    enabled: isAdmin,
    refetchInterval: (query) => {
      const runs = query.state.data;
      const hasActive = runs?.some((run) => run.status === 'queued' || run.status === 'running');
      return hasActive ? 5000 : false;
    },
  });

  const statusMutation = useMutation({
    mutationFn: ({ userId, status }: { userId: string; status: string }) =>
      updateUserStatus(userId, status),
    onSuccess: () => {
      usersQuery.refetch();
    },
  });

  const runActionMutation = useMutation({
    mutationFn: ({ runId, action }: { runId: string; action: 'fail' | 'requeue' }) =>
      action === 'fail' ? forceFailReviewRun(runId) : requeueReviewRun(runId),
    onSuccess: () => {
      runsQuery.refetch();
    },
  });

  const companyCreateMutation = useMutation({
    mutationFn: (name: string) => createCompany({ name }),
    onSuccess: () => {
      companiesQuery.refetch();
    },
  });

  const companyAssignMutation = useMutation({
    mutationFn: ({ userId, companyId }: { userId: string; companyId: string | null }) =>
      updateUserCompany(userId, companyId),
    onSuccess: () => {
      usersQuery.refetch();
    },
  });

  const handleUserFilterSubmit = (event: FormEvent) => {
    event.preventDefault();
    usersQuery.refetch();
  };

  const handleLogFilterSubmit = (event: FormEvent) => {
    event.preventDefault();
    accessLogsQuery.refetch();
  };

  const handleCaddyFilterSubmit = (event: FormEvent) => {
    event.preventDefault();
    caddyLogsQuery.refetch();
  };

  const handleAdjustSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setSubmittingAdjust(true);
    setAdjustMessage(null);
    setAdjustState('idle');
    try {
      const amountNumber = Math.abs(Number(adjustAmount));
      if (!amountNumber) {
        setAdjustMessage('Укажите сумму больше нуля.');
        setAdjustState('error');
        return;
      }
      await adjustWalletBalance({
        user_email: adjustEmail,
        amount: amountNumber,
        reason: adjustReason,
      });
      setAdjustMessage('Баланс успешно пополнен.');
      setAdjustState('success');
      setAdjustEmail('');
      setAdjustAmount('0');
      setAdjustReason('Admin top-up');
    } catch (err) {
      console.error(err);
      setAdjustMessage('Не удалось выполнить операцию.');
      setAdjustState('error');
    } finally {
      setSubmittingAdjust(false);
    }
  };

  const handleCompanySubmit = async (event: FormEvent) => {
    event.preventDefault();
    setSubmittingCompany(true);
    setCompanyMessage(null);
    setCompanyState('idle');
    const trimmed = companyName.trim();
    if (!trimmed) {
      setCompanyMessage('Укажите название компании.');
      setCompanyState('error');
      setSubmittingCompany(false);
      return;
    }
    try {
      await companyCreateMutation.mutateAsync(trimmed);
      setCompanyMessage('Компания создана.');
      setCompanyState('success');
      setCompanyName('');
    } catch (err) {
      console.error(err);
      setCompanyMessage('Не удалось создать компанию.');
      setCompanyState('error');
    } finally {
      setSubmittingCompany(false);
    }
  };

  const usersSummary = useMemo(() => {
    const users = usersQuery.data || [];
    const active = users.filter((user) => user.status === 'active').length;
    const disabled = users.filter((user) => user.status === 'disabled').length;
    return { active, disabled, total: users.length };
  }, [usersQuery.data]);

  const companyOptions = useMemo(() => companiesQuery.data || [], [companiesQuery.data]);

  const filteredRuns = useMemo(() => {
    const runs = runsQuery.data || [];
    return runs.filter((run) => {
      const matchesStatus = runsStatusFilter ? run.status === runsStatusFilter : true;
      const owner = `${run.user_name || ''} ${run.user_email || ''}`.toLowerCase();
      const matchesUser = runsUserFilter
        ? owner.includes(runsUserFilter.toLowerCase()) || run.id.includes(runsUserFilter)
        : true;
      return matchesStatus && matchesUser;
    });
  }, [runsQuery.data, runsStatusFilter, runsUserFilter]);

  if (userQuery.isLoading) {
    return <p>Загружаем админ-панель...</p>;
  }

  if (userQuery.error || !isAdmin) {
    return <p className="alert alert-error">Доступ только для администраторов.</p>;
  }

  const renderStatusAction = (user: UserProfile) => {
    const targetStatus = user.status === 'active' ? 'disabled' : 'active';
    const label = user.status === 'active' ? 'Заблокировать' : 'Разблокировать';
    return (
      <button
        className="btn btn-secondary"
        disabled={statusMutation.isPending}
        onClick={() => statusMutation.mutate({ userId: user.id, status: targetStatus })}
      >
        {label}
      </button>
    );
  };

  const renderAccessRow = (entry: AccessLogEntry) => (
    <tr key={`${entry.id}-${entry.created_at}`}>
      <td>{new Date(entry.created_at).toLocaleString()}</td>
      <td>{entry.ip_address}</td>
      <td>{entry.country_code || '—'}</td>
      <td>{entry.user_email || entry.user_id || '—'}</td>
      <td>{entry.method}</td>
      <td>{entry.path}</td>
      <td>{entry.status_code}</td>
      <td>{entry.block_reason || '—'}</td>
    </tr>
  );

  const renderCaddyRow = (entry: CaddyAccessLogEntry) => (
    <tr key={`${entry.id}-${entry.created_at}`}>
      <td>{new Date(entry.created_at).toLocaleString()}</td>
      <td>{entry.host || '—'}</td>
      <td>{entry.remote_ip || '—'}</td>
      <td>{entry.method || '—'}</td>
      <td>{entry.uri || '—'}</td>
      <td>{entry.status_code ?? '—'}</td>
      <td>{entry.user_agent ? entry.user_agent.slice(0, 80) : '—'}</td>
    </tr>
  );

  const statusLabels: Record<string, string> = {
    queued: 'В очереди',
    running: 'Выполняется',
    completed: 'Завершён',
    failed: 'Ошибка',
  };

  const formatDuration = (ms: number) => {
    if (ms <= 0) return '0 с';
    const totalSeconds = Math.floor(ms / 1000);
    const hours = Math.floor(totalSeconds / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;
    const parts: string[] = [];
    if (hours) parts.push(`${hours} ч`);
    if (minutes || hours) parts.push(`${minutes} мин`);
    parts.push(`${seconds} с`);
    return parts.join(' ');
  };

  const relativeTime = (value?: string | null) => {
    if (!value) return '—';
    const date = new Date(value);
    const diffMs = date.getTime() - Date.now();
    const minutes = Math.round(diffMs / 60000);
    const rtf = new Intl.RelativeTimeFormat('ru', { numeric: 'auto' });
    if (Math.abs(minutes) < 60) {
      return rtf.format(minutes, 'minute');
    }
    const hours = Math.round(minutes / 60);
    return rtf.format(hours, 'hour');
  };

  const getRunProgress = (run: ReviewRun) => {
    if (run.status === 'queued') {
      const base = run.queued_at ? new Date(run.queued_at).getTime() : null;
      if (base) {
        const diff = Date.now() - base;
        if (diff > 0) {
          return `В очереди ${formatDuration(diff)}`;
        }
      }
      return 'В очереди';
    }
    if (run.status === 'running') {
      const base = run.started_at
        ? new Date(run.started_at).getTime()
        : run.queued_at
          ? new Date(run.queued_at).getTime()
          : null;
      if (base) {
        const diff = Date.now() - base;
        if (diff > 0) {
          return `Выполняется ${formatDuration(diff)}`;
        }
      }
      return 'Выполняется';
    }
    return '—';
  };

  return (
    <div>
      <div className="page-heading">
        <div>
          <p className="muted">Администрирование</p>
          <h1>Панель администратора</h1>
        </div>
        <div className="balance-chip">
          Пользователи: {usersSummary.total} • активные: {usersSummary.active} • заблокированные:{' '}
          {usersSummary.disabled}
        </div>
      </div>

      <div className="card" style={{ marginBottom: '1.5rem' }}>
        <div className="card-header">
          <div>
            <h2 className="card-title">Пользователи</h2>
            <p className="muted">Список зарегистрированных пользователей и их статусы.</p>
          </div>
        </div>
        <form onSubmit={handleUserFilterSubmit} className="form-grid" style={{ gap: '1rem' }}>
          <div className="field">
            <label htmlFor="user-email-filter">Email</label>
            <input
              id="user-email-filter"
              type="text"
              value={userEmailFilter}
              onChange={(event) => setUserEmailFilter(event.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="user-status-filter">Статус</label>
            <select
              id="user-status-filter"
              value={userStatusFilter}
              onChange={(event) => setUserStatusFilter(event.target.value)}
            >
              <option value="">Все</option>
              <option value="active">Активные</option>
              <option value="disabled">Заблокированные</option>
            </select>
          </div>
          <div className="field">
            <label htmlFor="user-limit">Лимит</label>
            <input
              id="user-limit"
              type="number"
              min={1}
              max={500}
              value={usersLimit}
              onChange={(event) => setUsersLimit(event.target.value)}
            />
          </div>
          <button type="submit" className="btn btn-primary">
            Обновить
          </button>
        </form>
        {usersQuery.isLoading && <p className="muted">Загружаем пользователей...</p>}
        {usersQuery.error && <p className="alert alert-error">Не удалось получить список пользователей.</p>}
        <div className="table-container">
          <table className="table">
            <thead>
              <tr>
                <th>Email</th>
                <th>Имя</th>
                <th>Роль</th>
                <th>Компания</th>
                <th>Баланс</th>
                <th>Статус</th>
                <th>Создан</th>
                <th>Действия</th>
              </tr>
            </thead>
            <tbody>
              {usersQuery.data?.map((user) => (
                <tr key={user.id}>
                  <td>{user.email}</td>
                  <td>{user.name || '—'}</td>
                  <td>{user.role}</td>
                  <td>
                    <select
                      value={user.company_id ?? ''}
                      disabled={
                        companyAssignMutation.isPending ||
                        companiesQuery.isLoading ||
                        Boolean(companiesQuery.error)
                      }
                      onChange={(event) => {
                        const value = event.target.value;
                        companyAssignMutation.mutate({
                          userId: user.id,
                          companyId: value ? value : null,
                        });
                      }}
                    >
                      <option value="">—</option>
                      {companyOptions.map((company) => (
                        <option key={company.id} value={company.id}>
                          {company.name}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td>
                    {user.wallet_balance ?? '—'}
                    {user.wallet_currency ? ` ${user.wallet_currency}` : ''}
                  </td>
                  <td>
                    <span className="table-badge">
                      {user.status === 'active' ? 'Активен' : 'Заблокирован'}
                    </span>
                  </td>
                  <td>{new Date(user.created_at).toLocaleString()}</td>
                  <td>{renderStatusAction(user)}</td>
                </tr>
              ))}
              {!usersQuery.isLoading && !usersQuery.data?.length && (
                <tr>
                  <td colSpan={8} className="muted">
                    Пользователи не найдены.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card" style={{ marginBottom: '1.5rem' }}>
        <div className="card-header">
          <div>
            <h2 className="card-title">Компании</h2>
            <p className="muted">Создание и список компаний для группировки запусков.</p>
          </div>
        </div>
        <form onSubmit={handleCompanySubmit} className="form-grid" style={{ gap: '1rem' }}>
          <div className="field">
            <label htmlFor="company-name">Название</label>
            <input
              id="company-name"
              type="text"
              value={companyName}
              onChange={(event) => setCompanyName(event.target.value)}
            />
          </div>
          <button type="submit" className="btn btn-primary" disabled={isSubmittingCompany}>
            Создать
          </button>
        </form>
        {companyMessage && (
          <p className={`alert ${companyState === 'error' ? 'alert-error' : 'alert-success'}`}>
            {companyMessage}
          </p>
        )}
        {companiesQuery.isLoading && <p className="muted">Загружаем компании...</p>}
        {companiesQuery.error && <p className="alert alert-error">Не удалось получить список компаний.</p>}
        <div className="table-container">
          <table className="table">
            <thead>
              <tr>
                <th>Название</th>
                <th>Создана</th>
              </tr>
            </thead>
            <tbody>
              {companyOptions.map((company) => (
                <tr key={company.id}>
                  <td>{company.name}</td>
                  <td>{company.created_at ? new Date(company.created_at).toLocaleString() : '—'}</td>
                </tr>
              ))}
              {!companiesQuery.isLoading && !companyOptions.length && (
                <tr>
                  <td colSpan={2} className="muted">
                    Компании не найдены.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card" style={{ marginBottom: '1.5rem' }}>
        <div className="card-header">
          <div>
            <h2 className="card-title">Запуски</h2>
            <p className="muted">Админ-управление очередью и зависшими запусками.</p>
          </div>
        </div>
        <form className="form-grid" style={{ gap: '1rem' }}>
          <div className="field">
            <label htmlFor="runs-status-filter">Статус</label>
            <select
              id="runs-status-filter"
              value={runsStatusFilter}
              onChange={(event) => setRunsStatusFilter(event.target.value)}
            >
              <option value="">Все</option>
              <option value="queued">В очереди</option>
              <option value="running">Выполняется</option>
              <option value="completed">Завершён</option>
              <option value="failed">Ошибка</option>
            </select>
          </div>
          <div className="field">
            <label htmlFor="runs-user-filter">Пользователь / Run</label>
            <input
              id="runs-user-filter"
              type="text"
              value={runsUserFilter}
              onChange={(event) => setRunsUserFilter(event.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="runs-limit">Лимит</label>
            <input
              id="runs-limit"
              type="number"
              min={1}
              max={500}
              value={runsLimit}
              onChange={(event) => setRunsLimit(event.target.value)}
            />
          </div>
          <button type="button" className="btn btn-primary" onClick={() => runsQuery.refetch()}>
            Обновить
          </button>
        </form>
        {runsQuery.isLoading && <p className="muted">Загружаем запуски...</p>}
        {runsQuery.error && <p className="alert alert-error">Не удалось получить список запусков.</p>}
        <div className="table-container">
          <table className="table">
            <thead>
              <tr>
                <th>Run</th>
                <th>Пользователь</th>
                <th>Статус</th>
                <th>Прогресс</th>
                <th>Создан</th>
                <th>Старт</th>
                <th>Обновление</th>
                <th>Действия</th>
              </tr>
            </thead>
            <tbody>
              {filteredRuns.map((run) => (
                <tr key={run.id}>
                  <td>{run.id.slice(0, 8)}…</td>
                  <td>{run.user_name || run.user_email || '—'}</td>
                  <td>
                    <span className={`status-pill ${run.status}`}>
                      {statusLabels[run.status] ?? run.status}
                    </span>
                  </td>
                  <td>{getRunProgress(run)}</td>
                  <td>{new Date(run.queued_at).toLocaleString()}</td>
                  <td>{run.started_at ? new Date(run.started_at).toLocaleString() : '—'}</td>
                  <td>{relativeTime(run.finished_at || run.started_at || run.queued_at)}</td>
                  <td>
                    <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                      <button
                        className="btn btn-secondary"
                        disabled={
                          runActionMutation.isPending ||
                          run.status === 'completed' ||
                          run.status === 'failed'
                        }
                        onClick={() => {
                          if (
                            window.confirm(
                              'Пометить запуск как ошибочный? Очередь продолжит работу.',
                            )
                          ) {
                            runActionMutation.mutate({ runId: run.id, action: 'fail' });
                          }
                        }}
                      >
                        Снять
                      </button>
                      <button
                        className="btn btn-secondary"
                        disabled={
                          runActionMutation.isPending ||
                          run.status === 'completed' ||
                          run.status === 'failed'
                        }
                        onClick={() => {
                          if (
                            window.confirm(
                              'Поставить запуск в очередь заново? Это подходит для зависших запусков.',
                            )
                          ) {
                            runActionMutation.mutate({ runId: run.id, action: 'requeue' });
                          }
                        }}
                      >
                        В очередь
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {!runsQuery.isLoading && !filteredRuns.length && (
                <tr>
                  <td colSpan={8} className="muted">
                    Запуски не найдены.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card" style={{ marginBottom: '1.5rem' }}>
        <div className="card-header">
          <div>
            <h2 className="card-title">Пополнение баланса</h2>
            <p className="muted">Доступно только администраторам. Email — обязательное поле.</p>
          </div>
        </div>
        <form onSubmit={handleAdjustSubmit} className="form-grid" style={{ gap: '1rem' }}>
          <div className="field">
            <label htmlFor="adjust-email">Email пользователя</label>
            <input
              id="adjust-email"
              type="email"
              required
              value={adjustEmail}
              onChange={(event) => setAdjustEmail(event.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="adjust-amount">Сумма (баллы)</label>
            <input
              id="adjust-amount"
              type="number"
              min={1}
              required
              value={adjustAmount}
              onChange={(event) => setAdjustAmount(event.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="adjust-reason">Комментарий</label>
            <input
              id="adjust-reason"
              type="text"
              value={adjustReason}
              onChange={(event) => setAdjustReason(event.target.value)}
            />
          </div>
          <button type="submit" className="btn btn-primary" disabled={isSubmittingAdjust}>
            {isSubmittingAdjust ? 'Выполняем...' : 'Пополнить'}
          </button>
          {adjustMessage && (
            <div className={`alert ${adjustState === 'success' ? 'alert-success' : 'alert-error'}`}>
              {adjustMessage}
            </div>
          )}
        </form>
      </div>

      <div className="card">
        <div className="card-header">
          <div>
            <h2 className="card-title">Логи доступа</h2>
            <p className="muted">Фильтрация по IP, пользователю и пути.</p>
          </div>
        </div>
        <form onSubmit={handleLogFilterSubmit} className="form-grid" style={{ gap: '1rem' }}>
          <div className="field">
            <label htmlFor="log-ip">IP</label>
            <input
              id="log-ip"
              type="text"
              value={logIpFilter}
              onChange={(event) => setLogIpFilter(event.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="log-path">Путь</label>
            <input
              id="log-path"
              type="text"
              value={logPathFilter}
              onChange={(event) => setLogPathFilter(event.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="log-user">User ID</label>
            <input
              id="log-user"
              type="text"
              value={logUserIdFilter}
              onChange={(event) => setLogUserIdFilter(event.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="log-limit">Лимит</label>
            <input
              id="log-limit"
              type="number"
              min={1}
              max={500}
              value={logLimit}
              onChange={(event) => setLogLimit(event.target.value)}
            />
          </div>
          <button type="submit" className="btn btn-primary">
            Обновить
          </button>
        </form>
        {accessLogsQuery.isLoading && <p className="muted">Загружаем логи...</p>}
        {accessLogsQuery.error && <p className="alert alert-error">Не удалось получить логи.</p>}
        <div className="table-container">
          <table className="table">
            <thead>
              <tr>
                <th>Дата</th>
                <th>IP</th>
                <th>Страна</th>
                <th>Пользователь</th>
                <th>Метод</th>
                <th>Путь</th>
                <th>Статус</th>
                <th>Блокировка</th>
              </tr>
            </thead>
            <tbody>
              {accessLogsQuery.data?.map(renderAccessRow)}
              {!accessLogsQuery.isLoading && !accessLogsQuery.data?.length && (
                <tr>
                  <td colSpan={8} className="muted">
                    Логи не найдены.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card" style={{ marginTop: '1.5rem' }}>
        <div className="card-header">
          <div>
            <h2 className="card-title">Логи Caddy</h2>
            <p className="muted">Обращения к доменам, проксируемым через Caddy.</p>
          </div>
        </div>
        <form onSubmit={handleCaddyFilterSubmit} className="form-grid" style={{ gap: '1rem' }}>
          <div className="field">
            <label htmlFor="caddy-host">Host</label>
            <input
              id="caddy-host"
              type="text"
              value={caddyHostFilter}
              onChange={(event) => setCaddyHostFilter(event.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="caddy-ip">IP</label>
            <input
              id="caddy-ip"
              type="text"
              value={caddyIpFilter}
              onChange={(event) => setCaddyIpFilter(event.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="caddy-path">Путь</label>
            <input
              id="caddy-path"
              type="text"
              value={caddyPathFilter}
              onChange={(event) => setCaddyPathFilter(event.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="caddy-status">Статус</label>
            <input
              id="caddy-status"
              type="number"
              min={100}
              max={599}
              value={caddyStatusFilter}
              onChange={(event) => setCaddyStatusFilter(event.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="caddy-limit">Лимит</label>
            <input
              id="caddy-limit"
              type="number"
              min={1}
              max={500}
              value={caddyLimit}
              onChange={(event) => setCaddyLimit(event.target.value)}
            />
          </div>
          <button type="submit" className="btn btn-primary">
            Обновить
          </button>
        </form>
        {caddyLogsQuery.isLoading && <p className="muted">Загружаем логи...</p>}
        {caddyLogsQuery.error && <p className="alert alert-error">Не удалось получить логи.</p>}
        <div className="table-container">
          <table className="table">
            <thead>
              <tr>
                <th>Дата</th>
                <th>Host</th>
                <th>IP</th>
                <th>Метод</th>
                <th>URI</th>
                <th>Статус</th>
                <th>User-Agent</th>
              </tr>
            </thead>
            <tbody>
              {caddyLogsQuery.data?.map(renderCaddyRow)}
              {!caddyLogsQuery.isLoading && !caddyLogsQuery.data?.length && (
                <tr>
                  <td colSpan={7} className="muted">
                    Логи не найдены.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

export default AdminPage;
