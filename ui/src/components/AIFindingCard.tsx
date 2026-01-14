import type { AIFinding, AIFindingStatus } from '../services/api';

interface Props {
  finding: AIFinding;
  onChangeStatus?: (status: AIFindingStatus, reviewerComment?: string) => void;
  isUpdating?: boolean;
  sequence?: number;
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

function AIFindingCard({ finding, onChangeStatus, isUpdating, sequence }: Props) {
  const handleStatusChange = (status: AIFindingStatus) => {
    if (isUpdating) return;
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
            {finding.evidence.map((item, index) => (
              <li key={index}>
                {[item.file, item.lines].filter(Boolean).join(': ')} — {item.reason || 'Без описания'}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
        <button
          type="button"
          className="btn btn-primary"
          onClick={() => handleStatusChange('confirmed')}
          disabled={isUpdating || finding.status === 'confirmed'}
        >
          Подтвердить
        </button>
        <button
          type="button"
          className="btn btn-secondary"
          onClick={() => handleStatusChange('pending')}
          disabled={isUpdating || finding.status === 'pending'}
        >
          В ожидание
        </button>
        <button
          type="button"
          className="btn btn-ghost"
          onClick={() => handleStatusChange('rejected')}
          disabled={isUpdating || finding.status === 'rejected'}
        >
          Отклонить
        </button>
      </div>
    </article>
  );
}

export default AIFindingCard;
