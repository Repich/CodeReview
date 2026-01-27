import { FormEvent, useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import type { AxiosError } from 'axios';
import {
  createReviewRun,
  CreateReviewRunPayload,
  ReviewRun,
  SourceUnitPayload,
} from '../services/api';

interface Props {
  onCreated?: (run: ReviewRun) => void;
  availablePoints?: number | null;
  runCost: number;
}

const defaultModule: SourceUnitPayload = {
  name: 'DangerousModule',
  path: 'CommonModules/DangerousModule.bsl',
  module_type: 'CommonModule',
  content: '',
};

const MODULE_TYPE_OPTIONS = [
  { value: 'CommonModule', label: 'Общий модуль' },
  { value: 'FormModule', label: 'Модуль формы' },
  { value: 'ObjectModule', label: 'Модуль объекта' },
  { value: 'ManagerModule', label: 'Модуль менеджера' },
  { value: 'DocumentModule', label: 'Модуль документа' },
  { value: 'RecordSetModule', label: 'Модуль набора записей' },
  { value: 'CommandModule', label: 'Модуль команд' },
  { value: 'SessionModule', label: 'Модуль сеанса' },
  { value: 'HTTPServiceModule', label: 'Модуль HTTP-сервиса' },
  { value: 'Other', label: 'Другое' },
];

function RunCreateForm({ onCreated, availablePoints, runCost }: Props) {
  const [projectId, setProjectId] = useState('demo');
  const [externalRef, setExternalRef] = useState('');
  const [modules, setModules] = useState<SourceUnitPayload[]>([{ ...defaultModule }]);
  const [formError, setFormError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: (payload: CreateReviewRunPayload) => createReviewRun(payload),
    onSuccess: (run) => {
      setFormError(null);
      setModules([{ ...defaultModule }]);
      setExternalRef('');
      onCreated?.(run);
    },
  });

  const updateModule = (index: number, patch: Partial<SourceUnitPayload>) => {
    setModules((prev) =>
      prev.map((module, idx) => (idx === index ? { ...module, ...patch } : module))
    );
  };

  const addModule = () => setModules((prev) => [...prev, { ...defaultModule }]);
  const removeModule = (index: number) => setModules((prev) => prev.filter((_, idx) => idx !== index));

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    setFormError(null);

    if (modules.length === 0) {
      setFormError('Добавьте хотя бы один модуль');
      return;
    }

    if (modules.some((module) => !module.path.trim() || !module.name.trim() || !module.content.trim())) {
      setFormError('Заполните путь, имя и текст для каждого модуля');
      return;
    }

    const payload: CreateReviewRunPayload = {
      project_id: projectId.trim() || undefined,
      external_ref: externalRef.trim() || undefined,
      sources: modules.map((module) => ({
        ...module,
        path: module.path.trim(),
        name: module.name.trim(),
        module_type: module.module_type.trim() || 'CommonModule',
        content: module.content,
      })),
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
          Загрузите один или несколько модулей 1С. Мы сохраним их и отправим в очередь
          анализатора.
        </p>
      </div>

      <div className="field">
        <label htmlFor="project">Project ID</label>
        <input
          id="project"
          value={projectId}
          onChange={(event) => setProjectId(event.target.value)}
          placeholder="demo"
        />
      </div>
      <div className="field">
        <label htmlFor="external-ref">Внешняя ссылка</label>
        <input
          id="external-ref"
          value={externalRef}
          onChange={(event) => setExternalRef(event.target.value)}
          placeholder="MR-123"
        />
      </div>
      <p className="muted" style={{ gridColumn: '1 / -1' }}>
        Стоимость запуска: <strong>{runCost}</strong> баллов. Баланс:{' '}
        <strong>{availablePoints ?? '—'}</strong>.
      </p>

      <div style={{ gridColumn: '1 / -1', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3 style={{ margin: 0 }}>Исходники ({modules.length})</h3>
        <button type="button" className="btn btn-secondary" onClick={addModule} disabled={mutation.isPending}>
          Добавить модуль
        </button>
      </div>

      <div style={{ gridColumn: '1 / -1', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        {modules.map((module, index) => (
          <div key={index} className="card" style={{ padding: '1rem', borderColor: 'var(--border)' }}>
            <div className="card-header">
              <strong>Модуль #{index + 1}</strong>
              {modules.length > 1 && (
                <button
                  type="button"
                  className="btn btn-ghost"
                  onClick={() => removeModule(index)}
                  disabled={mutation.isPending}
                >
                  Удалить
                </button>
              )}
            </div>
            <div className="module-grid">
              <div className="field">
                <label>Имя</label>
                <input value={module.name} onChange={(event) => updateModule(index, { name: event.target.value })} />
              </div>
              <div className="field">
                <label>Путь</label>
                <input value={module.path} onChange={(event) => updateModule(index, { path: event.target.value })} />
              </div>
              <div className="field">
                <label>Тип модуля</label>
                <select
                  value={module.module_type}
                  onChange={(event) => updateModule(index, { module_type: event.target.value })}
                >
                  {MODULE_TYPE_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <div className="field">
              <label>Содержимое</label>
              <textarea
                value={module.content}
                onChange={(event) => updateModule(index, { content: event.target.value })}
                placeholder="Процедура Тест()..."
              />
            </div>
          </div>
        ))}
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
