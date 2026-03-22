import { FormEvent, useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { useMutation, useQuery } from '@tanstack/react-query';
import {
  createModelLabSession,
  discoverModelLabModels,
  evaluateModelLabSession,
  fetchCurrentUser,
  fetchModelLabConfig,
  fetchModelLabSession,
  fetchModelLabSessions,
  ModelLabCreatePayload,
  ModelLabSession,
} from '../services/api';

const DEFAULT_DEEPSEEK_MODEL = 'deepseek-chat';
const DEFAULT_OPENAI_MODEL = 'gpt-5-mini';

function parseModelIds(raw: string): string[] {
  const parts = raw
    .split(/[\n,;]/g)
    .map((item) => item.trim())
    .filter(Boolean);
  return Array.from(new Set(parts));
}

function shortId(value: string) {
  return value.length > 8 ? `${value.slice(0, 8)}…` : value;
}

function extractErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === 'string' && detail.trim()) {
      return detail;
    }
    if (Array.isArray(detail)) {
      return detail
        .map((item) => {
          if (typeof item === 'string') return item;
          if (item && typeof item.msg === 'string') return item.msg;
          return '';
        })
        .filter(Boolean)
        .join('; ');
    }
    return error.message;
  }
  if (error instanceof Error) return error.message;
  return 'Неизвестная ошибка';
}

function ModelLabPage() {
  const userQuery = useQuery({ queryKey: ['model-lab-me'], queryFn: fetchCurrentUser });
  const role = (userQuery.data?.role || '').toLowerCase();
  const isAdmin = role === 'admin';

  const configQuery = useQuery({
    queryKey: ['model-lab-config'],
    queryFn: fetchModelLabConfig,
    enabled: isAdmin,
    retry: false,
  });

  const modelLabEnabled = Boolean(configQuery.data?.enabled);

  const sessionsQuery = useQuery({
    queryKey: ['model-lab-sessions'],
    queryFn: () => fetchModelLabSessions(100),
    enabled: isAdmin && modelLabEnabled,
    refetchInterval: (query) => {
      const rows = query.state.data;
      const hasActive = rows?.some((row) =>
        ['queued', 'running', 'ready_for_evaluation', 'evaluating'].includes((row.status || '').toLowerCase()),
      );
      return hasActive ? 5000 : false;
    },
  });

  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);

  const detailQuery = useQuery({
    queryKey: ['model-lab-session', selectedSessionId],
    queryFn: () => fetchModelLabSession(selectedSessionId as string),
    enabled: isAdmin && modelLabEnabled && Boolean(selectedSessionId),
    refetchInterval: (query) => {
      const status = String(query.state.data?.session?.status || '').toLowerCase();
      return ['queued', 'running', 'ready_for_evaluation', 'evaluating'].includes(status) ? 5000 : false;
    },
  });

  useEffect(() => {
    const rows = sessionsQuery.data || [];
    if (!rows.length) {
      setSelectedSessionId(null);
      return;
    }
    if (!selectedSessionId) {
      setSelectedSessionId(rows[0].id);
      return;
    }
    const exists = rows.some((row) => row.id === selectedSessionId);
    if (!exists) {
      setSelectedSessionId(rows[0].id);
    }
  }, [sessionsQuery.data, selectedSessionId]);

  const [title, setTitle] = useState('');
  const [apiBase, setApiBase] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [sampleSize, setSampleSize] = useState(10);
  const [includeOpenWorld, setIncludeOpenWorld] = useState(false);
  const [useAllNorms, setUseAllNorms] = useState(true);
  const [disablePatterns, setDisablePatterns] = useState(true);

  const [deepseekBaselineEnabled, setDeepseekBaselineEnabled] = useState(true);
  const [deepseekBaselineModel, setDeepseekBaselineModel] = useState(DEFAULT_DEEPSEEK_MODEL);
  const [openaiBaselineEnabled, setOpenaiBaselineEnabled] = useState(true);
  const [openaiBaselineModel, setOpenaiBaselineModel] = useState(DEFAULT_OPENAI_MODEL);

  const [deepseekExpertEnabled, setDeepseekExpertEnabled] = useState(true);
  const [deepseekExpertModel, setDeepseekExpertModel] = useState(DEFAULT_DEEPSEEK_MODEL);
  const [openaiExpertEnabled, setOpenaiExpertEnabled] = useState(true);
  const [openaiExpertModel, setOpenaiExpertModel] = useState(DEFAULT_OPENAI_MODEL);

  const [discoveredModels, setDiscoveredModels] = useState<string[]>([]);
  const [selectedInternalModels, setSelectedInternalModels] = useState<string[]>([]);
  const [manualInternalModelsText, setManualInternalModelsText] = useState('');
  const [feedbackMessage, setFeedbackMessage] = useState<string | null>(null);
  const [feedbackState, setFeedbackState] = useState<'idle' | 'success' | 'error'>('idle');

  useEffect(() => {
    if (configQuery.data?.default_sample_size) {
      setSampleSize(configQuery.data.default_sample_size);
    }
  }, [configQuery.data?.default_sample_size]);

  const discoverMutation = useMutation({
    mutationFn: () => discoverModelLabModels({ api_base: apiBase.trim(), api_key: apiKey.trim() }),
    onSuccess: (data) => {
      const models = (data.models || []).filter(Boolean);
      setDiscoveredModels(models);
      setSelectedInternalModels((prev) => {
        const prevSet = new Set(prev);
        const next = models.filter((item) => prevSet.has(item));
        if (next.length) {
          return next;
        }
        return models.slice(0, Math.min(models.length, 3));
      });
      setFeedbackState('success');
      setFeedbackMessage(`Найдено моделей: ${models.length}`);
    },
    onError: (error) => {
      setFeedbackState('error');
      setFeedbackMessage(extractErrorMessage(error));
    },
  });

  const createMutation = useMutation({
    mutationFn: (payload: ModelLabCreatePayload) => createModelLabSession(payload),
    onSuccess: (session: ModelLabSession) => {
      setFeedbackState('success');
      setFeedbackMessage(`Сессия создана: ${session.id}`);
      sessionsQuery.refetch();
      setSelectedSessionId(session.id);
    },
    onError: (error) => {
      setFeedbackState('error');
      setFeedbackMessage(extractErrorMessage(error));
    },
  });

  const evaluateMutation = useMutation({
    mutationFn: (sessionId: string) => evaluateModelLabSession(sessionId),
    onSuccess: () => {
      setFeedbackState('success');
      setFeedbackMessage('Оценка завершена.');
      sessionsQuery.refetch();
      detailQuery.refetch();
    },
    onError: (error) => {
      setFeedbackState('error');
      setFeedbackMessage(extractErrorMessage(error));
    },
  });

  const selectedSessionStatus = String(detailQuery.data?.session?.status || '').toLowerCase();
  const canEvaluate = ['ready_for_evaluation', 'evaluated'].includes(selectedSessionStatus);

  const manualInternalModels = useMemo(
    () => parseModelIds(manualInternalModelsText),
    [manualInternalModelsText],
  );
  const effectiveInternalModels = useMemo(
    () => Array.from(new Set([...selectedInternalModels, ...manualInternalModels])),
    [selectedInternalModels, manualInternalModels],
  );
  const activeInternalCount = effectiveInternalModels.length;

  const limitsText = useMemo(() => {
    if (!configQuery.data) return null;
    return [
      `Внутренние модели на сессию: до ${configQuery.data.max_models}.`,
      `Платные baseline-модели (DeepSeek/OpenAI): до ${configQuery.data.max_paid_target_models}.`,
      `Платные baseline-прогоны: до ${configQuery.data.max_paid_target_runs}.`,
      `Экспертные модели: до ${configQuery.data.max_expert_models}.`,
      `Лимит экспертных вызовов: до ${configQuery.data.max_expert_calls}.`,
    ];
  }, [configQuery.data]);

  const onSubmitCreate = (event: FormEvent) => {
    event.preventDefault();
    setFeedbackMessage(null);
    setFeedbackState('idle');

    if (!apiBase.trim() || !apiKey.trim()) {
      setFeedbackState('error');
      setFeedbackMessage('Заполните API base и API key.');
      return;
    }
    if (!effectiveInternalModels.length) {
      setFeedbackState('error');
      setFeedbackMessage('Выберите хотя бы одну внутреннюю модель.');
      return;
    }

    const baseline_models: Array<{ provider: 'deepseek' | 'openai'; model: string }> = [];
    if (deepseekBaselineEnabled && deepseekBaselineModel.trim()) {
      baseline_models.push({ provider: 'deepseek', model: deepseekBaselineModel.trim() });
    }
    if (openaiBaselineEnabled && openaiBaselineModel.trim()) {
      baseline_models.push({ provider: 'openai', model: openaiBaselineModel.trim() });
    }

    const expert_models: Array<{ provider: 'deepseek' | 'openai'; model: string }> = [];
    if (deepseekExpertEnabled && deepseekExpertModel.trim()) {
      expert_models.push({ provider: 'deepseek', model: deepseekExpertModel.trim() });
    }
    if (openaiExpertEnabled && openaiExpertModel.trim()) {
      expert_models.push({ provider: 'openai', model: openaiExpertModel.trim() });
    }

    if (!expert_models.length) {
      setFeedbackState('error');
      setFeedbackMessage('Выберите хотя бы одну экспертную модель.');
      return;
    }

    const payload: ModelLabCreatePayload = {
      title: title.trim() || undefined,
      api_base: apiBase.trim(),
      api_key: apiKey.trim(),
      internal_models: effectiveInternalModels,
      baseline_models,
      expert_models,
      sample_size: sampleSize,
      include_open_world: includeOpenWorld,
      use_all_norms: useAllNorms,
      disable_patterns: disablePatterns,
    };
    createMutation.mutate(payload);
  };

  if (userQuery.isLoading) {
    return <p>Загружаем профиль…</p>;
  }

  if (!isAdmin) {
    return (
      <div className="card">
        <h2 className="card-title">Model Lab</h2>
        <p className="muted">Раздел доступен только администратору.</p>
      </div>
    );
  }

  if (configQuery.isLoading) {
    return <p>Загружаем настройки Model Lab…</p>;
  }

  if (configQuery.error) {
    return (
      <div className="card">
        <h2 className="card-title">Model Lab</h2>
        <p className="alert alert-error">Не удалось загрузить конфигурацию Model Lab.</p>
      </div>
    );
  }

  if (!modelLabEnabled) {
    return (
      <div className="card">
        <h2 className="card-title">Model Lab отключен</h2>
        <p className="muted">Включите `CODEREVIEW_MODEL_LAB_ENABLED=true` и перезапустите backend/worker.</p>
      </div>
    );
  }

  return (
    <div>
      <div className="page-heading">
        <div>
          <p className="muted">Администрирование</p>
          <h1>Model Lab</h1>
          <p className="muted">Сравнение внутренних моделей по историческим запускам code-review.</p>
        </div>
      </div>

      <section className="card" style={{ marginBottom: '1rem' }}>
        <div className="card-header">
          <h2 className="card-title">Новая сессия</h2>
        </div>

        {limitsText && (
          <div style={{ marginBottom: '0.75rem' }}>
            {limitsText.map((line) => (
              <div key={line} className="muted">
                {line}
              </div>
            ))}
          </div>
        )}

        <form className="form-grid" onSubmit={onSubmitCreate}>
          <div className="field">
            <label htmlFor="model-lab-title">Название (опционально)</label>
            <input
              id="model-lab-title"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="Например: Internal benchmark #1"
            />
          </div>

          <div className="field">
            <label htmlFor="model-lab-sample">Количество запусков</label>
            <input
              id="model-lab-sample"
              type="number"
              min={1}
              max={configQuery.data?.max_sample_size || 20}
              value={sampleSize}
              onChange={(event) => setSampleSize(Number(event.target.value) || 1)}
            />
          </div>

          <div className="field" style={{ gridColumn: '1 / -1' }}>
            <label htmlFor="model-lab-api-base">OpenAI-compatible API base</label>
            <input
              id="model-lab-api-base"
              value={apiBase}
              onChange={(event) => setApiBase(event.target.value)}
              placeholder="https://internal-llm.example.local"
            />
          </div>

          <div className="field" style={{ gridColumn: '1 / -1' }}>
            <label htmlFor="model-lab-api-key">API key (в памяти, в БД не сохраняется)</label>
            <input
              id="model-lab-api-key"
              type="password"
              autoComplete="new-password"
              value={apiKey}
              onChange={(event) => setApiKey(event.target.value)}
              placeholder="sk-..."
            />
          </div>

          <div style={{ gridColumn: '1 / -1', display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
            <button
              className="btn btn-secondary"
              type="button"
              onClick={() => discoverMutation.mutate()}
              disabled={discoverMutation.isPending || !apiBase.trim() || !apiKey.trim()}
            >
              {discoverMutation.isPending ? 'Запрос...' : 'Получить список внутренних моделей'}
            </button>
            <button
              className="btn btn-secondary"
              type="button"
              onClick={() => setSelectedInternalModels(discoveredModels)}
              disabled={!discoveredModels.length}
            >
              Выбрать все
            </button>
            <button
              className="btn btn-secondary"
              type="button"
              onClick={() => setSelectedInternalModels([])}
              disabled={!selectedInternalModels.length}
            >
              Очистить
            </button>
            <span className="muted">Выбрано внутренних моделей: {activeInternalCount}</span>
          </div>

          <div className="field" style={{ gridColumn: '1 / -1' }}>
            <label htmlFor="model-lab-manual-models">Внутренние модели (вручную)</label>
            <textarea
              id="model-lab-manual-models"
              rows={3}
              value={manualInternalModelsText}
              onChange={(event) => setManualInternalModelsText(event.target.value)}
              placeholder="llm-medium-moe-instruct, llm-small-instruct"
            />
            <p className="muted" style={{ marginTop: '0.35rem' }}>
              Укажите model id через запятую, `;` или с новой строки. Полезно, если discover недоступен.
            </p>
          </div>

          {discoveredModels.length > 0 && (
            <div className="field" style={{ gridColumn: '1 / -1' }}>
              <label>Внутренние модели</label>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '0.35rem' }}>
                {discoveredModels.map((model) => {
                  const checked = selectedInternalModels.includes(model);
                  return (
                    <label key={model} style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={(event) => {
                          setSelectedInternalModels((prev) => {
                            if (event.target.checked) {
                              return [...prev, model];
                            }
                            return prev.filter((item) => item !== model);
                          });
                        }}
                      />
                      <span>{model}</span>
                    </label>
                  );
                })}
              </div>
            </div>
          )}

          <div className="field">
            <label>Baseline DeepSeek</label>
            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
              <input
                type="checkbox"
                checked={deepseekBaselineEnabled}
                onChange={(event) => setDeepseekBaselineEnabled(event.target.checked)}
              />
              <input
                value={deepseekBaselineModel}
                onChange={(event) => setDeepseekBaselineModel(event.target.value)}
                disabled={!deepseekBaselineEnabled}
              />
            </div>
          </div>

          <div className="field">
            <label>Baseline OpenAI</label>
            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
              <input
                type="checkbox"
                checked={openaiBaselineEnabled}
                onChange={(event) => setOpenaiBaselineEnabled(event.target.checked)}
              />
              <input
                value={openaiBaselineModel}
                onChange={(event) => setOpenaiBaselineModel(event.target.value)}
                disabled={!openaiBaselineEnabled}
              />
            </div>
          </div>

          <div className="field">
            <label>Эксперт DeepSeek</label>
            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
              <input
                type="checkbox"
                checked={deepseekExpertEnabled}
                onChange={(event) => setDeepseekExpertEnabled(event.target.checked)}
              />
              <input
                value={deepseekExpertModel}
                onChange={(event) => setDeepseekExpertModel(event.target.value)}
                disabled={!deepseekExpertEnabled}
              />
            </div>
          </div>

          <div className="field">
            <label>Эксперт OpenAI</label>
            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
              <input
                type="checkbox"
                checked={openaiExpertEnabled}
                onChange={(event) => setOpenaiExpertEnabled(event.target.checked)}
              />
              <input
                value={openaiExpertModel}
                onChange={(event) => setOpenaiExpertModel(event.target.value)}
                disabled={!openaiExpertEnabled}
              />
            </div>
          </div>

          <div className="field" style={{ gridColumn: '1 / -1' }}>
            <label>Опции пайплайна</label>
            <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
              <label style={{ display: 'flex', gap: '0.4rem', alignItems: 'center' }}>
                <input
                  type="checkbox"
                  checked={includeOpenWorld}
                  onChange={(event) => setIncludeOpenWorld(event.target.checked)}
                />
                include_open_world
              </label>
              <label style={{ display: 'flex', gap: '0.4rem', alignItems: 'center' }}>
                <input
                  type="checkbox"
                  checked={useAllNorms}
                  onChange={(event) => setUseAllNorms(event.target.checked)}
                />
                use_all_norms
              </label>
              <label style={{ display: 'flex', gap: '0.4rem', alignItems: 'center' }}>
                <input
                  type="checkbox"
                  checked={disablePatterns}
                  onChange={(event) => setDisablePatterns(event.target.checked)}
                />
                disable_patterns
              </label>
            </div>
          </div>

          <div style={{ gridColumn: '1 / -1', display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
            <button className="btn btn-primary" type="submit" disabled={createMutation.isPending}>
              {createMutation.isPending ? 'Создаем…' : 'Создать сессию'}
            </button>
            {feedbackMessage && (
              <span className={feedbackState === 'error' ? 'alert alert-error' : 'muted'}>{feedbackMessage}</span>
            )}
          </div>
        </form>
      </section>

      <section className="card" style={{ marginBottom: '1rem' }}>
        <div className="card-header">
          <h2 className="card-title">Сессии</h2>
          {sessionsQuery.isFetching && <span className="muted">Обновляем…</span>}
        </div>

        {sessionsQuery.error && <p className="alert alert-error">Не удалось загрузить список сессий.</p>}

        <div className="table-container">
          <table className="table">
            <thead>
              <tr>
                <th>Session</th>
                <th>Статус</th>
                <th>Размер выборки</th>
                <th>Целевых моделей</th>
                <th>Создана</th>
              </tr>
            </thead>
            <tbody>
              {(sessionsQuery.data || []).map((session) => {
                const selected = session.id === selectedSessionId;
                return (
                  <tr
                    key={session.id}
                    onClick={() => setSelectedSessionId(session.id)}
                    style={{
                      cursor: 'pointer',
                      background: selected ? 'rgba(37, 99, 235, 0.07)' : undefined,
                    }}
                  >
                    <td>{shortId(session.id)}</td>
                    <td>
                      <span className={`status-pill ${String(session.status || '').toLowerCase()}`}>{session.status}</span>
                    </td>
                    <td>{session.sample_size}</td>
                    <td>{session.target_models?.length || 0}</td>
                    <td>{new Date(session.created_at).toLocaleString()}</td>
                  </tr>
                );
              })}
              {!(sessionsQuery.data || []).length && (
                <tr>
                  <td colSpan={5} className="muted">
                    Сессий пока нет.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="card">
        <div className="card-header">
          <h2 className="card-title">Детали сессии</h2>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button
              className="btn btn-secondary"
              type="button"
              onClick={() => detailQuery.refetch()}
              disabled={!selectedSessionId || detailQuery.isFetching}
            >
              Обновить
            </button>
            <button
              className="btn btn-primary"
              type="button"
              onClick={() => selectedSessionId && evaluateMutation.mutate(selectedSessionId)}
              disabled={!selectedSessionId || !canEvaluate || evaluateMutation.isPending}
            >
              {evaluateMutation.isPending ? 'Оцениваем…' : 'Запустить оценку экспертом'}
            </button>
          </div>
        </div>

        {!selectedSessionId && <p className="muted">Выберите сессию выше.</p>}
        {detailQuery.error && <p className="alert alert-error">Не удалось загрузить детали сессии.</p>}

        {detailQuery.data && (
          <div style={{ display: 'grid', gap: '1rem' }}>
            <div className="section-grid">
              <div>
                <strong>Session:</strong> {detailQuery.data.session.id}
              </div>
              <div>
                <strong>Статус:</strong> {detailQuery.data.session.status}
              </div>
              <div>
                <strong>Кейсов:</strong> {detailQuery.data.cases.length}
              </div>
              <div>
                <strong>Judgements:</strong> {detailQuery.data.judgements.length}
              </div>
            </div>

            <div>
              <h3 className="card-title" style={{ marginBottom: '0.5rem' }}>Leaderboard</h3>
              <div className="table-container">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Provider</th>
                      <th>Model</th>
                      <th>Cases</th>
                      <th>AVG score</th>
                    </tr>
                  </thead>
                  <tbody>
                    {detailQuery.data.leaderboard.map((row) => (
                      <tr key={`${row.provider}:${row.model}`}>
                        <td>{row.provider}</td>
                        <td>{row.model}</td>
                        <td>{row.cases}</td>
                        <td>{row.avg_score.toFixed(2)}</td>
                      </tr>
                    ))}
                    {!detailQuery.data.leaderboard.length && (
                      <tr>
                        <td colSpan={4} className="muted">
                          Нет оценок.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            <div>
              <h3 className="card-title" style={{ marginBottom: '0.5rem' }}>Кейсы</h3>
              <div className="table-container">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Target</th>
                      <th>Статус</th>
                      <th>Source run</th>
                      <th>Review run</th>
                      <th>AI findings</th>
                      <th>Open world</th>
                      <th>Score</th>
                    </tr>
                  </thead>
                  <tbody>
                    {detailQuery.data.cases.map((row) => (
                      <tr key={row.id}>
                        <td>{row.target_provider}/{row.target_model}</td>
                        <td>{row.status}</td>
                        <td>{shortId(row.source_run_id)}</td>
                        <td>
                          <a href={`/runs/${row.review_run_id}`}>{shortId(row.review_run_id)}</a>
                        </td>
                        <td>{row.ai_findings_count ?? 0}</td>
                        <td>{row.open_world_count ?? 0}</td>
                        <td>{typeof row.score_overall === 'number' ? row.score_overall.toFixed(2) : '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}

export default ModelLabPage;
