import { useMemo, useState, useEffect } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { fetchRuns, ReviewRun, fetchWallet, deleteReviewRun, fetchCurrentUser } from '../services/api';
import RunCreateForm from '../components/RunCreateForm';

const statusLabels: Record<string, string> = {
  queued: 'В очереди',
  running: 'Выполняется',
  completed: 'Завершён',
  failed: 'Ошибка',
};

const RUN_COST_POINTS = Number(import.meta.env.VITE_RUN_COST_POINTS || 10);

const formatDuration = (ms: number) => {
  if (ms <= 0) {
    return '0 с';
  }
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

function RunListPage() {
  const { data, isLoading, error, refetch, isFetching } = useQuery<ReviewRun[]>({
    queryKey: ['runs'],
    queryFn: () => fetchRuns(),
    refetchInterval: (query) => {
      const runs = query.state.data;
      const hasActive = runs?.some((run: ReviewRun) => run.status === 'queued' || run.status === 'running');
      return hasActive ? 5000 : false;
    },
    refetchOnWindowFocus: true,
  });

  const walletQuery = useQuery({
    queryKey: ['wallet'],
    queryFn: fetchWallet,
  });
  const currentUserQuery = useQuery({
    queryKey: ['current-user'],
    queryFn: fetchCurrentUser,
  });

  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);
  const deleteRunMutation = useMutation({
    mutationFn: (runId: string) => deleteReviewRun(runId),
    onMutate: (runId) => {
      setPendingDeleteId(runId);
    },
    onSuccess: () => {
      refetch();
    },
    onSettled: () => {
      setPendingDeleteId(null);
    },
  });

  const latestRuns = useMemo(() => data ?? [], [data]);
  useEffect(() => {
    const hasActive = latestRuns.some(
      (run) => run.status === 'queued' || run.status === 'running',
    );
    if (!hasActive) {
      return undefined;
    }
    const timer = window.setInterval(() => setNowTs(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [latestRuns]);
  const [nowTs, setNowTs] = useState(() => Date.now());

  if (isLoading) {
    return <p>Загружаем запуски...</p>;
  }

  if (error) {
    return (
      <div className="card">
        <p>Не удалось загрузить список запусков.</p>
        <button className="btn btn-primary" onClick={() => refetch()}>
          Повторить
        </button>
      </div>
    );
  }

  const getRunProgress = (run: ReviewRun) => {
    if (run.status === 'queued') {
      const base = run.queued_at ? new Date(run.queued_at).getTime() : null;
      if (base) {
        const diff = nowTs - base;
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
        const diff = nowTs - base;
        if (diff > 0) {
          return `Выполняется ${formatDuration(diff)}`;
        }
      }
      return 'Выполняется';
    }
    return '—';
  };

  const balance = walletQuery.data?.balance ?? '—';
  const currency = walletQuery.data?.currency ?? 'points';
  const isAdmin = (currentUserQuery.data?.role || '').toLowerCase() === 'admin';
  const showOwner = isAdmin || Boolean(currentUserQuery.data?.company_id);
  const currentUserId = currentUserQuery.data?.id;

  return (
    <div>
      <div className="page-heading">
        <div>
          <p className="muted">Аналитика</p>
          <h1>Запуски код-ревью</h1>
        </div>
        <div className="balance-chip">Баланс: {balance} {currency}</div>
      </div>

      <div className="card" style={{ marginBottom: '1.5rem' }}>
        <RunCreateForm
          onCreated={() => {
            refetch();
            walletQuery.refetch();
          }}
          availablePoints={walletQuery.data?.balance ?? null}
          runCost={RUN_COST_POINTS}
        />
      </div>

      <div className="card">
        <div className="card-header">
          <h2 className="card-title">История запусков</h2>
          {isFetching && <span className="muted">Обновляем…</span>}
        </div>
        <div className="table-container">
          <table className="table">
            <thead>
              <tr>
                <th>Run</th>
                {showOwner && <th>Пользователь</th>}
                <th>Статус</th>
                <th>Прогресс</th>
                <th>Создан</th>
                <th>Старт</th>
                <th>Обновление</th>
                <th>Действия</th>
              </tr>
            </thead>
            <tbody>
              {latestRuns.map((run) => {
                const canManageRun =
                  isAdmin || (currentUserId && run.user_id && run.user_id === currentUserId);
                return (
                <tr key={run.id}>
                  <td>
                    <Link to={`/runs/${run.id}`}>{run.id.slice(0, 8)}…</Link>
                  </td>
                  {showOwner && (
                    <td>{run.user_name || run.user_email || '—'}</td>
                  )}
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
                    <button
                      className="btn btn-secondary"
                      disabled={
                        run.status === 'running' ||
                        !canManageRun ||
                        (deleteRunMutation.isPending && pendingDeleteId === run.id)
                      }
                      onClick={() => {
                        if (run.status === 'running') {
                          return;
                        }
                        if (!canManageRun) {
                          return;
                        }
                        if (
                          window.confirm(
                            'Вы действительно хотите удалить этот запуск? Данные будет невозможно восстановить.',
                          )
                        ) {
                          deleteRunMutation.mutate(run.id);
                        }
                      }}
                    >
                      Удалить
                    </button>
                  </td>
                </tr>
                );
              })}
              {!latestRuns.length && (
                <tr>
                  <td colSpan={showOwner ? 8 : 7} className="muted">
                    Запусков пока нет.
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

export default RunListPage;
