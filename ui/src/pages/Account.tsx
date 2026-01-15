import { useQuery } from '@tanstack/react-query';
import {
  fetchCurrentUser,
  fetchWallet,
  fetchWalletTransactions,
} from '../services/api';

function AccountPage() {
  const userQuery = useQuery({ queryKey: ['me'], queryFn: fetchCurrentUser });
  const walletQuery = useQuery({ queryKey: ['wallet'], queryFn: fetchWallet });
  const txQuery = useQuery({
    queryKey: ['wallet-transactions'],
    queryFn: fetchWalletTransactions,
    enabled: true,
  });

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

    </div>
  );
}

export default AccountPage;
