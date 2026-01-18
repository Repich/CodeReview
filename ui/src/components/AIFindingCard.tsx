import type { AIFinding, AIFindingEvidence, AIFindingStatus } from '../services/api';

interface Props {
  finding: AIFinding;
  onChangeStatus?: (status: AIFindingStatus, reviewerComment?: string) => void;
  isUpdating?: boolean;
  sequence?: number;
  readOnly?: boolean;
  sourceLookup?: Map<string, string[]> | null;
}

const statusLabels: Record<AIFindingStatus, string> = {
  suggested: 'Предложено',
  pending: 'В ожидании',
  confirmed: 'Подтверждено',
  rejected: 'Отклонено',
};

const statusClassName: Record<AIFindingStatus, string> = {
  suggested: 'status-pill info',
  pending: 'status-pill queued',
  confirmed: 'status-pill completed',
  rejected: 'status-pill failed',
};

const parseLineRange = (value?: string | null) => {
  if (!value) return null;
  const match = value.match(/(\d+)(?:\s*-\s*(\d+))?/);
  if (!match) return null;
  const start = Number(match[1]);
  const end = match[2] ? Number(match[2]) : start;
  if (Number.isNaN(start) || Number.isNaN(end)) return null;
  return { start, end };
};

const resolveEvidenceTarget = (item: AIFindingEvidence) => {
  let file = item.file ?? '';
  let lines = item.lines ?? '';
  if (!file && lines.includes(':')) {
    const parts = lines.split(':');
    file = parts.slice(0, -1).join(':').trim();
    lines = parts[parts.length - 1].trim();
  }
  return { file, range: parseLineRange(lines) };
};

const buildSnippet = (sourceLines: string[], start: number, end: number) => {
  const safeStart = Math.max(1, start);
  const safeEnd = Math.min(end, sourceLines.length);
  const slice = sourceLines.slice(safeStart - 1, safeEnd);
  return slice
    .map((line, index) => `${safeStart + index}: ${line}`)
    .join('\n')
    .trimEnd();
};

function AIFindingCard({
  finding,
  onChangeStatus,
  isUpdating,
  sequence,
  readOnly,
  sourceLookup,
}: Props) {
  const handleStatusChange = (status: AIFindingStatus) => {
    if (isUpdating || readOnly) return;
    if (status === 'confirmed' || status === 'rejected') {
      const promptLabel =
        status === 'confirmed'
          ? 'Комментарий к подтверждению (опционально)'
          : 'Комментарий к отклонению (опционально)';
      const comment = window.prompt(promptLabel, finding.reviewer_comment ?? '');
      if (comment === null) {
        return;
      }
      onChangeStatus?.(status, comment.trim() || undefined);
      return;
    }
    onChangeStatus?.(status);
  };

  return (
    <article className="card finding-card">
      <div className="card-header" style={{ marginBottom: '0.5rem' }}>
        <div>
          <strong>
            {sequence ? `#${sequence} · ` : ''}
            {finding.norm_id || 'Новая норма'}
          </strong>
          <p className="muted" style={{ margin: 0 }}>
            {finding.section || 'Без раздела'}
            {finding.category ? ` · ${finding.category}` : null}
          </p>
        </div>
        <span className={statusClassName[finding.status]}>{statusLabels[finding.status]}</span>
      </div>

      <p style={{ marginTop: 0, whiteSpace: 'pre-line' }}>{finding.norm_text}</p>

      {(finding.source_reference || finding.norm_source_reference || finding.norm_source_excerpt) && (
        <details style={{ marginBottom: '0.5rem' }}>
          <summary>Источник нормы</summary>
          {finding.source_reference && (
            <p className="muted" style={{ marginTop: '0.25rem' }}>
              LLM: {finding.source_reference}
            </p>
          )}
          {finding.norm_source_reference && (
            <p className="muted" style={{ marginTop: '0.25rem' }}>
              Официально: {finding.norm_source_reference}
            </p>
          )}
          {finding.norm_source_excerpt && (
            <p style={{ whiteSpace: 'pre-wrap' }}>{finding.norm_source_excerpt}</p>
          )}
        </details>
      )}

      {finding.reviewer_comment && (
        <div className="muted" style={{ marginBottom: '0.75rem' }}>
          <strong style={{ display: 'block', marginBottom: '0.25rem' }}>Комментарий</strong>
          <p style={{ margin: 0, whiteSpace: 'pre-line' }}>{finding.reviewer_comment}</p>
        </div>
      )}

      {finding.evidence && finding.evidence.length > 0 && (
        <div className="muted" style={{ marginBottom: '0.75rem' }}>
          <strong style={{ display: 'block', marginBottom: '0.25rem' }}>Контекст</strong>
          <ul style={{ margin: 0, paddingInlineStart: '1.25rem' }}>
            {finding.evidence.map((item, index) => {
              const { file, range } = resolveEvidenceTarget(item);
              const sourceLines = file ? sourceLookup?.get(file) : undefined;
              const snippet =
                sourceLines && range ? buildSnippet(sourceLines, range.start, range.end) : null;

              return (
                <li key={index}>
                  {[item.file, item.lines].filter(Boolean).join(': ')} —{' '}
                  {item.reason || 'Без описания'}
                  {snippet && (
                    <details style={{ marginTop: '0.35rem' }}>
                      <summary>Фрагмент кода</summary>
                      <pre data-source-path={file || undefined}>{snippet}</pre>
                    </details>
                  )}
                </li>
              );
            })}
          </ul>
        </div>
      )}

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
        <button
          type="button"
          className="btn btn-primary"
          onClick={() => handleStatusChange('confirmed')}
          disabled={isUpdating || readOnly || finding.status === 'confirmed'}
        >
          Подтвердить
        </button>
        <button
          type="button"
          className="btn btn-secondary"
          onClick={() => handleStatusChange('pending')}
          disabled={isUpdating || readOnly || finding.status === 'pending'}
        >
          В ожидание
        </button>
        <button
          type="button"
          className="btn btn-ghost"
          onClick={() => handleStatusChange('rejected')}
          disabled={isUpdating || readOnly || finding.status === 'rejected'}
        >
          Отклонить
        </button>
      </div>
    </article>
  );
}

export default AIFindingCard;
