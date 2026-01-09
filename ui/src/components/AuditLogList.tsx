import type { AuditLog } from '../services/api';

interface Props {
  logs: AuditLog[];
}

function AuditLogList({ logs }: Props) {
  if (!logs.length) {
    return <p className="muted">Журнал событий пуст.</p>;
  }

  return (
    <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
      {logs.map((log) => (
        <li key={log.id} className="card" style={{ padding: '1rem', marginBottom: '0.75rem' }}>
          <div className="card-header" style={{ marginBottom: '0.3rem' }}>
            <strong>{log.event_type}</strong>
            <time dateTime={log.created_at} className="muted">
              {new Date(log.created_at).toLocaleString()}
            </time>
          </div>
          {log.actor && <p className="muted" style={{ marginTop: 0 }}>Актор: {log.actor}</p>}
          {log.payload && (
            <details>
              <summary>Payload</summary>
              <pre>{JSON.stringify(log.payload, null, 2)}</pre>
            </details>
          )}
        </li>
      ))}
    </ul>
  );
}

export default AuditLogList;
