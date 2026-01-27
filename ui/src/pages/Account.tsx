import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  fetchCurrentUser,
  fetchChangelog,
  fetchWallet,
  fetchWalletTransactions,
  updateUserSettings,
} from '../services/api';

function AccountPage() {
  const queryClient = useQueryClient();
  const userQuery = useQuery({ queryKey: ['me'], queryFn: fetchCurrentUser });
  const walletQuery = useQuery({ queryKey: ['wallet'], queryFn: fetchWallet });
  const txQuery = useQuery({
    queryKey: ['wallet-transactions'],
    queryFn: fetchWalletTransactions,
    enabled: true,
  });
  const changelogQuery = useQuery({
    queryKey: ['changelog'],
    queryFn: fetchChangelog,
  });
  const [findingsView, setFindingsView] = useState<'separate' | 'combined'>('separate');
  const [disablePatterns, setDisablePatterns] = useState(false);
  const settingsMutation = useMutation({
    mutationFn: (payload: import('../services/api').UserSettingsUpdate) =>
      updateUserSettings(payload),
    onSuccess: (data) => {
      queryClient.setQueryData(['me'], data);
    },
  });

  useEffect(() => {
    const stored = userQuery.data?.settings?.findings_view;
    if (stored) {
      setFindingsView(stored);
    }
    const storedDisable = userQuery.data?.settings?.disable_patterns;
    if (typeof storedDisable === 'boolean') {
      setDisablePatterns(storedDisable);
    }
  }, [userQuery.data?.settings?.findings_view, userQuery.data?.settings?.disable_patterns]);

  if (userQuery.isLoading || walletQuery.isLoading) {
    return <p>Загружаем профиль...</p>;
  }

  if (userQuery.error || walletQuery.error) {
    return <p>Не удалось загрузить данные профиля.</p>;
  }

  return (
    <div>
      <div className="page-heading">
        <div>
          <p className="muted">Пользователь</p>
          <h1>Личный кабинет</h1>
        </div>
        <div className="balance-chip">
          Баланс: {walletQuery.data?.balance ?? 0} {walletQuery.data?.currency}
        </div>
      </div>

      <div className="section-grid" style={{ marginBottom: '1.5rem' }}>
        <div className="card">
          <h2 className="card-title">Профиль</h2>
          <p className="muted" style={{ marginBottom: '0.5rem' }}>
            Основные данные учётной записи.
          </p>
          <dl style={{ margin: 0, display: 'grid', gap: '0.5rem' }}>
            <div>
              <dt className="muted">Email</dt>
              <dd>{userQuery.data?.email}</dd>
            </div>
            <div>
              <dt className="muted">Имя</dt>
              <dd>{userQuery.data?.name || '—'}</dd>
            </div>
            <div>
              <dt className="muted">Статус</dt>
              <dd>{userQuery.data?.status}</dd>
            </div>
            <div>
              <dt className="muted">Роль</dt>
              <dd>{userQuery.data?.role}</dd>
            </div>
            <div>
              <dt className="muted">Компания</dt>
              <dd>{userQuery.data?.company_name || '—'}</dd>
            </div>
          </dl>
        </div>

        <div className="card">
          <h2 className="card-title">Баланс</h2>
          <p className="muted">Стоимость запуска: 10 баллов.</p>
          <div style={{ fontSize: '2rem', fontWeight: 700 }}>
            {walletQuery.data?.balance ?? 0}{' '}
            <span style={{ fontSize: '1rem', color: 'var(--muted)' }}>
              {walletQuery.data?.currency}
            </span>
          </div>
          <p className="muted">Пополняйте баланс перед запуском анализа.</p>
        </div>

        <div className="card">
          <h2 className="card-title">Настройки</h2>
          <p className="muted" style={{ marginBottom: '0.75rem' }}>
            Персонализируйте отображение нарушений.
          </p>
          <div className="segmented-control" role="group" aria-label="Отображение нарушений">
            <button
              type="button"
              className={findingsView === 'separate' ? 'active' : ''}
              onClick={() => {
                setFindingsView('separate');
                settingsMutation.mutate({ findings_view: 'separate' });
              }}
              disabled={settingsMutation.isPending}
            >
              Раздельно
            </button>
            <button
              type="button"
              className={findingsView === 'combined' ? 'active' : ''}
              onClick={() => {
                setFindingsView('combined');
                settingsMutation.mutate({ findings_view: 'combined' });
              }}
              disabled={settingsMutation.isPending}
            >
              Вместе
            </button>
          </div>
          <div style={{ marginTop: '1rem' }}>
            <p className="muted" style={{ marginBottom: '0.5rem' }}>
              Паттерны (LLM)
            </p>
            <div className="segmented-control" role="group" aria-label="Проверка паттернов">
              <button
                type="button"
                className={!disablePatterns ? 'active' : ''}
                onClick={() => {
                  setDisablePatterns(false);
                  settingsMutation.mutate({ disable_patterns: false });
                }}
                disabled={settingsMutation.isPending}
              >
                Включена
              </button>
              <button
                type="button"
                className={disablePatterns ? 'active' : ''}
                onClick={() => {
                  setDisablePatterns(true);
                  settingsMutation.mutate({ disable_patterns: true });
                }}
                disabled={settingsMutation.isPending}
              >
                Выключена
              </button>
            </div>
          </div>
          <p className="muted" style={{ marginTop: '0.75rem' }}>
            Раздельно — отдельная вкладка LLM. Вместе — единый список слева от кода.
          </p>
          {settingsMutation.isError && (
            <p className="alert alert-error" style={{ marginTop: '0.75rem' }}>
              Не удалось сохранить настройки.
            </p>
          )}
        </div>
      </div>

      <div className="card" style={{ marginBottom: '1.5rem' }}>
        <div className="card-header">
          <h2 className="card-title">История транзакций</h2>
        </div>
        {txQuery.isLoading && <p className="muted">Загружаем историю...</p>}
        {txQuery.error && <p className="alert alert-error">Не удалось получить историю.</p>}
        <div className="table-container">
          <table className="table">
            <thead>
              <tr>
                <th>Дата</th>
                <th>Тип</th>
                <th>Источник</th>
                <th>Сумма</th>
              </tr>
            </thead>
            <tbody>
              {txQuery.data?.map((tx) => (
                <tr key={tx.id}>
                  <td>{new Date(tx.created_at).toLocaleString()}</td>
                  <td>
                    <span className="table-badge">
                      {tx.txn_type === 'debit' ? 'Списание' : 'Начисление'}
                    </span>
                  </td>
                  <td>{tx.source}</td>
                  <td style={{ color: tx.txn_type === 'debit' ? 'var(--danger)' : 'var(--success)' }}>
                    {tx.txn_type === 'debit' ? '-' : '+'}
                    {tx.amount}
                  </td>
                </tr>
              ))}
              {!txQuery.isLoading && !txQuery.data?.length && (
                <tr>
                  <td colSpan={4} className="muted">
                    История пуста.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <h2 className="card-title">Что нового</h2>
        </div>
        {changelogQuery.isLoading && <p className="muted">Загружаем обновления...</p>}
        {changelogQuery.error && (
          <p className="alert alert-error">Не удалось загрузить changelog.</p>
        )}
        {changelogQuery.data && (
          <>
            <p className="muted">
              Обновлено: {new Date(changelogQuery.data.updated_at).toLocaleString()}
            </p>
            <pre
              style={{
                whiteSpace: 'pre-wrap',
                background: 'var(--surface)',
                padding: '1rem',
                borderRadius: '0.75rem',
                maxHeight: '320px',
                overflow: 'auto',
              }}
            >
              {changelogQuery.data.content}
            </pre>
          </>
        )}
      </div>

    </div>
  );
}

export default AccountPage;
