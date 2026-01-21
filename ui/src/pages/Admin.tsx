import { FormEvent, useMemo, useState, useEffect } from 'react';
import axios from 'axios';
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
  fetchNormCatalog,
  fetchRuns,
  fetchUsers,
  forceFailReviewRun,
  updateUserRole,
  fetchSuggestedNorms,
  voteSuggestedNorm,
  acceptSuggestedNorm,
  LLMPlaygroundResponse,
  requeueReviewRun,
  runLLMPlayground,
  updateUserStatus,
  updateUserCompany,
  UserProfile,
} from '../services/api';

type LLMRequestInfo = Omit<LLMPlaygroundResponse, 'response'>;

const DEFAULT_LLM_SYSTEM_PROMPT = `Ты — строгий эксперт по код-ревью 1С.
Твоя цель — находить только критические (critical) и серьезные (major) проблемы.
Фокус: корректность, потеря данных, безопасность, транзакции, конкурентность,
неправильная логика запросов, ошибки типов/дат, серьезные performance-риски.
Не упоминай стиль, нейминг, форматирование и мелкие улучшения.
Если проблем нет — верни пустой массив [].
Ответ строго JSON-массив без пояснений.
Схема:
[
  {
    "severity": "critical|major",
    "title": "...",
    "reason": "...",
    "evidence": "строки/цитата",
    "suggestion": "как исправить"
  }
]`;

const DEFAULT_LLM_USER_PROMPT = `Проанализируй код 1С ниже и найди только критические/серьезные проблемы.
Код:
\`\`\`bsl
// вставьте код сюда
\`\`\``;

function AdminPage() {
  const userQuery = useQuery({ queryKey: ['admin-me'], queryFn: fetchCurrentUser });
  const role = (userQuery.data?.role || '').toLowerCase();
  const isAdmin = role === 'admin';
  const isTeacher = role === 'teacher';
  const canManageNorms = isAdmin || isTeacher;
  const currentUserId = userQuery.data?.id;
  useEffect(() => {
    if (isTeacher && !isAdmin) {
      setActiveTab('norms');
    }
  }, [isTeacher, isAdmin]);
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
  const [llmSystemPrompt, setLlmSystemPrompt] = useState(DEFAULT_LLM_SYSTEM_PROMPT);
  const [llmUserPrompt, setLlmUserPrompt] = useState(DEFAULT_LLM_USER_PROMPT);
  const [llmTemperature, setLlmTemperature] = useState('0.2');
  const [llmUseReasoning, setLlmUseReasoning] = useState(false);
  const [llmModelOverride, setLlmModelOverride] = useState('');
  const [llmResponse, setLlmResponse] = useState<LLMPlaygroundResponse | null>(null);
  const [llmError, setLlmError] = useState<string | null>(null);
  const [isSubmittingLlm, setSubmittingLlm] = useState(false);
  const [llmRequestCount, setLlmRequestCount] = useState(0);
  const [llmSuccessCount, setLlmSuccessCount] = useState(0);
  const [llmLastDurationMs, setLlmLastDurationMs] = useState<number | null>(null);
  const [llmLastResponseChars, setLlmLastResponseChars] = useState<number | null>(null);
  const [llmLastResponseAt, setLlmLastResponseAt] = useState<string | null>(null);
  const [llmCopyMessage, setLlmCopyMessage] = useState<string | null>(null);
  const [llmLastRequestInfo, setLlmLastRequestInfo] = useState<LLMRequestInfo | null>(null);
  const [normSource, setNormSource] = useState<'static' | 'llm'>('static');
  const [normSearch, setNormSearch] = useState('');
  const [normLimit, setNormLimit] = useState('200');
  const [activeTab, setActiveTab] = useState<
    'users' | 'llm' | 'runs' | 'access' | 'caddy' | 'norms'
  >('users');
  const [normsSubTab, setNormsSubTab] = useState<'catalog' | 'requests'>('catalog');

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

  const normCatalogQuery = useQuery({
    queryKey: ['norms-catalog', normSource, normSearch, normLimit],
    queryFn: () =>
      fetchNormCatalog({
        source: normSource,
        query: normSearch || undefined,
        limit: Number(normLimit) || 200,
      }),
    enabled: canManageNorms,
  });

  const suggestedNormsQuery = useQuery({
    queryKey: ['suggested-norms'],
    queryFn: () => fetchSuggestedNorms({ limit: 200 }),
    enabled: canManageNorms,
  });

  const statusMutation = useMutation({
    mutationFn: ({ userId, status }: { userId: string; status: string }) =>
      updateUserStatus(userId, status),
    onSuccess: () => {
      usersQuery.refetch();
    },
  });

  const roleMutation = useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: string }) =>
      updateUserRole(userId, role),
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

  const suggestedNormVoteMutation = useMutation({
    mutationFn: ({ normId, vote }: { normId: string; vote: 1 | -1 }) =>
      voteSuggestedNorm(normId, vote),
    onSuccess: () => {
      suggestedNormsQuery.refetch();
    },
  });

  const suggestedNormAcceptMutation = useMutation({
    mutationFn: (normId: string) => acceptSuggestedNorm(normId),
    onSuccess: () => {
      suggestedNormsQuery.refetch();
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

  const handleNormCatalogSubmit = (event: FormEvent) => {
    event.preventDefault();
    normCatalogQuery.refetch();
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

  const handleLlmSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setSubmittingLlm(true);
    setLlmError(null);
    setLlmResponse(null);
    setLlmCopyMessage(null);
    setLlmLastRequestInfo(null);
    const temperature = Number(llmTemperature);
    if (Number.isNaN(temperature) || temperature < 0 || temperature > 2) {
      setLlmError('Температура должна быть числом от 0 до 2.');
      setSubmittingLlm(false);
      return;
    }
    const startedAt = Date.now();
    setLlmRequestCount((prev) => prev + 1);
    try {
      const response = await runLLMPlayground({
        system_prompt: llmSystemPrompt,
        user_prompt: llmUserPrompt,
        temperature,
        use_reasoning: llmUseReasoning,
        model: llmModelOverride.trim() || undefined,
      });
      setLlmResponse(response);
      setLlmLastRequestInfo({
        api_base: response.api_base,
        endpoint: response.endpoint,
        timeout_seconds: response.timeout_seconds,
        model: response.model,
        temperature: response.temperature,
        use_reasoning: response.use_reasoning,
        model_override: response.model_override ?? null,
        request_headers: response.request_headers,
        request_payload: response.request_payload,
      });
      setLlmSuccessCount((prev) => prev + 1);
      setLlmLastDurationMs(Date.now() - startedAt);
      setLlmLastResponseChars(response.response.length);
      setLlmLastResponseAt(new Date().toLocaleString());
    } catch (err) {
      console.error(err);
      if (axios.isAxiosError(err)) {
        const detail = (err.response?.data as { detail?: unknown } | undefined)?.detail;
        if (detail && typeof detail === 'object' && !Array.isArray(detail)) {
          const message = (detail as { message?: string }).message;
          const request = (detail as { request?: LLMRequestInfo }).request;
          setLlmError(message || 'Не удалось вызвать LLM.');
          if (request) {
            setLlmLastRequestInfo(request);
          }
        } else if (typeof detail === 'string') {
          setLlmError(detail || 'Не удалось вызвать LLM.');
        } else {
          setLlmError('Не удалось вызвать LLM.');
        }
      } else {
        setLlmError('Не удалось вызвать LLM.');
      }
      setLlmLastDurationMs(Date.now() - startedAt);
    } finally {
      setSubmittingLlm(false);
    }
  };

  const handleCopyLlmRequest = async () => {
    if (!llmRequestDump) return;
    try {
      await navigator.clipboard.writeText(llmRequestDump);
      setLlmCopyMessage('Скопировано.');
    } catch (err) {
      console.error(err);
      setLlmCopyMessage('Не удалось скопировать.');
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

  const llmRequestDump = useMemo(() => {
    if (!llmLastRequestInfo) return null;
    return JSON.stringify(
      {
        endpoint: llmLastRequestInfo.endpoint,
        api_base: llmLastRequestInfo.api_base,
        timeout_seconds: llmLastRequestInfo.timeout_seconds,
        model: llmLastRequestInfo.model,
        temperature: llmLastRequestInfo.temperature,
        use_reasoning: llmLastRequestInfo.use_reasoning,
        model_override: llmLastRequestInfo.model_override ?? null,
        headers: llmLastRequestInfo.request_headers,
        payload: llmLastRequestInfo.request_payload,
      },
      null,
      2,
    );
  }, [llmLastRequestInfo]);

  if (userQuery.isLoading) {
    return <p>Загружаем админ-панель...</p>;
  }

  if (userQuery.error || (!isAdmin && !isTeacher)) {
    return <p className="alert alert-error">Доступ только для администраторов и преподавателей.</p>;
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
          <p className="muted">{isAdmin ? 'Администрирование' : 'Режим обучения'}</p>
          <h1>{isAdmin ? 'Панель администратора' : 'Панель преподавателя'}</h1>
        </div>
        {isAdmin && (
          <div className="balance-chip">
            Пользователи: {usersSummary.total} • активные: {usersSummary.active} • заблокированные:{' '}
            {usersSummary.disabled}
          </div>
        )}
      </div>

      {activeTab === 'norms' && canManageNorms && (
        <>
          <div className="tabs" style={{ marginBottom: '1rem' }}>
            {[
              { id: 'catalog', label: 'Каталог норм' },
              { id: 'requests', label: 'Заявки норм' },
            ].map((tab) => (
              <button
                key={tab.id}
                type="button"
                className={`tab-button ${normsSubTab === tab.id ? 'active' : ''}`}
                onClick={() => setNormsSubTab(tab.id as 'catalog' | 'requests')}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {normsSubTab === 'catalog' && (
          <div className="card" style={{ marginBottom: '1.5rem' }}>
            <div className="card-header">
              <div>
                <h2 className="card-title">Каталог норм</h2>
                <p className="muted">
                  Просмотр норм статического анализатора и LLM. Используйте фильтр для поиска.
                </p>
              </div>
            </div>
            <form onSubmit={handleNormCatalogSubmit} className="form-grid" style={{ gap: '1rem' }}>
              <div className="field">
                <label htmlFor="norm-source">Источник</label>
                <select
                  id="norm-source"
                  value={normSource}
                  onChange={(event) => setNormSource(event.target.value as 'static' | 'llm')}
                >
                  <option value="static">Статический анализатор</option>
                  <option value="llm">LLM нормы</option>
                </select>
              </div>
              <div className="field">
                <label htmlFor="norm-search">Поиск</label>
                <input
                  id="norm-search"
                  type="text"
                  value={normSearch}
                  onChange={(event) => setNormSearch(event.target.value)}
                  placeholder="norm_id, название, раздел"
                />
              </div>
              <div className="field">
                <label htmlFor="norm-limit">Лимит</label>
                <input
                  id="norm-limit"
                  type="number"
                  min={1}
                  max={2000}
                  value={normLimit}
                  onChange={(event) => setNormLimit(event.target.value)}
                />
              </div>
              <button type="submit" className="btn btn-primary">
                Обновить
              </button>
            </form>
            {normCatalogQuery.isLoading && <p className="muted">Загружаем нормы...</p>}
            {normCatalogQuery.error && (
              <p className="alert alert-error">Не удалось загрузить каталог норм.</p>
            )}
            {normCatalogQuery.data && (
              <div className="card-list" style={{ marginTop: '1rem' }}>
                {normCatalogQuery.data.map((norm) => (
                  <details key={norm.norm_id} className="card" style={{ padding: '1rem' }}>
                    <summary>
                      <strong>{norm.norm_id}</strong>
                      {norm.title ? ` · ${norm.title}` : ''}
                    </summary>
                    <p className="muted" style={{ marginTop: '0.5rem' }}>
                      {[norm.section, norm.category, norm.default_severity, norm.priority && `P${norm.priority}`]
                        .filter(Boolean)
                        .join(' · ')}
                    </p>
                    {norm.norm_text && <p style={{ whiteSpace: 'pre-wrap' }}>{norm.norm_text}</p>}
                    {norm.detection_hint && (
                      <p className="muted" style={{ marginTop: '0.5rem' }}>
                        Подсказка: {norm.detection_hint}
                      </p>
                    )}
                    {norm.rationale && (
                      <p className="muted" style={{ marginTop: '0.5rem' }}>
                        Обоснование: {norm.rationale}
                      </p>
                    )}
                    {norm.source_reference && (
                      <p className="muted" style={{ marginTop: '0.5rem' }}>
                        Источник: {norm.source_reference}
                      </p>
                    )}
                    {norm.scope && (
                      <p className="muted" style={{ marginTop: '0.5rem' }}>
                        Область: {norm.scope}
                      </p>
                    )}
                  </details>
                ))}
                {!normCatalogQuery.data.length && (
                  <div className="empty-state">Нормы не найдены.</div>
                )}
              </div>
            )}
          </div>
          )}

          {normsSubTab === 'requests' && (
            <div className="card" style={{ marginBottom: '1.5rem' }}>
              <div className="card-header">
                <div>
                  <h2 className="card-title">Заявки норм</h2>
                  <p className="muted">Результаты автооформления норм через LLM, доступно голосование.</p>
                </div>
                <button className="btn btn-secondary" type="button" onClick={() => suggestedNormsQuery.refetch()}>
                  Обновить
                </button>
              </div>
              {suggestedNormsQuery.isLoading && <p className="muted">Загружаем заявки...</p>}
              {suggestedNormsQuery.error && (
                <p className="alert alert-error">Не удалось загрузить заявки на нормы.</p>
              )}
              {suggestedNormsQuery.data && (
                <table className="table">
                  <thead>
                    <tr>
                      <th>Статус</th>
                      <th>Раздел / severity</th>
                      <th>Описание</th>
                      <th>Голоса</th>
                      <th>Действия</th>
                    </tr>
                  </thead>
                  <tbody>
                    {suggestedNormsQuery.data.items.map((item) => (
                      <tr key={item.id}>
                        <td>
                          <span className="table-badge">{item.status}</span>
                          {item.duplicate_of && item.duplicate_of.length > 0 && (
                            <div className="muted">Дубликат: {item.duplicate_of.join(', ')}</div>
                          )}
                        </td>
                        <td>
                          <div>{item.section}</div>
                          <div className="muted">{item.generated_severity || item.severity}</div>
                        </td>
                        <td style={{ maxWidth: '520px', whiteSpace: 'pre-wrap' }}>
                          <strong>{item.generated_title || item.generated_norm_id || 'Без заголовка'}</strong>
                          <div className="muted" style={{ marginTop: '0.35rem' }}>
                            {item.generated_text || item.text_raw}
                          </div>
                        </td>
                        <td>{item.vote_score}</td>
                    <td>
                      <div className="btn-group">
                        <button
                          type="button"
                          className={`btn btn-secondary ${item.user_vote === 1 ? 'active' : ''}`}
                          onClick={() => suggestedNormVoteMutation.mutate({ normId: item.id, vote: 1 })}
                        >
                          +
                        </button>
                        <button
                          type="button"
                          className={`btn btn-secondary ${item.user_vote === -1 ? 'active' : ''}`}
                          onClick={() => suggestedNormVoteMutation.mutate({ normId: item.id, vote: -1 })}
                        >
                          -
                        </button>
                        {isAdmin && (
                          <button
                            type="button"
                            className="btn btn-primary"
                            onClick={() => suggestedNormAcceptMutation.mutate(item.id)}
                            disabled={
                              suggestedNormAcceptMutation.isPending
                              || !item.generated_norm_id
                              || !item.generated_title
                              || !item.generated_text
                              || item.status === 'accepted_auto'
                              || item.status === 'accepted_manual'
                              || item.status === 'rejected_duplicate'
                            }
                          >
                            Принять норму
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
              )}
              {suggestedNormsQuery.data && !suggestedNormsQuery.data.items.length && (
                <div className="empty-state">Пока нет заявок.</div>
              )}
            </div>
          )}
        </>
      )}

      <div className="tabs">
        {[
          ...(canManageNorms ? [{ id: 'norms', label: 'Нормы' }] : []),
          ...(isAdmin
            ? [
                { id: 'users', label: 'Пользователи' },
                { id: 'llm', label: 'LLM эксперименты' },
                { id: 'runs', label: 'Запуски' },
                { id: 'access', label: 'Логи доступа' },
                { id: 'caddy', label: 'Логи Caddy' },
              ]
            : []),
        ].map((tab) => (
          <button
            key={tab.id}
            type="button"
            className={`tab-button ${activeTab === tab.id ? 'active' : ''}`}
            onClick={() =>
            setActiveTab(
                tab.id as 'users' | 'llm' | 'runs' | 'access' | 'caddy' | 'norms',
              )
            }
          >
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === 'users' && isAdmin && (
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
                  <td>
                    <select
                      value={user.role}
                      disabled={roleMutation.isPending || user.id === currentUserId}
                      onChange={(event) => {
                        roleMutation.mutate({ userId: user.id, role: event.target.value });
                      }}
                    >
                      <option value="user">user</option>
                      <option value="teacher">teacher</option>
                      <option value="admin">admin</option>
                    </select>
                  </td>
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
      )}

      {activeTab === 'users' && isAdmin && (
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
      )}

      {activeTab === 'llm' && isAdmin && (
        <div className="card" style={{ marginBottom: '1.5rem' }}>
        <div className="card-header">
          <div>
            <h2 className="card-title">LLM эксперименты</h2>
            <p className="muted">Отладочный вызов LLM без влияния на основной пайплайн.</p>
          </div>
        </div>
        <div className="pill-row" style={{ marginBottom: '1rem' }}>
          <span className="chip">Запросов: {llmRequestCount}</span>
          <span className="chip">Успешных: {llmSuccessCount}</span>
          <span className="chip">System: {llmSystemPrompt.length} симв.</span>
          <span className="chip">User: {llmUserPrompt.length} симв.</span>
          {llmLastDurationMs !== null && (
            <span className="chip">Последний ответ: {llmLastDurationMs} мс</span>
          )}
          {llmLastResponseChars !== null && (
            <span className="chip">Длина ответа: {llmLastResponseChars} симв.</span>
          )}
          {llmLastResponseAt && <span className="chip">Время: {llmLastResponseAt}</span>}
        </div>
        <form onSubmit={handleLlmSubmit} className="form-grid" style={{ gap: '1rem' }}>
          <div className="field" style={{ gridColumn: '1 / -1' }}>
            <label htmlFor="llm-system-prompt">System prompt</label>
            <textarea
              id="llm-system-prompt"
              rows={8}
              value={llmSystemPrompt}
              onChange={(event) => setLlmSystemPrompt(event.target.value)}
            />
          </div>
          <div className="field" style={{ gridColumn: '1 / -1' }}>
            <label htmlFor="llm-user-prompt">User prompt</label>
            <textarea
              id="llm-user-prompt"
              rows={10}
              value={llmUserPrompt}
              onChange={(event) => setLlmUserPrompt(event.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="llm-temperature">Температура</label>
            <input
              id="llm-temperature"
              type="number"
              step="0.1"
              min={0}
              max={2}
              value={llmTemperature}
              onChange={(event) => setLlmTemperature(event.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="llm-model-override">Модель (опционально)</label>
            <input
              id="llm-model-override"
              type="text"
              value={llmModelOverride}
              onChange={(event) => setLlmModelOverride(event.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="llm-use-reasoning">Рассуждающая модель</label>
            <input
              id="llm-use-reasoning"
              type="checkbox"
              checked={llmUseReasoning}
              onChange={(event) => setLlmUseReasoning(event.target.checked)}
            />
          </div>
          <button type="submit" className="btn btn-primary" disabled={isSubmittingLlm}>
            Отправить
          </button>
        </form>
        {llmError && <p className="alert alert-error">{llmError}</p>}
        {llmResponse && (
          <div style={{ marginTop: '1rem' }}>
            <p className="muted">Модель: {llmResponse.model}</p>
            <pre className="diff-snippet" style={{ whiteSpace: 'pre-wrap' }}>
              {llmResponse.response}
            </pre>
          </div>
        )}
        {llmRequestDump && (
          <div style={{ marginTop: '1rem' }}>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.75rem',
                flexWrap: 'wrap',
                marginBottom: '0.5rem',
              }}
            >
              <p className="muted" style={{ margin: 0 }}>
                Параметры вызова
              </p>
              <button type="button" className="btn btn-secondary" onClick={handleCopyLlmRequest}>
                Скопировать
              </button>
              {llmCopyMessage && <span className="muted">{llmCopyMessage}</span>}
            </div>
            <pre className="diff-snippet" style={{ whiteSpace: 'pre-wrap' }}>
              {llmRequestDump}
            </pre>
          </div>
        )}
        </div>
      )}

      {activeTab === 'runs' && isAdmin && (
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
      )}

      {activeTab === 'users' && isAdmin && (
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
      )}

      {activeTab === 'access' && isAdmin && (
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
      )}

      {activeTab === 'caddy' && isAdmin && (
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
      )}
    </div>
  );
}

export default AdminPage;
