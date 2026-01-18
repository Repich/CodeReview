import { useState, useMemo, useEffect, FormEvent } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useMutation, useQuery } from '@tanstack/react-query';
import {
  fetchRun,
  fetchFindings,
  fetchAuditLogs,
  fetchFeedback,
  fetchIOLogs,
  fetchAIFindings,
  fetchCurrentUser,
  fetchLLMLogs,
  downloadFindingsJsonl,
  updateAIFindingStatus,
  deleteReviewRun,
  rerunReviewRun,
  fetchRunSources,
  createNorm,
} from '../services/api';
import type {
  Finding,
  AIFinding,
  AIFindingStatus,
  LLMLogEntry,
  RunSource,
  CognitiveComplexitySummary,
} from '../services/api';
import FindingCard from '../components/FindingCard';
import FindingFilters from '../components/FindingFilters';
import AuditLogList from '../components/AuditLogList';
import FeedbackList from '../components/FeedbackList';
import ArtifactsTable from '../components/ArtifactsTable';
import AIFindingCard from '../components/AIFindingCard';
import FindingGroupCard from '../components/FindingGroupCard';

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

const formatDecimal = (value?: number | null) => {
  if (value === null || value === undefined) return '—';
  return value.toFixed(3);
};

type FindingGroup = {
  base: Finding;
  items: Finding[];
};

type FindingDisplayItem =
  | { kind: 'single'; finding: Finding }
  | { kind: 'group'; group: FindingGroup };

const shouldGroupFinding = (finding: Finding) =>
  finding.severity === 'minor' || finding.severity === 'info';

const groupFindings = (items: Finding[]): FindingDisplayItem[] => {
  const groups = new Map<string, FindingGroup>();
  const output: FindingDisplayItem[] = [];

  items.forEach((finding) => {
    if (!shouldGroupFinding(finding)) {
      output.push({ kind: 'single', finding });
      return;
    }
    const key = [
      finding.norm_id,
      finding.detector_id,
      finding.message,
      finding.file_path ?? '',
    ].join('::');
    const existing = groups.get(key);
    if (existing) {
      existing.items.push(finding);
      return;
    }
    const group = { base: finding, items: [finding] };
    groups.set(key, group);
    output.push({ kind: 'group', group });
  });

  return output;
};

function RunDetailsPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [severity, setSeverity] = useState('');
  const [query, setQuery] = useState('');
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const [isDownloading, setIsDownloading] = useState(false);
  const [nowTs, setNowTs] = useState(() => Date.now());
  const [activeTab, setActiveTab] = useState('findings');
  const [showDiff, setShowDiff] = useState(false);
  const [showAIContext, setShowAIContext] = useState(false);
  const [showFindingsContext, setShowFindingsContext] = useState(true);
  const [selectionDraft, setSelectionDraft] = useState<{
    text: string;
    file: string | null;
    lineStart: number | null;
    lineEnd: number | null;
  } | null>(null);
  const [showNormForm, setShowNormForm] = useState(false);
  const [normId, setNormId] = useState('');
  const [normTitle, setNormTitle] = useState('');
  const [normSection, setNormSection] = useState('');
  const [normScope, setNormScope] = useState('');
  const [normDetectorType, setNormDetectorType] = useState('custom');
  const [normCheckType, setNormCheckType] = useState('manual');
  const [normSeverity, setNormSeverity] = useState('major');
  const [normText, setNormText] = useState('');
  const [normSourceRef, setNormSourceRef] = useState('user');
  const [normSourceExcerpt, setNormSourceExcerpt] = useState('');
  const [normCodeApplicable, setNormCodeApplicable] = useState(true);
  const [normIsActive, setNormIsActive] = useState(true);
  const [normVersion, setNormVersion] = useState('1');
  const [normMessage, setNormMessage] = useState<string | null>(null);
  const [normState, setNormState] = useState<'idle' | 'success' | 'error'>('idle');

  const runQuery = useQuery({
    queryKey: ['run', id],
    queryFn: () => fetchRun(id!),
    enabled: Boolean(id),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === 'queued' || status === 'running' ? 4000 : false;
    },
    refetchOnWindowFocus: true,
  });

  const isActiveRun = ['queued', 'running'].includes(runQuery.data?.status ?? '');

  const findingsQuery = useQuery({
    queryKey: ['findings', id],
    queryFn: () => fetchFindings(id!),
    enabled: Boolean(id),
    refetchInterval: () => (isActiveRun ? 4000 : false),
  });

  const auditQuery = useQuery({
    queryKey: ['audit', id],
    queryFn: () => fetchAuditLogs(id!),
    enabled: Boolean(id),
    refetchInterval: () => (isActiveRun ? 5000 : false),
  });

  const feedbackQuery = useQuery({
    queryKey: ['feedback', id],
    queryFn: () => fetchFeedback(id!),
    enabled: Boolean(id),
  });

  const artifactsQuery = useQuery({
    queryKey: ['artifacts', id],
    queryFn: () => fetchIOLogs(id!),
    enabled: Boolean(id),
    refetchInterval: () => (isActiveRun ? 5000 : false),
  });

  const aiFindingsQuery = useQuery({
    queryKey: ['ai-findings', id],
    queryFn: () => fetchAIFindings(id!),
    enabled: Boolean(id),
    refetchInterval: () => (isActiveRun ? 5000 : false),
  });

  const userQuery = useQuery({
    queryKey: ['run-details-user'],
    queryFn: fetchCurrentUser,
  });
  const role = (userQuery.data?.role || '').toLowerCase();
  const isAdmin = role === 'admin';
  const isTeacher = role === 'teacher';
  const currentUserId = userQuery.data?.id;
  const canTeach = isAdmin || isTeacher;
  const canEditRun =
    Boolean(isAdmin) || (currentUserId && runQuery.data?.user_id === currentUserId);

  const llmLogsQuery = useQuery({
    queryKey: ['llm-logs', id],
    queryFn: () => fetchLLMLogs(id!),
    enabled: Boolean(id) && isAdmin,
  });

  const runSourcesQuery = useQuery({
    queryKey: ['run-sources', id],
    queryFn: () => fetchRunSources(id!),
    enabled: Boolean(id) && (showDiff || showAIContext || showFindingsContext),
  });

  const updateAiFinding = useMutation<
    AIFinding,
    unknown,
    { findingId: string; status: AIFindingStatus; reviewerComment?: string }
  >({
    mutationFn: ({ findingId, status, reviewerComment }) =>
      updateAIFindingStatus(findingId, status, reviewerComment),
    onSuccess: () => {
      aiFindingsQuery.refetch();
    },
  });

  const createNormMutation = useMutation({
    mutationFn: (payload: {
      norm_id: string;
      title: string;
      section: string;
      scope: string;
      detector_type: string;
      check_type: string;
      default_severity: string;
      norm_text: string;
      source_reference?: string | null;
      source_excerpt?: string | null;
      code_applicability: boolean;
      is_active: boolean;
      version: number;
    }) => createNorm(payload),
  });

  const deleteRunMutation = useMutation({
    mutationFn: () => deleteReviewRun(id!),
    onSuccess: () => {
      navigate('/runs');
    },
  });

  const rerunMutation = useMutation({
    mutationFn: () => rerunReviewRun(id!),
    onSuccess: () => {
      runQuery.refetch();
      findingsQuery.refetch();
      aiFindingsQuery.refetch();
      auditQuery.refetch();
      artifactsQuery.refetch();
      llmLogsQuery.refetch();
    },
  });

  const orderedFindings = useMemo(() => {
    const items = [...(findingsQuery.data?.items ?? [])];
    const textCompare = (a: string, b: string) => a.localeCompare(b, 'ru');
    items.sort((a, b) => {
      const aFile = a.file_path || '';
      const bFile = b.file_path || '';
      const aFileMissing = aFile ? 0 : 1;
      const bFileMissing = bFile ? 0 : 1;
      if (aFileMissing !== bFileMissing) {
        return aFileMissing - bFileMissing;
      }
      if (aFile !== bFile) {
        return textCompare(aFile, bFile);
      }
      const aLine = a.line_start ?? Number.MAX_SAFE_INTEGER;
      const bLine = b.line_start ?? Number.MAX_SAFE_INTEGER;
      if (aLine !== bLine) {
        return aLine - bLine;
      }
      const aLineEnd = a.line_end ?? Number.MAX_SAFE_INTEGER;
      const bLineEnd = b.line_end ?? Number.MAX_SAFE_INTEGER;
      if (aLineEnd !== bLineEnd) {
        return aLineEnd - bLineEnd;
      }
      if (a.norm_id !== b.norm_id) {
        return textCompare(a.norm_id, b.norm_id);
      }
      if (a.detector_id !== b.detector_id) {
        return textCompare(a.detector_id, b.detector_id);
      }
      return a.id.localeCompare(b.id);
    });
    return items;
  }, [findingsQuery.data]);

  const findingOrderMap = useMemo(() => {
    const map = new Map<string, number>();
    orderedFindings.forEach((finding, index) => {
      map.set(finding.id, index + 1);
    });
    return map;
  }, [orderedFindings]);

  const filteredFindings: Finding[] = useMemo(() => {
    return orderedFindings.filter((item) => {
      if (severity && item.severity !== severity) {
        return false;
      }
      if (query && !item.message.toLowerCase().includes(query.toLowerCase())) {
        return false;
      }
      return true;
    });
  }, [orderedFindings, severity, query]);

  const displayFindings = useMemo(
    () => groupFindings(filteredFindings),
    [filteredFindings],
  );

  useEffect(() => {
    if (!isActiveRun) return undefined;
    const timer = window.setInterval(() => setNowTs(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [isActiveRun]);

  useEffect(() => {
    if (!canTeach) return undefined;
    const handler = () => {
      const selection = window.getSelection();
      if (!selection || selection.isCollapsed) {
        setSelectionDraft(null);
        return;
      }
      const rawText = selection.toString().trim();
      if (!rawText) {
        setSelectionDraft(null);
        return;
      }
      const anchorElement =
        selection.anchorNode instanceof HTMLElement
          ? selection.anchorNode
          : selection.anchorNode?.parentElement || null;
      const focusElement =
        selection.focusNode instanceof HTMLElement
          ? selection.focusNode
          : selection.focusNode?.parentElement || null;
      const container =
        anchorElement?.closest?.('[data-source-path]') ||
        focusElement?.closest?.('[data-source-path]') ||
        null;
      if (!container) {
        setSelectionDraft(null);
        return;
      }
      const file = container.getAttribute('data-source-path');
      const lines = rawText
        .split('\n')
        .map((line) => {
          const match = line.match(/^\s*(\d+)\s*:/);
          return match ? Number(match[1]) : null;
        })
        .filter((value): value is number => value !== null);
      const lineStart = lines.length ? Math.min(...lines) : null;
      const lineEnd = lines.length ? Math.max(...lines) : null;
      const text = rawText.length > 4000 ? `${rawText.slice(0, 4000)}…` : rawText;
      setSelectionDraft({ text, file, lineStart, lineEnd });
    };
    document.addEventListener('selectionchange', handler);
    return () => document.removeEventListener('selectionchange', handler);
  }, [canTeach]);

  const progressText = useMemo(() => {
    const runData = runQuery.data;
    if (!runData) return '';
    if (runData.status === 'queued' && runData.queued_at) {
      const diff = nowTs - new Date(runData.queued_at).getTime();
      if (diff > 0) {
        return `В очереди ${formatDuration(diff)}`;
      }
    }
    if (runData.status === 'running') {
      const base = runData.started_at
        ? new Date(runData.started_at).getTime()
        : runData.queued_at
          ? new Date(runData.queued_at).getTime()
          : null;
      if (base) {
        const diff = nowTs - base;
        if (diff > 0) {
          return `Выполняется ${formatDuration(diff)}`;
        }
      }
    }
    return '';
  }, [runQuery.data, nowTs]);

  const run = runQuery.data;
  const aiFindings: AIFinding[] = aiFindingsQuery.data?.items ?? [];
  const orderedAiFindings = useMemo(() => {
    const items = [...aiFindings];
    const textCompare = (a: string, b: string) => a.localeCompare(b, 'ru');
    const parseLineStart = (value?: string | null) => {
      if (!value) return Number.MAX_SAFE_INTEGER;
      const match = value.match(/(\d+)/);
      return match ? Number(match[1]) : Number.MAX_SAFE_INTEGER;
    };
    const extractEvidenceKey = (finding: AIFinding) => {
      const ev = (finding.evidence || []).find((item) => item.file || item.lines) || null;
      const file = ev?.file ?? '';
      const line = parseLineStart(ev?.lines ?? null);
      return { file, line };
    };
    items.sort((a, b) => {
      const aKey = extractEvidenceKey(a);
      const bKey = extractEvidenceKey(b);
      const aFileMissing = aKey.file ? 0 : 1;
      const bFileMissing = bKey.file ? 0 : 1;
      if (aFileMissing !== bFileMissing) {
        return aFileMissing - bFileMissing;
      }
      if (aKey.file !== bKey.file) {
        return textCompare(aKey.file, bKey.file);
      }
      if (aKey.line !== bKey.line) {
        return aKey.line - bKey.line;
      }
      const aNorm = a.norm_id || '';
      const bNorm = b.norm_id || '';
      if (aNorm !== bNorm) {
        return textCompare(aNorm, bNorm);
      }
      return a.id.localeCompare(b.id);
    });
    return items;
  }, [aiFindings]);

  const aiOrderMap = useMemo(() => {
    const map = new Map<string, number>();
    orderedAiFindings.forEach((finding, index) => {
      map.set(finding.id, index + 1);
    });
    return map;
  }, [orderedAiFindings]);
  const totalFindings = findingsQuery.data?.total ?? 0;
  const severityCounts = useMemo(() => {
    const counts: Record<string, number> = {
      critical: 0,
      major: 0,
      minor: 0,
      warning: 0,
      info: 0,
    };
    for (const item of findingsQuery.data?.items ?? []) {
      const key = (item.severity || '').toLowerCase();
      if (key in counts) {
        counts[key] += 1;
      }
    }
    return counts;
  }, [findingsQuery.data]);
  const aiCounts = useMemo(() => {
    const counts: Record<string, number> = {
      suggested: 0,
      pending: 0,
      confirmed: 0,
      rejected: 0,
    };
    for (const item of aiFindings) {
      counts[item.status] = (counts[item.status] || 0) + 1;
    }
    return counts;
  }, [aiFindings]);
  const complexityMetrics = run?.context?.metrics?.cognitive_complexity as
    | CognitiveComplexitySummary
    | undefined;
  const complexityProcedures = useMemo(() => {
    if (!complexityMetrics?.procedures) return [];
    return [...complexityMetrics.procedures].sort((a, b) => {
      if (b.complexity !== a.complexity) {
        return b.complexity - a.complexity;
      }
      if (b.loc !== a.loc) {
        return b.loc - a.loc;
      }
      return a.name.localeCompare(b.name);
    });
  }, [complexityMetrics]);
  const diffSources: RunSource[] = useMemo(
    () => (runSourcesQuery.data ?? []).filter((src) => (src.change_ranges?.length ?? 0) > 0),
    [runSourcesQuery.data],
  );
  const sourceLookup = useMemo(() => {
    if (!runSourcesQuery.data) return null;
    const map = new Map<string, string[]>();
    runSourcesQuery.data.forEach((source) => {
      map.set(source.path, source.content.split('\n'));
    });
    return map;
  }, [runSourcesQuery.data]);
  const changeRangeMap = run?.context?.change_ranges as Record<string, unknown> | undefined;
  const changeRangeCount = changeRangeMap ? Object.keys(changeRangeMap).length : 0;
  const hasChangeRanges = changeRangeCount > 0;
  const tabs = useMemo(() => {
    const items = [
      { id: 'findings', label: 'Найденные нарушения', count: totalFindings },
      { id: 'ai', label: 'Предложения LLM', count: aiFindings.length },
      {
        id: 'complexity',
        label: 'Когнитивная сложность',
        count: complexityMetrics?.procedures?.length ?? 0,
      },
      {
        id: 'llm',
        label: 'Диагностика LLM',
        count: llmLogsQuery.data?.length ?? 0,
        adminOnly: true,
      },
      { id: 'audit', label: 'Журнал событий', count: auditQuery.data?.length ?? 0 },
      { id: 'artifacts', label: 'Артефакты', count: artifactsQuery.data?.length ?? 0 },
    ];
    return items.filter((item) => (item.adminOnly ? isAdmin : true));
  }, [
    totalFindings,
    aiFindings.length,
    complexityMetrics,
    llmLogsQuery.data,
    auditQuery.data,
    artifactsQuery.data,
    isAdmin,
  ]);

  if (runQuery.isLoading || findingsQuery.isLoading) {
    return <p>Загружаем запуск...</p>;
  }

  if (runQuery.error) {
    return <p>Не удалось загрузить запуск.</p>;
  }

  const handleDownloadFindings = async () => {
    if (!id) return;
    setDownloadError(null);
    setIsDownloading(true);
    try {
      const blob = await downloadFindingsJsonl(id);
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `${id}.jsonl`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Failed to download findings', error);
      setDownloadError('Не удалось скачать findings. Попробуйте позже.');
    } finally {
      setIsDownloading(false);
    }
  };

  const handleAiStatusChange = (
    findingId: string,
    status: AIFindingStatus,
    reviewerComment?: string,
  ) => {
    if (!canEditRun) {
      return;
    }
    updateAiFinding.mutate({ findingId, status, reviewerComment });
  };

  const handleOpenNormForm = () => {
    if (!selectionDraft) return;
    if (!showNormForm && !normSourceExcerpt) {
      setNormSourceExcerpt(selectionDraft.text);
    }
    setShowNormForm(true);
  };

  const handleNormSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (!canTeach) return;
    setNormMessage(null);
    setNormState('idle');
    if (!normId || !normTitle || !normSection || !normScope || !normText) {
      setNormMessage('Заполните обязательные поля: norm_id, название, раздел, область, текст нормы.');
      setNormState('error');
      return;
    }
    try {
      await createNormMutation.mutateAsync({
        norm_id: normId.trim(),
        title: normTitle.trim(),
        section: normSection.trim(),
        scope: normScope.trim(),
        detector_type: normDetectorType.trim() || 'custom',
        check_type: normCheckType.trim() || 'manual',
        default_severity: normSeverity,
        norm_text: normText.trim(),
        source_reference: normSourceRef.trim() || null,
        source_excerpt: normSourceExcerpt.trim() || null,
        code_applicability: normCodeApplicable,
        is_active: normIsActive,
        version: Number(normVersion) || 1,
      });
      setNormMessage('Норма создана.');
      setNormState('success');
      setNormId('');
      setNormTitle('');
      setNormSection('');
      setNormScope('');
      setNormText('');
      setNormSourceRef('user');
      setNormSourceExcerpt('');
      setNormVersion('1');
      setShowNormForm(false);
    } catch (error) {
      console.error('Failed to create norm', error);
      setNormMessage('Не удалось создать норму.');
      setNormState('error');
    }
  };

  const handleDeleteRun = () => {
    if (!id || !run) return;
    if (run.status === 'running') {
      return;
    }
    if (!canEditRun) {
      return;
    }
    if (
      window.confirm(
        'Удалить запуск навсегда? Все findings, логи и артефакты будут удалены без возможности восстановления.',
      )
    ) {
      deleteRunMutation.mutate();
    }
  };

  const handleRerun = () => {
    if (!id || !run) return;
    if (run.status === 'running' || run.status === 'queued') {
      return;
    }
    if (!canEditRun) {
      return;
    }
    if (
      window.confirm(
        'Перезапустить запуск? Текущие findings, логи и артефакты будут очищены.',
      )
    ) {
      rerunMutation.mutate();
    }
  };

  return (
    <div>
      <div className="page-heading">
        <div>
          <p className="muted">Запуск</p>
          <h1>{id}</h1>
        </div>
        <div className="page-heading-actions" style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '0.25rem' }}>
          <span className={`status-pill ${run?.status ?? ''}`}>
            {statusLabels[run?.status ?? ''] ?? run?.status}
          </span>
          {progressText && <span className="muted">{progressText}</span>}
          <button
            className="btn btn-secondary"
            disabled={
              run?.status === 'running' ||
              run?.status === 'queued' ||
              rerunMutation.isPending ||
              !canEditRun
            }
            onClick={handleRerun}
          >
            {rerunMutation.isPending ? 'Перезапускаем…' : 'Перезапустить'}
          </button>
          {rerunMutation.isError && (
            <span className="alert alert-error" style={{ marginTop: '0.25rem' }}>
              Не удалось перезапустить. Попробуйте позже.
            </span>
          )}
          <button
            className="btn btn-secondary"
            disabled={run?.status === 'running' || deleteRunMutation.isPending || !canEditRun}
            onClick={handleDeleteRun}
          >
            {deleteRunMutation.isPending ? 'Удаляем…' : 'Удалить запуск'}
          </button>
          {deleteRunMutation.isError && (
            <span className="alert alert-error" style={{ marginTop: '0.25rem' }}>
              Не удалось удалить запуск. Попробуйте позже.
            </span>
          )}
        </div>
      </div>

      <div className="card" style={{ marginBottom: '1.5rem' }}>
        <div className="section-grid">
          <div>
            <p className="muted">Создано</p>
            <strong>{run?.queued_at ? new Date(run.queued_at).toLocaleString() : '—'}</strong>
          </div>
          <div>
            <p className="muted">Старт</p>
            <strong>{run?.started_at ? new Date(run.started_at).toLocaleString() : '—'}</strong>
          </div>
          <div>
            <p className="muted">Завершение</p>
            <strong>{run?.finished_at ? new Date(run.finished_at).toLocaleString() : '—'}</strong>
          </div>
          <div>
            <p className="muted">Стоимость</p>
            <strong>{run?.cost_points ?? '—'} баллов</strong>
          </div>
        </div>
      </div>

      <section className="card" style={{ marginBottom: '1.5rem' }}>
        <div className="card-header">
          <div>
            <h2 className="card-title">Сводка запуска</h2>
            <p className="muted">Ключевые метрики</p>
          </div>
        </div>
        <div className="section-grid">
          <div>
            <p className="muted">Нарушения</p>
            <strong>{totalFindings}</strong>
            <div className="pill-row">
              {(['critical', 'major', 'minor', 'warning', 'info'] as const)
                .filter((level) => severityCounts[level] > 0)
                .map((level) => (
                  <span key={level} className={`status-pill ${level}`}>
                    {level}: {severityCounts[level]}
                  </span>
                ))}
              {!totalFindings && <span className="muted">Пока нет</span>}
            </div>
          </div>
          <div>
            <p className="muted">Предложения LLM</p>
            <strong>{aiFindings.length}</strong>
            <div className="pill-row">
              {(['pending', 'confirmed', 'rejected'] as const)
                .filter((status) => aiCounts[status] > 0)
                .map((status) => (
                  <span key={status} className="table-badge">
                    {status}: {aiCounts[status]}
                  </span>
                ))}
              {!aiFindings.length && <span className="muted">Нет новых</span>}
            </div>
          </div>
          <div>
            <p className="muted">Когнитивная сложность</p>
            <strong>{complexityMetrics?.total ?? '—'}</strong>
            <div className="pill-row">
              <span className="table-badge">
                LOC: {complexityMetrics?.total_loc ?? '—'}
              </span>
              <span className="table-badge">
                на строку: {formatDecimal(complexityMetrics?.avg_per_line ?? null)}
              </span>
            </div>
          </div>
          <div>
            <p className="muted">Артефакты</p>
            <strong>{artifactsQuery.data?.length ?? 0}</strong>
            <div className="pill-row">
              <span className="table-badge">LLM логи: {llmLogsQuery.data?.length ?? 0}</span>
            </div>
          </div>
        </div>
      </section>

      {canTeach && selectionDraft && (
        <section className="card" style={{ marginBottom: '1.5rem' }}>
          <div className="card-header">
            <div>
              <h2 className="card-title">Выделение для новой нормы</h2>
              <p className="muted">
                {selectionDraft.file || 'Без файла'}
                {selectionDraft.lineStart
                  ? `:${selectionDraft.lineStart}${
                      selectionDraft.lineEnd && selectionDraft.lineEnd !== selectionDraft.lineStart
                        ? `-${selectionDraft.lineEnd}`
                        : ''
                    }`
                  : ''}
              </p>
            </div>
            <button className="btn btn-primary" type="button" onClick={handleOpenNormForm}>
              Создать норму
            </button>
          </div>
          <pre>{selectionDraft.text}</pre>
        </section>
      )}

      {showNormForm && canTeach && (
        <section className="card" style={{ marginBottom: '1.5rem' }}>
          <div className="card-header">
            <div>
              <h2 className="card-title">Новая норма</h2>
              <p className="muted">Заполните обязательные поля и сохраните норму.</p>
            </div>
            <button className="btn btn-secondary" type="button" onClick={() => setShowNormForm(false)}>
              Скрыть
            </button>
          </div>
          {selectionDraft && (
            <div style={{ marginBottom: '1rem' }}>
              <p className="muted" style={{ marginBottom: '0.35rem' }}>
                Пример/контекст:
              </p>
              <pre>{selectionDraft.text}</pre>
            </div>
          )}
          <form onSubmit={handleNormSubmit} className="form-grid" style={{ gap: '1rem' }}>
            <div className="field">
              <label htmlFor="norm-id-inline">norm_id</label>
              <input
                id="norm-id-inline"
                type="text"
                value={normId}
                onChange={(event) => setNormId(event.target.value)}
                placeholder="CUSTOM_001"
              />
              <small className="muted">Уникальный идентификатор, латиница и подчёркивания.</small>
            </div>
            <div className="field">
              <label htmlFor="norm-title-inline">Название</label>
              <input
                id="norm-title-inline"
                type="text"
                value={normTitle}
                onChange={(event) => setNormTitle(event.target.value)}
                placeholder="Краткая формулировка"
              />
            </div>
            <div className="field">
              <label htmlFor="norm-section-inline">Раздел</label>
              <input
                id="norm-section-inline"
                type="text"
                value={normSection}
                onChange={(event) => setNormSection(event.target.value)}
                placeholder="Запросы / Транзакции / Безопасность"
              />
            </div>
            <div className="field">
              <label htmlFor="norm-scope-inline">Область</label>
              <input
                id="norm-scope-inline"
                type="text"
                value={normScope}
                onChange={(event) => setNormScope(event.target.value)}
                placeholder="сервер / клиент / любой модуль"
              />
            </div>
            <div className="field">
              <label htmlFor="norm-detector-inline">Тип детектора</label>
              <input
                id="norm-detector-inline"
                type="text"
                value={normDetectorType}
                onChange={(event) => setNormDetectorType(event.target.value)}
                placeholder="custom/manual"
              />
            </div>
            <div className="field">
              <label htmlFor="norm-check-inline">Тип проверки</label>
              <input
                id="norm-check-inline"
                type="text"
                value={normCheckType}
                onChange={(event) => setNormCheckType(event.target.value)}
                placeholder="manual/llm/static"
              />
            </div>
            <div className="field">
              <label htmlFor="norm-severity-inline">Серьёзность</label>
              <select
                id="norm-severity-inline"
                value={normSeverity}
                onChange={(event) => setNormSeverity(event.target.value)}
              >
                <option value="critical">critical</option>
                <option value="major">major</option>
                <option value="minor">minor</option>
                <option value="info">info</option>
              </select>
            </div>
            <div className="field">
              <label htmlFor="norm-version-inline">Версия</label>
              <input
                id="norm-version-inline"
                type="number"
                min={1}
                value={normVersion}
                onChange={(event) => setNormVersion(event.target.value)}
              />
            </div>
            <div className="field" style={{ gridColumn: '1 / -1' }}>
              <label htmlFor="norm-text-inline">Текст нормы</label>
              <textarea
                id="norm-text-inline"
                rows={6}
                value={normText}
                onChange={(event) => setNormText(event.target.value)}
              />
              <small className="muted">Полное правило с формулировкой нарушения.</small>
            </div>
            <div className="field">
              <label htmlFor="norm-source-ref-inline">Источник (опционально)</label>
              <input
                id="norm-source-ref-inline"
                type="text"
                value={normSourceRef}
                onChange={(event) => setNormSourceRef(event.target.value)}
              />
            </div>
            <div className="field">
              <label htmlFor="norm-source-excerpt-inline">Пример/выдержка (опционально)</label>
              <input
                id="norm-source-excerpt-inline"
                type="text"
                value={normSourceExcerpt}
                onChange={(event) => setNormSourceExcerpt(event.target.value)}
              />
            </div>
            <div className="field">
              <label htmlFor="norm-code-inline">Применимо к коду</label>
              <input
                id="norm-code-inline"
                type="checkbox"
                checked={normCodeApplicable}
                onChange={(event) => setNormCodeApplicable(event.target.checked)}
              />
            </div>
            <div className="field">
              <label htmlFor="norm-active-inline">Активна</label>
              <input
                id="norm-active-inline"
                type="checkbox"
                checked={normIsActive}
                onChange={(event) => setNormIsActive(event.target.checked)}
              />
            </div>
            <button type="submit" className="btn btn-primary" disabled={createNormMutation.isPending}>
              {createNormMutation.isPending ? 'Сохраняем…' : 'Создать норму'}
            </button>
          </form>
          {normMessage && (
            <p className={`alert ${normState === 'success' ? 'alert-success' : 'alert-error'}`}>
              {normMessage}
            </p>
          )}
        </section>
      )}

      <div className="tabs">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            className={`tab-button ${activeTab === tab.id ? 'active' : ''}`}
            onClick={() => setActiveTab(tab.id)}
            type="button"
          >
            {tab.label}
            <span className="tab-count">{tab.count}</span>
          </button>
        ))}
      </div>

      {activeTab === 'findings' && (
        <>
          <section className="card" style={{ marginBottom: '1.5rem' }}>
            <div className="card-header">
              <div>
                <h2 className="card-title">Найденные нарушения</h2>
                <p className="muted">
                  {displayFindings.length} карточек · {filteredFindings.length} нарушений
                </p>
              </div>
              <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                {showFindingsContext && runSourcesQuery.isLoading && (
                  <span className="muted">Загружаем контекст…</span>
                )}
                <button
                  className="btn btn-secondary"
                  type="button"
                  onClick={() => setShowFindingsContext((prev) => !prev)}
                >
                  {showFindingsContext ? 'Скрыть контекст' : 'Показать контекст'}
                </button>
              </div>
            </div>
            <FindingFilters severity={severity} setSeverity={setSeverity} query={query} setQuery={setQuery} />
            <div className="card-list">
              {displayFindings.map((item) => {
                if (item.kind === 'single') {
                  return (
                    <FindingCard
                      key={item.finding.id}
                      finding={item.finding}
                      sequence={findingOrderMap.get(item.finding.id)}
                      showContext={showFindingsContext}
                      sourceLookup={showFindingsContext ? sourceLookup : null}
                    />
                  );
                }
                return (
                  <FindingGroupCard
                    key={`group-${item.group.base.id}`}
                    base={item.group.base}
                    items={item.group.items}
                    sequence={findingOrderMap.get(item.group.base.id)}
                    showContext={showFindingsContext}
                    sourceLookup={showFindingsContext ? sourceLookup : null}
                  />
                );
              })}
              {!displayFindings.length && (
                <div className="empty-state">Нет нарушений под текущий фильтр.</div>
              )}
            </div>
          </section>

          {hasChangeRanges && (
            <section className="card" style={{ marginBottom: '1.5rem' }}>
              <div className="card-header">
                <div>
                  <h2 className="card-title">Изменения в коде</h2>
                  <p className="muted">{changeRangeCount} файлов</p>
                </div>
                {showDiff && runSourcesQuery.isLoading && <span className="muted">Загружаем…</span>}
              </div>
              {!showDiff && (
                <button className="btn btn-secondary" type="button" onClick={() => setShowDiff(true)}>
                  Показать изменения
                </button>
              )}
              {showDiff && runSourcesQuery.error && (
                <p className="alert alert-error">Не удалось загрузить информацию об изменениях.</p>
              )}
              {showDiff && !runSourcesQuery.error && <RunDiffView sources={diffSources} />}
            </section>
          )}

          <section className="card">
            <h2 className="card-title">Обратная связь</h2>
            {feedbackQuery.isLoading && <p className="muted">Загружаем обратную связь...</p>}
            {feedbackQuery.error && <p className="alert alert-error">Не удалось загрузить отзывы.</p>}
            {feedbackQuery.data && <FeedbackList items={feedbackQuery.data.items} />}
          </section>
        </>
      )}

      {activeTab === 'ai' && (
        <section className="card" style={{ marginBottom: '1.5rem' }}>
          <div className="card-header">
            <div>
              <h2 className="card-title">Предложения LLM</h2>
              <p className="muted">
                {aiFindings.length}/{aiFindingsQuery.data?.total ?? 0}
              </p>
            </div>
            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
              {showAIContext && runSourcesQuery.isLoading && (
                <span className="muted">Загружаем контекст…</span>
              )}
              {aiFindingsQuery.isLoading && <span className="muted">Обновляем…</span>}
              <button
                className="btn btn-secondary"
                type="button"
                onClick={() => setShowAIContext((prev) => !prev)}
              >
                {showAIContext ? 'Скрыть контекст' : 'Показать контекст'}
              </button>
            </div>
          </div>
          {aiFindingsQuery.error && (
            <p className="alert alert-error">Не удалось загрузить предложения LLM.</p>
          )}
          <div className="card-list">
            {orderedAiFindings.map((finding) => (
              <AIFindingCard
                key={finding.id}
                finding={finding}
                sequence={aiOrderMap.get(finding.id)}
                onChangeStatus={
                  canEditRun
                    ? (status, reviewerComment) =>
                        handleAiStatusChange(finding.id, status, reviewerComment)
                    : undefined
                }
                isUpdating={
                  updateAiFinding.isPending && updateAiFinding.variables?.findingId === finding.id
                }
                readOnly={!canEditRun}
                sourceLookup={showAIContext ? sourceLookup : null}
              />
            ))}
            {!aiFindings.length && !aiFindingsQuery.isLoading && (
              <div className="empty-state">LLM не предложила дополнительных норм.</div>
            )}
          </div>
        </section>
      )}

      {activeTab === 'complexity' && (
        <section className="card" style={{ marginBottom: '1.5rem' }}>
          <div className="card-header">
            <div>
              <h2 className="card-title">Когнитивная сложность</h2>
              <p className="muted">Метрики по процедурам и функциям</p>
            </div>
            {complexityMetrics && (
              <span className="muted">{complexityMetrics.procedures?.length ?? 0} процедур</span>
            )}
          </div>
          {!complexityMetrics && (
            <div className="empty-state">Метрики пока не рассчитаны для этого запуска.</div>
          )}
          {complexityMetrics && (
            <>
              <div className="section-grid" style={{ marginBottom: '1rem' }}>
                <div>
                  <p className="muted">Суммарная сложность</p>
                  <strong>{complexityMetrics.total}</strong>
                </div>
                <div>
                  <p className="muted">Строк кода</p>
                  <strong>{complexityMetrics.total_loc}</strong>
                </div>
                <div>
                  <p className="muted">Сложность на строку</p>
                  <strong>{formatDecimal(complexityMetrics.avg_per_line)}</strong>
                </div>
              </div>
              <div className="table-container">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Процедура</th>
                      <th>Файл</th>
                      <th>Строки</th>
                      <th>Сложность</th>
                      <th>LOC</th>
                      <th>На строку</th>
                    </tr>
                  </thead>
                  <tbody>
                    {complexityProcedures.map((proc) => (
                      <tr key={`${proc.file_path}:${proc.name}:${proc.start_line}`}>
                        <td>{proc.name}</td>
                        <td className="muted">{proc.file_path}</td>
                        <td>
                          {proc.start_line}-{proc.end_line}
                        </td>
                        <td>{proc.complexity}</td>
                        <td>{proc.loc}</td>
                        <td>{formatDecimal(proc.avg_per_line)}</td>
                      </tr>
                    ))}
                    {!complexityProcedures.length && (
                      <tr>
                        <td colSpan={6} className="muted">
                          Процедуры и функции не обнаружены.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </section>
      )}

      {activeTab === 'llm' && isAdmin && (
        <section className="card" style={{ marginBottom: '1.5rem' }}>
          <div className="card-header">
            <div>
              <h2 className="card-title">Диагностика LLM</h2>
              <p className="muted">
                {llmLogsQuery.data?.length ?? 0} логов • {run?.llm_prompt_version || 'версия ?'}
              </p>
            </div>
            {llmLogsQuery.isLoading && <span className="muted">Загружаем…</span>}
          </div>
          {llmLogsQuery.error && (
            <p className="alert alert-error">Не удалось загрузить диагностические логи.</p>
          )}
          <div className="card-list">
            {(llmLogsQuery.data ?? []).map((log) => (
              <LLMLogCard key={log.io_log_id} log={log} />
            ))}
            {!llmLogsQuery.data?.length && !llmLogsQuery.isLoading && (
              <div className="empty-state">Логи LLM отсутствуют.</div>
            )}
          </div>
        </section>
      )}

      {activeTab === 'audit' && (
        <section className="card" style={{ marginBottom: '1.5rem' }}>
          <h2 className="card-title">Журнал событий</h2>
          {auditQuery.isLoading && <p className="muted">Загружаем журнал...</p>}
          {auditQuery.error && <p className="alert alert-error">Не удалось загрузить журнал.</p>}
          {auditQuery.data && <AuditLogList logs={auditQuery.data} />}
        </section>
      )}

      {activeTab === 'artifacts' && (
        <section className="card">
          <div className="card-header">
            <h2 className="card-title">Артефакты</h2>
            <button className="btn btn-secondary" onClick={handleDownloadFindings} disabled={isDownloading}>
              {isDownloading ? 'Готовим файл...' : 'Скачать findings JSONL'}
            </button>
          </div>
          {downloadError && <p className="alert alert-error">{downloadError}</p>}
          {artifactsQuery.isLoading && <p className="muted">Загружаем артефакты...</p>}
          {artifactsQuery.error && <p className="alert alert-error">Не удалось загрузить артефакты.</p>}
          {artifactsQuery.data && <ArtifactsTable artifacts={artifactsQuery.data} />}
        </section>
      )}
    </div>
  );
}

export default RunDetailsPage;

function LLMLogCard({ log }: { log: LLMLogEntry }) {
  const { data } = log;
  const unitLabel = data.unit_name || data.unit_id || 'фрагмент';
  const responseText = (data.response ?? '').trim();
  return (
    <article className="card">
      <div className="card-header" style={{ marginBottom: '0.5rem' }}>
        <div>
          <strong>{new Date(log.created_at).toLocaleString()}</strong>
          <p className="muted" style={{ margin: 0 }}>
            prompt_version: {data.prompt_version ?? '—'}
          </p>
          <p className="muted" style={{ margin: 0 }}>
            Единица: {unitLabel}
          </p>
        </div>
        <span className="status-pill info">LLM log</span>
      </div>
      <p className="muted" style={{ marginBottom: '0.5rem' }}>
        Контекст файлов: {data.context_files?.length ?? 0} • Модулей: {data.source_paths?.length ?? 0}
      </p>
      <details style={{ marginBottom: '0.5rem' }}>
        <summary>Показать промпт</summary>
        <pre>{data.prompt}</pre>
      </details>
      <details>
        <summary>Показать ответ модели</summary>
        <pre>{responseText || '[]'}</pre>
      </details>
    </article>
  );
}

function RunDiffView({ sources }: { sources: RunSource[] }) {
  if (!sources.length) {
    return <div className="empty-state">Нет изменений.</div>;
  }

  return (
    <div className="diff-view">
      {sources.map((source) => (
        <div key={source.path} className="diff-block">
          <h3 style={{ marginBottom: '0.35rem' }}>{source.path}</h3>
          {source.change_ranges?.map((range, index) => (
            <DiffSnippet
              key={`${source.path}-${index}`}
              content={source.content}
              range={range}
            />
          ))}
        </div>
      ))}
    </div>
  );
}

function DiffSnippet({
  content,
  range,
  contextLines = 3,
}: {
  content: string;
  range: { start: number; end: number };
  contextLines?: number;
}) {
  const lines = content.split('\n');
  const start = Math.max(range.start - 1 - contextLines, 0);
  const end = Math.min(range.end + contextLines, lines.length);
  const snippet = [];

  for (let idx = start; idx < end; idx += 1) {
    const lineNumber = idx + 1;
    const isChanged = lineNumber >= range.start && lineNumber <= range.end;
    snippet.push(
      <div key={lineNumber} className={`diff-line${isChanged ? ' diff-line-changed' : ''}`}>
        <span className="diff-line-number">{lineNumber.toString().padStart(4, ' ')}</span>
        <span className="diff-line-text">{lines[idx] || '\u00A0'}</span>
      </div>,
    );
  }

  return <div className="diff-snippet">{snippet}</div>;
}
