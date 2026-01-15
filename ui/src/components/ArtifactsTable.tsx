import { getStoredAuthToken } from '../services/api';
import type { IOLogEntry } from '../services/api';

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

  const buildUrl = (artifact: IOLogEntry) => {
    const base = artifactBaseUrl || (import.meta.env.VITE_API_BASE || 'http://localhost:8000/api');
    const url = new URL(`${base}/audit/io/${artifact.id}/download`);
    const token = getStoredAuthToken();
    if (token) {
      url.searchParams.set('token', token);
    }
    return url.toString();
  };

  return (
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
                <a href={buildUrl(artifact)} target="_blank" rel="noreferrer">
                  Скачать
                </a>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default ArtifactsTable;
