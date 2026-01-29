import { useMemo, useState } from 'react';
import {
  fetchRawSourceContent,
  fetchRawSourcesIndex,
  getStoredAuthToken,
} from '../services/api';
import type { IOLogEntry, RawSourceEntry } from '../services/api';

interface Props {
  artifacts: IOLogEntry[];
  artifactBaseUrl?: string;
}

const humanSize = (size?: number | null) => {
  if (!size) return '—';
  const kb = size / 1024;
  if (kb < 1024) return `${kb.toFixed(1)} KB`;
  return `${(kb / 1024).toFixed(2)} MB`;
};

function ArtifactsTable({ artifacts, artifactBaseUrl }: Props) {
  if (!artifacts.length) {
    return <p className="muted">Артефактов пока нет.</p>;
  }

  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewTitle, setPreviewTitle] = useState('');
  const [previewContent, setPreviewContent] = useState('');
  const [previewKind, setPreviewKind] = useState<'text' | 'json'>('text');
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [sourcesOpen, setSourcesOpen] = useState(false);
  const [sourcesList, setSourcesList] = useState<RawSourceEntry[]>([]);
  const [sourcesLoading, setSourcesLoading] = useState(false);
  const [sourcesError, setSourcesError] = useState<string | null>(null);
  const [sourceContent, setSourceContent] = useState('');
  const [sourcePath, setSourcePath] = useState<string | null>(null);
  const [sourceLoading, setSourceLoading] = useState(false);

  const buildUrl = (artifact: IOLogEntry) => {
    const base = artifactBaseUrl || (import.meta.env.VITE_API_BASE || 'http://localhost:8000/api');
    const url = new URL(`${base}/audit/io/${artifact.id}/download`);
    const token = getStoredAuthToken();
    if (token) {
      url.searchParams.set('token', token);
    }
    return url.toString();
  };

  const isPreviewable = (artifact: IOLogEntry) => {
    const path = artifact.storage_path.toLowerCase();
    return path.endsWith('.txt') || path.endsWith('.json');
  };

  const isRawSources = (artifact: IOLogEntry) => artifact.artifact_type === 'sources_raw.zip';

  const handleOpenRawSources = async (artifact: IOLogEntry) => {
    setSourcesError(null);
    setSourcesLoading(true);
    setSourcesOpen(true);
    setSourcesList([]);
    setSourceContent('');
    setSourcePath(null);
    try {
      const data = await fetchRawSourcesIndex(artifact.review_run_id);
      setSourcesList(data);
    } catch (error) {
      console.error('Failed to load raw sources index', error);
      setSourcesError('Не удалось загрузить список исходников.');
    } finally {
      setSourcesLoading(false);
    }
  };

  const handleSelectRawSource = async (artifact: IOLogEntry, path: string) => {
    setSourcePath(path);
    setSourceLoading(true);
    setSourceContent('');
    try {
      const data = await fetchRawSourceContent(artifact.review_run_id, path);
      setSourceContent(data.content || '');
    } catch (error) {
      console.error('Failed to load raw source', error);
      setSourcesError('Не удалось загрузить исходник.');
    } finally {
      setSourceLoading(false);
    }
  };

  const handlePreview = async (artifact: IOLogEntry) => {
    setPreviewError(null);
    setPreviewLoading(true);
    setPreviewOpen(true);
    setPreviewTitle(artifact.storage_path);
    const url = buildUrl(artifact);
    try {
      const response = await fetch(url, { credentials: 'include' });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const text = await response.text();
      const lower = artifact.storage_path.toLowerCase();
      if (lower.endsWith('.json')) {
        setPreviewKind('json');
        setPreviewContent(text);
      } else {
        setPreviewKind('text');
        setPreviewContent(text);
      }
    } catch (error) {
      console.error('Failed to load artifact', error);
      setPreviewError('Не удалось загрузить артефакт для просмотра.');
    } finally {
      setPreviewLoading(false);
    }
  };

  return (
    <>
      <div className="table-container">
        <table className="table">
          <thead>
            <tr>
              <th>Тип</th>
              <th>Направление</th>
              <th>Размер</th>
              <th>SHA256</th>
              <th>Создан</th>
              <th>Действие</th>
            </tr>
          </thead>
          <tbody>
            {artifacts.map((artifact) => (
              <tr key={artifact.id}>
                <td>{artifact.artifact_type}</td>
                <td>{artifact.direction}</td>
                <td>{humanSize(artifact.size_bytes ?? undefined)}</td>
                <td>
                  <code>{artifact.checksum ?? '—'}</code>
                </td>
                <td>{new Date(artifact.created_at).toLocaleString()}</td>
                <td>
                  <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
                    <a href={buildUrl(artifact)} target="_blank" rel="noreferrer">
                      Скачать
                    </a>
                    {isPreviewable(artifact) && (
                      <button
                        type="button"
                        className="link-button"
                        onClick={() => handlePreview(artifact)}
                      >
                        Просмотр
                      </button>
                    )}
                    {isRawSources(artifact) && (
                      <button
                        type="button"
                        className="link-button"
                        onClick={() => handleOpenRawSources(artifact)}
                      >
                        Просмотр
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {previewOpen && (
        <ArtifactPreviewModal
          title={previewTitle}
          content={previewContent}
          kind={previewKind}
          loading={previewLoading}
          error={previewError}
          onClose={() => setPreviewOpen(false)}
        />
      )}
      {sourcesOpen && (
        <RawSourcesModal
          title="Исходный код (sources_raw.zip)"
          sources={sourcesList}
          loading={sourcesLoading}
          error={sourcesError}
          selectedPath={sourcePath}
          content={sourceContent}
          loadingContent={sourceLoading}
          onSelect={(path) => {
            const artifact = artifacts.find((item) => isRawSources(item));
            if (artifact) {
              handleSelectRawSource(artifact, path);
            }
          }}
          onClose={() => setSourcesOpen(false)}
        />
      )}
    </>
  );
}

export default ArtifactsTable;

function ArtifactPreviewModal({
  title,
  content,
  kind,
  loading,
  error,
  onClose,
}: {
  title: string;
  content: string;
  kind: 'text' | 'json';
  loading: boolean;
  error: string | null;
  onClose: () => void;
}) {
  const [copied, setCopied] = useState(false);
  const formattedJson = useMemo(() => {
    if (kind !== 'json') return '';
    try {
      const parsed = JSON.parse(content);
      const pretty = JSON.stringify(parsed, null, 2);
      return highlightJson(pretty);
    } catch (err) {
      return highlightJson(content);
    }
  }, [content, kind]);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch (copyError) {
      console.error('Failed to copy artifact content', copyError);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(event) => event.stopPropagation()}>
        <div className="modal-header">
          <div>
            <strong>Просмотр артефакта</strong>
            <p className="muted" style={{ margin: 0 }}>
              {title}
            </p>
          </div>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={handleCopy}
              disabled={loading || Boolean(error) || !content}
            >
              {copied ? 'Скопировано' : 'Копировать'}
            </button>
            <button type="button" className="btn btn-secondary" onClick={onClose}>
              Закрыть
            </button>
          </div>
        </div>
        {loading && <p className="muted">Загружаем...</p>}
        {error && <p className="alert alert-error">{error}</p>}
        {!loading && !error && (
          <div className="preview-body">
            {kind === 'json' ? (
              <pre
                className="json-preview"
                dangerouslySetInnerHTML={{ __html: formattedJson }}
              />
            ) : (
              <pre className="text-preview">{content}</pre>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function RawSourcesModal({
  title,
  sources,
  loading,
  error,
  selectedPath,
  content,
  loadingContent,
  onSelect,
  onClose,
}: {
  title: string;
  sources: RawSourceEntry[];
  loading: boolean;
  error: string | null;
  selectedPath: string | null;
  content: string;
  loadingContent: boolean;
  onSelect: (path: string) => void;
  onClose: () => void;
}) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    if (!content) return;
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch (copyError) {
      console.error('Failed to copy raw source content', copyError);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(event) => event.stopPropagation()}>
        <div className="modal-header">
          <div>
            <strong>{title}</strong>
            <p className="muted" style={{ margin: 0 }}>
              {sources.length} файлов
            </p>
          </div>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={handleCopy}
              disabled={loadingContent || !content}
            >
              {copied ? 'Скопировано' : 'Копировать'}
            </button>
            <button type="button" className="btn btn-secondary" onClick={onClose}>
              Закрыть
            </button>
          </div>
        </div>
        <div className="raw-sources-layout">
          <aside className="raw-sources-list">
            {loading && <p className="muted">Загружаем список...</p>}
            {error && <p className="alert alert-error">{error}</p>}
            {!loading &&
              !error &&
              sources.map((item) => (
                <button
                  key={item.path}
                  type="button"
                  className={`raw-source-item ${selectedPath === item.path ? 'active' : ''}`}
                  onClick={() => onSelect(item.path)}
                >
                  <span>{item.path}</span>
                  <span className="muted">{(item.size / 1024).toFixed(1)} KB</span>
                </button>
              ))}
            {!loading && !error && !sources.length && (
              <div className="empty-state">Файлы не найдены.</div>
            )}
          </aside>
          <section className="raw-sources-content">
            {loadingContent && <p className="muted">Загружаем файл...</p>}
            {!loadingContent && selectedPath && (
              <pre className="text-preview">{content || 'Пустой файл.'}</pre>
            )}
            {!loadingContent && !selectedPath && (
              <div className="empty-state">Выберите файл слева.</div>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}

const JSON_TOKEN_RE =
  /("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(?:\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d+)?(?:[eE][+\-]?\d+)?)/g;

function escapeHtml(value: string) {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function highlightJson(value: string) {
  let result = '';
  let lastIndex = 0;
  for (const match of value.matchAll(JSON_TOKEN_RE)) {
    const index = match.index ?? 0;
    if (index > lastIndex) {
      result += escapeHtml(value.slice(lastIndex, index));
    }
    const token = match[0];
    let cls = 'json-number';
    if (token.startsWith('"')) {
      cls = token.endsWith(':') ? 'json-key' : 'json-string';
    } else if (token === 'true' || token === 'false') {
      cls = 'json-boolean';
    } else if (token === 'null') {
      cls = 'json-null';
    }
    result += `<span class="${cls}">${escapeHtml(token)}</span>`;
    lastIndex = index + token.length;
  }
  if (lastIndex < value.length) {
    result += escapeHtml(value.slice(lastIndex));
  }
  return result;
}
