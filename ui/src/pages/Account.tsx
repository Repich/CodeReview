import { FormEvent, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  fetchCurrentUser,
  fetchWallet,
  fetchWalletTransactions,
  adjustWalletBalance,
} from '../services/api';

function AccountPage() {
  const userQuery = useQuery({ queryKey: ['me'], queryFn: fetchCurrentUser });
  const walletQuery = useQuery({ queryKey: ['wallet'], queryFn: fetchWallet });
  const txQuery = useQuery({
    queryKey: ['wallet-transactions'],
    queryFn: fetchWalletTransactions,
    enabled: true,
  });
  const isAdmin = (userQuery.data?.role || '').toLowerCase() === 'admin';
  const [adjustEmail, setAdjustEmail] = useState('');
  const [adjustAmount, setAdjustAmount] = useState('0');
  const [adjustReason, setAdjustReason] = useState('Admin top-up');
  const [adjustMessage, setAdjustMessage] = useState<string | null>(null);
  const [adjustState, setAdjustState] = useState<'idle' | 'success' | 'error'>('idle');
  const [isSubmittingAdjust, setSubmittingAdjust] = useState(false);

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
      await Promise.all([walletQuery.refetch(), txQuery.refetch()]);
    } catch (err) {
      console.error(err);
      setAdjustMessage('Не удалось выполнить операцию.');
      setAdjustState('error');
    } finally {
      setSubmittingAdjust(false);
    }
  };

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

      {isAdmin && (
        <div className="card">
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
      )}
    </div>
  );
}

export default AccountPage;
