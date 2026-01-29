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
  createSuggestedNorm,
  fetchSuggestedNormSections,
  fetchRunEvaluation,
  startRunEvaluation,
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
  const [showFindingsContext, setShowFindingsContext] = useState(true);
  const [selectedAiId, setSelectedAiId] = useState<string | null>(null);
  const [selectedFindingKey, setSelectedFindingKey] = useState<string | null>(null);
  const [selectedFindingRange, setSelectedFindingRange] = useState<{
    file: string;
    lineStart: number;
    lineEnd: number;
  } | null>(null);
  const [aiLeftWidth, setAiLeftWidth] = useState(760);
  const [isResizingAI, setIsResizingAI] = useState(false);
  const [selectionDraft, setSelectionDraft] = useState<{
    text: string;
    file: string | null;
    lineStart: number | null;
    lineEnd: number | null;
  } | null>(null);
  const [showNormForm, setShowNormForm] = useState(false);
  const [normSection, setNormSection] = useState('');
  const [normSeverity, setNormSeverity] = useState<'critical' | 'major' | 'minor' | 'info'>('major');
  const [normText, setNormText] = useState('');
  const [normMessage, setNormMessage] = useState<string | null>(null);
  const [normState, setNormState] = useState<'idle' | 'success' | 'error'>('idle');
  const [selectionRuns, setSelectionRuns] = useState(5);

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
  const evaluationOf = (runQuery.data?.context as Record<string, unknown> | undefined)?.evaluation_of as
    | string
    | undefined;
  const isEvaluationRun = Boolean(evaluationOf);

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
  const findingsView = userQuery.data?.settings?.findings_view ?? 'separate';
  const isCombinedView = findingsView === 'combined';

  const llmLogsQuery = useQuery({
    queryKey: ['llm-logs', id],
    queryFn: () => fetchLLMLogs(id!),
    enabled: Boolean(id) && isAdmin,
  });

  const evaluationQuery = useQuery({
    queryKey: ['run-evaluation', id],
    queryFn: () => fetchRunEvaluation(id!),
    enabled: Boolean(id) && isAdmin,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === 'queued' || status === 'running' ? 4000 : false;
    },
  });

  const evaluationMutation = useMutation({
    mutationFn: () => startRunEvaluation(id!, selectionRuns),
    onSuccess: () => {
      evaluationQuery.refetch();
    },
  });

  const evaluationComparison = useMemo(() => {
    const report = evaluationQuery.data?.report as
      | {
          baseline?: { overall?: { avg_jaccard?: number } };
          prefiltered?: { overall?: { avg_jaccard?: number } };
        }
      | undefined;
    const baseline = report?.baseline?.overall?.avg_jaccard;
    const prefiltered = report?.prefiltered?.overall?.avg_jaccard;
    if (typeof baseline !== 'number' || typeof prefiltered !== 'number') {
      return null;
    }
    const delta = prefiltered - baseline;
    const threshold = 0.02;
    let verdict = 'Без заметных изменений';
    if (delta > threshold) {
      verdict = 'Стало лучше';
    } else if (delta < -threshold) {
      verdict = 'Стало хуже';
    }
    return { baseline, prefiltered, delta, verdict };
  }, [evaluationQuery.data?.report]);

  const runSourcesQuery = useQuery({
    queryKey: ['run-sources', id],
    queryFn: () => fetchRunSources(id!),
    enabled:
      Boolean(id) &&
      (activeTab === 'ai' ||
        (activeTab === 'findings' && (showFindingsContext || isCombinedView)) ||
        showDiff),
  });

  const normSectionsQuery = useQuery({
    queryKey: ['suggested-norm-sections'],
    queryFn: () => fetchSuggestedNormSections(),
    enabled: canTeach,
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
    mutationFn: (payload: { section: string; severity: 'critical' | 'major' | 'minor' | 'info'; text: string }) =>
      createSuggestedNorm(payload),
  });
  const [lastSuggested, setLastSuggested] = useState<import('../services/api').SuggestedNorm | null>(null);
  const [isSuggesting, setIsSuggesting] = useState(false);

  const deleteRunMutation = useMutation({
    mutationFn: () => deleteReviewRun(id!),
    onSuccess: () => {
      navigate('/runs');
    },
  });

  const rerunMutation = useMutation({
    mutationFn: (runId: string) => rerunReviewRun(runId),
    onSuccess: (_data, runId) => {
      if (runId && runId !== id) {
        navigate(`/runs/${runId}`);
        return;
      }
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
    if (activeTab === 'ai' && canTeach) return;
    setSelectionDraft(null);
    setShowNormForm(false);
  }, [activeTab, canTeach]);

  useEffect(() => {
    if (normSectionsQuery.data && normSectionsQuery.data.length && !normSection) {
      setNormSection(normSectionsQuery.data[0]);
    }
  }, [normSectionsQuery.data, normSection]);

  useEffect(() => {
    const handleMouseMove = (event: MouseEvent) => {
      if (!isResizingAI) return;
      const newWidth = Math.min(Math.max(event.clientX - 240, 520), 1100);
      setAiLeftWidth(newWidth);
    };
    const handleMouseUp = () => setIsResizingAI(false);
    if (isResizingAI) {
      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleMouseUp);
    }
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isResizingAI]);

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
  const aiCountSummary = aiFindingsQuery.isLoading ? '…' : aiFindings.length;
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
  const selectedAiFinding = useMemo(
    () => orderedAiFindings.find((f) => f.id === selectedAiId) || null,
    [orderedAiFindings, selectedAiId],
  );
  const highlightedRange = useMemo(() => {
    if (selectedFindingRange) {
      return selectedFindingRange;
    }
    const finding = selectedAiFinding;
    if (!finding) return null;
    const ev = (finding.evidence || []).find((item) => item.file || item.lines) || null;
    const file = ev?.file || (finding as any).file_path || null;
    let lineStart: number | null = (finding as any).line_start ?? null;
    let lineEnd: number | null = (finding as any).line_end ?? lineStart;
    if (ev?.lines) {
      const nums = (ev.lines.match(/\d+/g) || []).map(Number);
      if (nums.length >= 1) {
        lineStart = nums[0];
        lineEnd = nums[1] ?? nums[0];
      }
    }
    if (!file) return null;
    return {
      file,
      lineStart: lineStart || 0,
      lineEnd: lineEnd || lineStart || 0,
    };
  }, [selectedAiFinding, selectedFindingRange]);

  useEffect(() => {
    if (!highlightedRange) return;
    const escapedFile = highlightedRange.file.replace(/"/g, '\\"');
    const target = document.querySelector(
      `[data-source-path="${escapedFile}"] [data-line="${highlightedRange.lineStart}"]`,
    ) as HTMLElement | null;
    if (target && typeof target.scrollIntoView === 'function') {
      target.scrollIntoView({ block: 'center', behavior: 'smooth' });
    }
  }, [highlightedRange, runSourcesQuery.data]);
  const totalFindings = findingsQuery.data?.total ?? 0;
  const combinedFindingsCount = useMemo(
    () => totalFindings + aiFindings.length,
    [totalFindings, aiFindings.length],
  );
  const displayFindingsCount = isCombinedView ? combinedFindingsCount : totalFindings;
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
  const renderSource = (source: RunSource) => {
    const lines = source.content.split('\n');
    return (
      <pre
        data-source-path={source.path}
        data-line-start="1"
        data-line-end={String(lines.length)}
        style={{
          maxHeight: '55vh',
          overflow: 'auto',
          background: '#fff',
          color: '#0f172a',
          padding: '0.75rem',
          borderRadius: '0.5rem',
          border: '1px solid var(--border)',
        }}
      >
        {lines.map((line, idx) => {
          const ln = idx + 1;
          const isHl =
            highlightedRange &&
            highlightedRange.file === source.path &&
            ln >= highlightedRange.lineStart &&
            ln <= highlightedRange.lineEnd;
          return (
            <div
              key={`${source.path}:${ln}`}
              data-line={ln}
              style={{
                background: isHl ? 'rgba(255, 210, 0, 0.2)' : 'transparent',
                padding: '0 0.25rem',
              }}
            >
              <span style={{ color: '#7e8696', marginRight: '0.5rem' }}>
                {String(ln).padStart(4, ' ')}:
              </span>
              <span>{line}</span>
            </div>
          );
        })}
      </pre>
    );
  };
  const changeRangeMap = run?.context?.change_ranges as Record<string, unknown> | undefined;
  const changeRangeCount = changeRangeMap ? Object.keys(changeRangeMap).length : 0;
  const hasChangeRanges = changeRangeCount > 0;
  const aiCountDisplay = aiFindingsQuery.isLoading ? '…' : String(aiFindings.length);
  const evaluationCountDisplay = evaluationQuery.isLoading
    ? '…'
    : evaluationQuery.data?.report
      ? '1'
      : '0';
  const tabs = useMemo(() => {
    const items: { id: string; label: string; count: number | string; adminOnly?: boolean }[] = [
      { id: 'findings', label: 'Найденные нарушения', count: displayFindingsCount },
      { id: 'ai', label: 'Предложения LLM', count: aiCountDisplay },
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
      {
        id: 'evaluation',
        label: 'Проверка детерминизма',
        count: evaluationCountDisplay,
        adminOnly: true,
      },
      { id: 'audit', label: 'Журнал событий', count: auditQuery.data?.length ?? 0 },
      { id: 'artifacts', label: 'Артефакты', count: artifactsQuery.data?.length ?? 0 },
    ];
    return items
      .filter((item) => (item.adminOnly ? isAdmin : true))
      .filter((item) => (isCombinedView ? item.id !== 'ai' : true));
  }, [
    totalFindings,
    displayFindingsCount,
    aiCountDisplay,
    evaluationCountDisplay,
    complexityMetrics,
    llmLogsQuery.data,
    auditQuery.data,
    artifactsQuery.data,
    isAdmin,
    isCombinedView,
  ]);

  useEffect(() => {
    if (isCombinedView && activeTab === 'ai') {
      setActiveTab('findings');
    }
  }, [activeTab, isCombinedView]);

  const handleSelectStaticFinding = (finding: Finding, items?: Finding[]) => {
    const pool = items && items.length ? items : [finding];
    const candidate =
      pool.find((entry) => entry.file_path && (entry.line_start || entry.line_end)) || finding;
    const file = candidate.file_path;
    const lineStart = candidate.line_start ?? candidate.line_end ?? null;
    const lineEnd = candidate.line_end ?? lineStart ?? null;
    setSelectedFindingKey(finding.id);
    setSelectedFindingRange(
      file && lineStart
        ? {
            file,
            lineStart,
            lineEnd: lineEnd ?? lineStart,
          }
        : null,
    );
    setSelectedAiId(null);
  };

  const aiSection = (
    <section className="card" style={{ marginBottom: '1.5rem', overflow: 'hidden' }}>
      <div className="card-header">
        <div>
          <h2 className="card-title">Предложения LLM</h2>
          <p className="muted">
            {aiFindingsQuery.isLoading
              ? 'Загружаем…'
              : `${aiFindings.length}/${aiFindingsQuery.data?.total ?? 0}`}
          </p>
        </div>
        {aiFindingsQuery.isLoading && <span className="muted">Обновляем…</span>}
      </div>
      {aiFindingsQuery.error && (
        <p className="alert alert-error">Не удалось загрузить предложения LLM.</p>
      )}
      {normMessage && !showNormForm && (
        <p className={`alert ${normState === 'success' ? 'alert-success' : 'alert-error'}`}>
          {normMessage}
        </p>
      )}
      {(aiFindingsQuery.isLoading || runSourcesQuery.isLoading) && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', padding: '1rem' }}>
          <div className="loader-beeline" aria-label="Загрузка предложений LLM" />
          <div className="muted">Загружаем запуск, исходный код и предложения LLM…</div>
        </div>
      )}
      {!aiFindingsQuery.isLoading && (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: `${aiLeftWidth}px 12px 1fr`,
            columnGap: '0.75rem',
            alignItems: 'start',
            minHeight: '72vh',
            minWidth: `${aiLeftWidth + 950}px`,
          }}
        >
          <div
            className={`card-list ${isCombinedView ? 'compact-list' : ''}`}
            style={{ maxHeight: '78vh', overflow: 'auto' }}
          >
            {isCombinedView && (
              <>
                <div className="chip" style={{ marginBottom: '0.5rem' }}>
                  Статический анализ
                </div>
                <p className="muted" style={{ margin: '0 0 0.5rem' }}>
                  {displayFindings.length} карточек · {filteredFindings.length} нарушений
                </p>
                <FindingFilters
                  severity={severity}
                  setSeverity={setSeverity}
                  query={query}
                  setQuery={setQuery}
                />
                {displayFindings.map((item) => {
                  if (item.kind === 'single') {
                    return (
                      <div
                        key={`combined-${item.finding.id}`}
                        onClick={() => handleSelectStaticFinding(item.finding)}
                        style={{
                          border:
                            selectedFindingKey === item.finding.id
                              ? '1px solid var(--primary)'
                              : undefined,
                          borderRadius: '0.75rem',
                          padding: '0.25rem',
                        }}
                      >
                        <FindingCard
                          finding={item.finding}
                          sequence={findingOrderMap.get(item.finding.id)}
                          showContext={false}
                          sourceLookup={null}
                        />
                      </div>
                    );
                  }
                  return (
                    <div
                      key={`combined-group-${item.group.base.id}`}
                      onClick={() => handleSelectStaticFinding(item.group.base, item.group.items)}
                      style={{
                        border:
                          selectedFindingKey === item.group.base.id
                            ? '1px solid var(--primary)'
                            : undefined,
                        borderRadius: '0.75rem',
                        padding: '0.25rem',
                      }}
                    >
                      <FindingGroupCard
                        base={item.group.base}
                        items={item.group.items}
                        sequence={findingOrderMap.get(item.group.base.id)}
                        showContext={false}
                        sourceLookup={null}
                      />
                    </div>
                  );
                })}
                {!displayFindings.length && (
                  <div className="empty-state">Статических нарушений не найдено.</div>
                )}
                <div className="chip" style={{ margin: '0.75rem 0 0.5rem' }}>
                  Предложения LLM
                </div>
              </>
            )}
            {orderedAiFindings.map((finding) => (
              <div
                key={finding.id}
                onClick={() => {
                  setSelectedFindingKey(null);
                  setSelectedFindingRange(null);
                  setSelectedAiId(finding.id);
                  if (finding.norm_text) {
                    setNormText(finding.norm_text);
                  } else if ((finding as any).message) {
                    setNormText((finding as any).message);
                  }
                }}
                style={{
                  border: finding.id === selectedAiId ? '1px solid var(--primary)' : undefined,
                  borderRadius: '0.75rem',
                  padding: '0.25rem',
                }}
              >
                <AIFindingCard
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
                  sourceLookup={sourceLookup}
                />
              </div>
            ))}
            {!aiFindings.length && !aiFindingsQuery.isLoading && (
              <div className="empty-state">LLM не предложила дополнительных норм.</div>
            )}
          </div>

          <div
            onMouseDown={() => setIsResizingAI(true)}
            style={{
              cursor: 'col-resize',
              width: '12px',
              height: '100%',
              background:
                'repeating-linear-gradient(0deg, #f6d200, #f6d200 6px, #000 6px, #000 10px)',
              borderRadius: '6px',
              margin: '0 auto',
            }}
            aria-label="Перетащите, чтобы изменить ширину колонок"
          />

          <div className="card" style={{ padding: '1rem', maxHeight: '78vh', overflow: 'auto' }}>
            <div className="card-header" style={{ marginBottom: '0.5rem' }}>
              <div>
                <h3 className="card-title">Контекст и нормы</h3>
                <p className="muted">Исходный код целиком, выделение выбранного предложения.</p>
              </div>
              <button
                className="btn btn-primary"
                type="button"
                onClick={() => {
                  handleOpenNormForm();
                  if (selectedAiFinding?.norm_text) {
                    setNormText(selectedAiFinding.norm_text);
                  }
                }}
              >
                Создать норму
              </button>
            </div>

            {lastSuggested && (
              <section className="card" style={{ marginBottom: '1rem' }}>
                <div className="card-header">
                  <div>
                    <h3 className="card-title">Результат автооформления</h3>
                    <p className="muted">
                      Статус: {lastSuggested.status}
                      {lastSuggested.duplicate_of?.length ? (
                        <>
                          {' '}
                          · Дубликат:{' '}
                          {lastSuggested.duplicate_of
                            .map(
                              (dupId) =>
                                `${dupId}${
                                  lastSuggested.duplicate_titles && lastSuggested.duplicate_titles[dupId]
                                    ? ` — ${lastSuggested.duplicate_titles[dupId]}`
                                    : ''
                                }`,
                            )
                            .join(', ')}
                        </>
                      ) : null}
                    </p>
                  </div>
                </div>
                <div style={{ display: 'grid', gap: '0.35rem' }}>
                  <div>
                    <strong>norm_id:</strong> {lastSuggested.generated_norm_id || '—'}
                  </div>
                  <div>
                    <strong>Название:</strong> {lastSuggested.generated_title || '—'}
                  </div>
                  <div>
                    <strong>Раздел:</strong> {lastSuggested.generated_section || lastSuggested.section}
                    {' · '}
                    <strong>Серьёзность:</strong>{' '}
                    {lastSuggested.generated_severity || lastSuggested.severity}
                  </div>
                  <div>
                    <strong>Область:</strong> {lastSuggested.generated_scope || '—'}
                  </div>
                  <div>
                    <strong>Текст нормы:</strong>
                    <div className="muted" style={{ whiteSpace: 'pre-wrap' }}>
                      {lastSuggested.generated_text || lastSuggested.text_raw}
                    </div>
                  </div>
                </div>
              </section>
            )}

            {showNormForm && (
              <section className="card" style={{ marginBottom: '1rem' }}>
                <div className="card-header">
                  <div>
                    <h3 className="card-title">Новая норма</h3>
                    <p className="muted">Заполните обязательные поля и сохраните норму.</p>
                  </div>
                  <button
                    className="btn btn-secondary"
                    type="button"
                    onClick={() => setShowNormForm(false)}
                  >
                    Скрыть
                  </button>
                </div>
                {selectionDraft && (
                  <div style={{ marginBottom: '0.75rem' }}>
                    <p className="muted" style={{ marginBottom: '0.35rem' }}>
                      Пример/контекст:
                    </p>
                    <pre>{selectionDraft.text}</pre>
                  </div>
                )}
                <form onSubmit={handleNormSubmit} className="form-grid" style={{ gap: '1rem' }}>
                  <div className="field">
                    <label htmlFor="norm-section-inline">Раздел</label>
                    <select
                      id="norm-section-inline"
                      value={normSection}
                      onChange={(event) => setNormSection(event.target.value)}
                      disabled={normSectionsQuery.isLoading}
                    >
                      {(normSectionsQuery.data || []).map((section) => (
                        <option key={section} value={section}>
                          {section}
                        </option>
                      ))}
                      {!normSectionsQuery.data?.length && <option value="">Нет данных</option>}
                    </select>
                  </div>
                  <div className="field">
                    <label htmlFor="norm-severity-inline">Серьёзность</label>
                    <select
                      id="norm-severity-inline"
                      value={normSeverity}
                      onChange={(event) =>
                        setNormSeverity(event.target.value as 'critical' | 'major' | 'minor' | 'info')
                      }
                    >
                      <option value="critical">critical</option>
                      <option value="major">major</option>
                      <option value="minor">minor</option>
                      <option value="info">info</option>
                    </select>
                  </div>
                  <div className="field" style={{ gridColumn: '1 / -1' }}>
                    <label htmlFor="norm-text-inline">Текст нормы</label>
                    <textarea
                      id="norm-text-inline"
                      rows={4}
                      value={normText}
                      onChange={(event) => setNormText(event.target.value)}
                      placeholder="Опишите нарушение свободным текстом; LLM оформит норму и проверит дубль."
                    />
                  </div>
                  <button
                    type="submit"
                    className="btn btn-primary"
                    disabled={createNormMutation.isPending}
                  >
                    {createNormMutation.isPending ? 'Сохраняем…' : 'Создать норму'}
                  </button>
                  {isSuggesting && <div className="loader-beeline" aria-label="Ожидаем ответ LLM" />}
                </form>
                {normMessage && (
                  <p className={`alert ${normState === 'success' ? 'alert-success' : 'alert-error'}`}>
                    {normMessage}
                  </p>
                )}
              </section>
            )}

            <div style={{ display: 'grid', gap: '0.75rem', maxHeight: '54vh', overflow: 'auto' }}>
              {runSourcesQuery.error && (
                <p className="alert alert-error">Не удалось загрузить исходный код запуска.</p>
              )}
              {runSourcesQuery.isLoading && <span className="muted">Загружаем исходники…</span>}
              {!runSourcesQuery.isLoading &&
                !runSourcesQuery.error &&
                (runSourcesQuery.data || []).map((source) => (
                  <div key={source.path} style={{ border: '1px solid var(--border)', borderRadius: '0.75rem' }}>
                    <div
                      style={{
                        padding: '0.5rem 0.75rem',
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        background: '#f7f7fb',
                        borderBottom: '1px solid var(--border)',
                      }}
                    >
                      <div>
                        <strong>{source.path}</strong>{' '}
                        <span className="muted">({source.content.split('\n').length} строк)</span>
                      </div>
                    </div>
                    {renderSource(source)}
                  </div>
                ))}
              {!runSourcesQuery.isLoading &&
                !runSourcesQuery.error &&
                !(runSourcesQuery.data || []).length && <div className="empty-state">Исходники не найдены.</div>}
            </div>
          </div>
        </div>
      )}
    </section>
  );

  if (runQuery.isLoading || findingsQuery.isLoading) {
    return (
      <div className="card" style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
        <div className="loader-beeline" aria-label="Загрузка запуска" />
        <div>
          <h2 className="card-title" style={{ margin: 0 }}>
            Загружаем запуск…
          </h2>
          <p className="muted" style={{ margin: 0 }}>
            Получаем данные запуска и предложения LLM
          </p>
        </div>
      </div>
    );
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

  function handleAiStatusChange(
    findingId: string,
    status: AIFindingStatus,
    reviewerComment?: string,
  ) {
    if (!canEditRun) {
      return;
    }
    updateAiFinding.mutate({ findingId, status, reviewerComment });
  }

  function handleOpenNormForm() {
    const selection = window.getSelection();
    if (!selection || selection.isCollapsed) {
      setNormMessage('Сначала выделите фрагмент кода в блоке исходников.');
      setNormState('error');
      return;
    }
    const rawText = selection.toString().trim();
    if (!rawText) {
      setNormMessage('Сначала выделите фрагмент кода в блоке исходников.');
      setNormState('error');
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
      setNormMessage('Выделите код внутри блока исходников справа от предложений.');
      setNormState('error');
      return;
    }
    const file = container.getAttribute('data-source-path');
    const lineStartAttr = container.getAttribute('data-line-start');
    const lineEndAttr = container.getAttribute('data-line-end');
    const lines = rawText
      .split('\n')
      .map((line) => {
        const match = line.match(/^\s*(\d+)\s*:/);
        return match ? Number(match[1]) : null;
      })
      .filter((value): value is number => value !== null);
    const lineStart = lines.length
      ? Math.min(...lines)
      : lineStartAttr
      ? Number(lineStartAttr)
      : null;
    const lineEnd = lines.length
      ? Math.max(...lines)
      : lineEndAttr
      ? Number(lineEndAttr)
      : null;
    const text = rawText.length > 4000 ? `${rawText.slice(0, 4000)}…` : rawText;
    const draft = { text, file, lineStart, lineEnd };
    setSelectionDraft(draft);
    setNormMessage(null);
    setNormState('idle');
    setShowNormForm(true);
  }

  async function handleNormSubmit(event: FormEvent) {
    event.preventDefault();
    if (!canTeach) return;
    setNormMessage(null);
    setNormState('idle');
    setIsSuggesting(true);
    if (!normSection || !normText) {
      setNormMessage('Заполните раздел и текст нормы.');
      setNormState('error');
      setIsSuggesting(false);
      return;
    }
    try {
      const result = await createNormMutation.mutateAsync({
        section: normSection.trim(),
        severity: normSeverity,
        text: normText.trim(),
      });
      setLastSuggested(result);
      setNormMessage(
        result.status === 'rejected_duplicate'
          ? 'Норма отклонена как дубликат. Проверьте существующие правила.'
          : 'Норма оформлена. Можно перезапустить анализ для применения.',
      );
      setNormState('success');
      setNormSection('');
      setNormText('');
      setShowNormForm(false);
    } catch (error) {
      console.error('Failed to create norm', error);
      setNormMessage('Не удалось создать норму.');
      setNormState('error');
    }
    setIsSuggesting(false);
  }

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
    const targetId = isEvaluationRun && evaluationOf ? evaluationOf : id;
    if (
      window.confirm(
        isEvaluationRun
          ? 'Перезапустить базовый запуск? Текущие findings, логи и артефакты будут очищены.'
          : 'Перезапустить запуск? Текущие findings, логи и артефакты будут очищены.',
      )
    ) {
      rerunMutation.mutate(targetId);
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
            {rerunMutation.isPending
              ? 'Перезапускаем…'
              : isEvaluationRun
                ? 'Перезапустить базовый запуск'
                : 'Перезапустить'}
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
            <strong>{displayFindingsCount}</strong>
            <div className="pill-row">
              {(['critical', 'major', 'minor', 'warning', 'info'] as const)
                .filter((level) => severityCounts[level] > 0)
                .map((level) => (
                  <span key={level} className={`status-pill ${level}`}>
                    {level}: {severityCounts[level]}
                  </span>
                ))}
              {!displayFindingsCount && <span className="muted">Пока нет</span>}
            </div>
          </div>
          <div>
            <p className="muted">Предложения LLM</p>
            <strong>{aiCountSummary}</strong>
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

      <div className="tabs sticky-tabs">
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
          {!isCombinedView && (
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
                      <div
                        key={item.finding.id}
                        onClick={() => handleSelectStaticFinding(item.finding)}
                        style={{
                          border:
                            selectedFindingKey === item.finding.id
                              ? '1px solid var(--primary)'
                              : undefined,
                          borderRadius: '0.75rem',
                          padding: '0.25rem',
                        }}
                      >
                        <FindingCard
                          finding={item.finding}
                          sequence={findingOrderMap.get(item.finding.id)}
                          showContext={showFindingsContext}
                          sourceLookup={showFindingsContext ? sourceLookup : null}
                        />
                      </div>
                    );
                  }
                  return (
                    <div
                      key={`group-${item.group.base.id}`}
                      onClick={() => handleSelectStaticFinding(item.group.base, item.group.items)}
                      style={{
                        border:
                          selectedFindingKey === item.group.base.id
                            ? '1px solid var(--primary)'
                            : undefined,
                        borderRadius: '0.75rem',
                        padding: '0.25rem',
                      }}
                    >
                      <FindingGroupCard
                        base={item.group.base}
                        items={item.group.items}
                        sequence={findingOrderMap.get(item.group.base.id)}
                        showContext={showFindingsContext}
                        sourceLookup={showFindingsContext ? sourceLookup : null}
                      />
                    </div>
                  );
                })}
                {!displayFindings.length && (
                  <div className="empty-state">Нет нарушений под текущий фильтр.</div>
                )}
              </div>
            </section>
          )}

          {isCombinedView && aiSection}

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

      {activeTab === 'ai' && !isCombinedView && aiSection}

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

      {activeTab === 'evaluation' && isAdmin && (
        <section className="card" style={{ marginBottom: '1.5rem' }}>
          <div className="card-header">
            <div>
              <h2 className="card-title">Проверка детерминизма</h2>
              <p className="muted">
                Отдельный режим для администратора: повторяемость выбора норм на одном и том же коде.
              </p>
            </div>
          </div>
          <div className="section-grid" style={{ marginBottom: '1rem' }}>
            <label className="field">
              <span>Количество прогонов (2–20)</span>
              <input
                type="number"
                min={2}
                max={20}
                value={selectionRuns}
                onChange={(event) => setSelectionRuns(Number(event.target.value || 2))}
              />
            </label>
            <div style={{ display: 'flex', alignItems: 'flex-end' }}>
              <button
                className="btn btn-primary"
                type="button"
                onClick={() => evaluationMutation.mutate()}
                disabled={evaluationMutation.isPending || !id}
              >
                {evaluationMutation.isPending ? 'Запускаем...' : 'Запустить проверку'}
              </button>
            </div>
          </div>
          {evaluationQuery.isLoading && <p className="muted">Загружаем результаты...</p>}
          {evaluationQuery.error && (
            <p className="alert alert-error">Не удалось загрузить отчет проверки.</p>
          )}
          {evaluationQuery.data?.status && (
            <p className="muted">
              Статус последнего прогона: <strong>{evaluationQuery.data.status}</strong>
            </p>
          )}
          {evaluationQuery.data?.evaluation_run_id && (
            <p className="muted">ID запуска проверки: {evaluationQuery.data.evaluation_run_id}</p>
          )}
          {evaluationComparison && (
            <div className="section-grid" style={{ marginTop: '0.75rem' }}>
              <div>
                <p className="muted">Baseline Jaccard</p>
                <strong>{evaluationComparison.baseline.toFixed(3)}</strong>
              </div>
              <div>
                <p className="muted">Prefiltered Jaccard</p>
                <strong>{evaluationComparison.prefiltered.toFixed(3)}</strong>
              </div>
              <div>
                <p className="muted">Итог</p>
                <strong>{evaluationComparison.verdict}</strong>
              </div>
            </div>
          )}
          {evaluationQuery.data?.report ? (
            <pre className="json-preview" style={{ marginTop: '1rem' }}>
              {JSON.stringify(evaluationQuery.data.report, null, 2)}
            </pre>
          ) : (
            !evaluationQuery.isLoading && (
              <div className="empty-state">Отчет пока не сформирован.</div>
            )
          )}
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
