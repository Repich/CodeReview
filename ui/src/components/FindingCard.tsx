import { Finding } from '../services/api';

interface Props {
  finding: Finding;
  sequence?: number;
  showContext?: boolean;
  sourceLookup?: Map<string, string[]> | null;
}

const buildSnippet = (sourceLines: string[], start: number, end: number) => {
  const safeStart = Math.max(1, start);
  const safeEnd = Math.min(end, sourceLines.length);
  const slice = sourceLines.slice(safeStart - 1, safeEnd);
  return slice
    .map((line, index) => `${safeStart + index}: ${line}`)
    .join('\n')
    .trimEnd();
};

function FindingCard({ finding, sequence, showContext, sourceLookup }: Props) {
  const contextSnippet = (() => {
    if (!showContext || !sourceLookup || !finding.file_path || !finding.line_start) {
      return null;
    }
    const sourceLines = sourceLookup.get(finding.file_path);
    if (!sourceLines) return null;
    const endLine = finding.line_end ?? finding.line_start;
    return buildSnippet(sourceLines, finding.line_start, endLine);
  })();

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
      {contextSnippet && (
        <details open>
          <summary>Контекст</summary>
          <pre data-source-path={finding.file_path || undefined}>{contextSnippet}</pre>
        </details>
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
