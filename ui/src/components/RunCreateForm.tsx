import { FormEvent, useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import type { AxiosError } from 'axios';
import {
  createReviewRun,
  CreateReviewRunPayload,
  ReviewRun,
} from '../services/api';

interface Props {
  onCreated?: (run: ReviewRun) => void;
  availablePoints?: number | null;
  runCost: number;
}

function RunCreateForm({ onCreated, availablePoints, runCost }: Props) {
  const [sourceCode, setSourceCode] = useState('');
  const [formError, setFormError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: (payload: CreateReviewRunPayload) => createReviewRun(payload),
    onSuccess: (run) => {
      setFormError(null);
      setSourceCode('');
      onCreated?.(run);
    },
  });

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    setFormError(null);

    if (!sourceCode.trim()) {
      setFormError('Добавьте текст кода');
      return;
    }

    const payload: CreateReviewRunPayload = {
      sources: [
        {
          name: 'UserCode',
          path: 'CommonModules/UserCode.bsl',
          module_type: 'CommonModule',
          content: sourceCode,
        },
      ],
    };

    mutation.mutate(payload, {
      onError: (error) => {
        const axiosError = error as AxiosError<{ detail?: string }>;
        const detail = axiosError?.response?.data?.detail;
        const message =
          detail && typeof detail === 'string'
            ? detail
            : error instanceof Error
            ? error.message
            : 'Не удалось создать запуск';
        setFormError(message);
      },
    });
  };

  const isBalanceInsufficient =
    typeof availablePoints === 'number' && availablePoints < runCost;

  return (
    <form onSubmit={handleSubmit} className="form-grid" style={{ gap: '1.25rem' }}>
      <div style={{ gridColumn: '1 / -1' }}>
        <h2 className="card-title" style={{ marginBottom: '0.35rem' }}>
          Создать новый запуск
        </h2>
        <p className="muted">
          Вставьте код 1С. Мы сохраним его и отправим в очередь анализатора.
        </p>
      </div>

      <p className="muted" style={{ gridColumn: '1 / -1' }}>
        Стоимость запуска: <strong>{runCost}</strong> баллов. Баланс:{' '}
        <strong>{availablePoints ?? '—'}</strong>.
      </p>

      <div className="field" style={{ gridColumn: '1 / -1' }}>
        <label htmlFor="source-code">Код</label>
        <textarea
          id="source-code"
          value={sourceCode}
          onChange={(event) => setSourceCode(event.target.value)}
          placeholder="Процедура Тест()..."
          style={{ minHeight: '24rem' }}
        />
      </div>

      {formError && <div className="alert alert-error" style={{ gridColumn: '1 / -1' }}>{formError}</div>}
      {mutation.isSuccess && !formError && (
        <div className="alert alert-success" style={{ gridColumn: '1 / -1' }}>
          Запуск создан. Ожидайте выполнения.
        </div>
      )}

      <button
        type="submit"
        className="btn btn-primary"
        style={{ gridColumn: '1 / -1' }}
        disabled={mutation.isPending || isBalanceInsufficient}
      >
        {mutation.isPending
          ? 'Создаем...'
          : isBalanceInsufficient
          ? 'Недостаточно баллов'
          : 'Создать запуск'}
      </button>
    </form>
  );
}

export default RunCreateForm;
