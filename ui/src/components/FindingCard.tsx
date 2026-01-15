import { Finding } from '../services/api';

interface Props {
  finding: Finding;
  sequence?: number;
}

function FindingCard({ finding, sequence }: Props) {
  return (
    <article className="card finding-card">
      <div className="card-header" style={{ marginBottom: '0.5rem' }}>
        <div>
          <strong>
            {sequence ? `#${sequence} · ` : ''}
            {finding.norm_id}
          </strong>
          {finding.norm_title && (
            <p className="muted" style={{ margin: 0 }}>
              {finding.norm_title}
            </p>
          )}
          <p className="muted" style={{ margin: 0 }}>
            {finding.detector_id}
          </p>
        </div>
        <span className={`status-pill ${finding.severity}`}>{finding.severity}</span>
      </div>
      <p style={{ marginTop: 0 }}>{finding.message}</p>
      {finding.file_path && (
        <p className="muted" style={{ marginBottom: '0.5rem' }}>
          {finding.file_path}:{finding.line_start ?? '?'}
        </p>
      )}
      {finding.code_snippet && (
        <pre>{finding.code_snippet}</pre>
      )}
      {(finding.norm_text || finding.norm_section) && (
        <details>
          <summary>Описание нормы</summary>
          {finding.norm_section && (
            <p className="muted" style={{ margin: '0.25rem 0' }}>
              Раздел: {finding.norm_section}
            </p>
          )}
          {finding.norm_text && (
            <p style={{ whiteSpace: 'pre-wrap' }}>{finding.norm_text}</p>
          )}
        </details>
      )}
      {(finding.norm_source_reference || finding.norm_source_excerpt) && (
        <details>
          <summary>Источник нормы</summary>
          {finding.norm_source_reference && (
            <p className="muted" style={{ marginTop: '0.25rem' }}>
              {finding.norm_source_reference}
            </p>
          )}
          {finding.norm_source_excerpt && (
            <p style={{ whiteSpace: 'pre-wrap' }}>{finding.norm_source_excerpt}</p>
          )}
        </details>
      )}
      {finding.context && (
        <details>
          <summary>Context</summary>
          <pre>{JSON.stringify(finding.context, null, 2)}</pre>
        </details>
      )}
    </article>
  );
}

export default FindingCard;
