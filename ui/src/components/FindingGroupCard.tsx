import type { Finding } from '../services/api';

interface Props {
  base: Finding;
  items: Finding[];
  sequence?: number;
  showContext?: boolean;
  sourceLookup?: Map<string, string[]> | null;
}

const formatLineList = (lines: number[]) => {
  const unique = Array.from(new Set(lines)).filter((value) => Number.isFinite(value));
  unique.sort((a, b) => a - b);
  const preview = unique.slice(0, 20);
  const suffix = unique.length > 20 ? ` … +${unique.length - 20}` : '';
  return `${preview.join(', ')}${suffix}`;
};

const buildLineSnippets = (sourceLines: string[], lineNumbers: number[]) => {
  const unique = Array.from(new Set(lineNumbers)).filter((value) => Number.isFinite(value));
  unique.sort((a, b) => a - b);
  return unique
    .map((lineNo) => `${lineNo}: ${sourceLines[lineNo - 1] ?? ''}`)
    .join('\n')
    .trimEnd();
};

function FindingGroupCard({ base, items, sequence, showContext, sourceLookup }: Props) {
  const files = new Map<string, number[]>();
  items.forEach((item) => {
    if (!item.file_path) return;
    const lines = files.get(item.file_path) ?? [];
    if (item.line_start) {
      lines.push(item.line_start);
    }
    files.set(item.file_path, lines);
  });

  const contextBlocks = showContext && sourceLookup
    ? [...files.entries()]
        .map(([path, lines]) => {
          const sourceLines = sourceLookup.get(path);
          if (!sourceLines) return null;
          const snippet = buildLineSnippets(sourceLines, lines);
          if (!snippet) return null;
          return { path, snippet };
        })
        .filter((entry): entry is { path: string; snippet: string } => Boolean(entry))
    : [];

  return (
    <article className="card finding-card">
      <div className="card-header" style={{ marginBottom: '0.5rem' }}>
        <div>
          <strong>
            {sequence ? `#${sequence} · ` : ''}
            {base.norm_id}
          </strong>
          {base.norm_title && (
            <p className="muted" style={{ margin: 0 }}>
              {base.norm_title}
            </p>
          )}
          <p className="muted" style={{ margin: 0 }}>
            {base.detector_id}
          </p>
        </div>
        <span className={`status-pill ${base.severity}`}>{base.severity}</span>
      </div>

      <p style={{ marginTop: 0 }}>{base.message}</p>
      <p className="muted" style={{ marginBottom: '0.5rem' }}>
        Вхождений: {items.length}
      </p>

      {files.size > 0 && (
        <details>
          <summary>Расположение</summary>
          {[...files.entries()].map(([path, lines]) => (
            <p key={path} className="muted" style={{ margin: '0.25rem 0' }}>
              {path}: {formatLineList(lines)}
            </p>
          ))}
        </details>
      )}
      {contextBlocks.length > 0 && (
        <details open>
          <summary>Контекст</summary>
          {contextBlocks.map((block) => (
            <div key={block.path} style={{ marginTop: '0.5rem' }}>
              <p className="muted" style={{ margin: '0.25rem 0' }}>
                {block.path}
              </p>
              <pre data-source-path={block.path}>{block.snippet}</pre>
            </div>
          ))}
        </details>
      )}

      {(base.norm_text || base.norm_section) && (
        <details>
          <summary>Описание нормы</summary>
          {base.norm_section && (
            <p className="muted" style={{ margin: '0.25rem 0' }}>
              Раздел: {base.norm_section}
            </p>
          )}
          {base.norm_text && <p style={{ whiteSpace: 'pre-wrap' }}>{base.norm_text}</p>}
        </details>
      )}

      {(base.norm_source_reference || base.norm_source_excerpt) && (
        <details>
          <summary>Источник нормы</summary>
          {base.norm_source_reference && (
            <p className="muted" style={{ marginTop: '0.25rem' }}>
              {base.norm_source_reference}
            </p>
          )}
          {base.norm_source_excerpt && (
            <p style={{ whiteSpace: 'pre-wrap' }}>{base.norm_source_excerpt}</p>
          )}
        </details>
      )}
    </article>
  );
}

export default FindingGroupCard;
