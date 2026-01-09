import type { FeedbackEntry } from '../services/api';

interface Props {
  items: FeedbackEntry[];
}

function verdictLabel(verdict: string) {
  switch (verdict) {
    case 'tp':
      return 'True positive';
    case 'fp':
      return 'False positive';
    case 'fn':
      return 'False negative';
    case 'skip':
      return 'Пропущено';
    default:
      return verdict;
  }
}

function FeedbackList({ items }: Props) {
  if (!items.length) {
    return <p className="muted">Отзывов пока нет.</p>;
  }

  return (
    <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
      {items.map((feedback) => (
        <li key={feedback.id} className="card" style={{ padding: '1rem', marginBottom: '0.75rem' }}>
          <div className="card-header" style={{ marginBottom: '0.4rem' }}>
            <strong>{feedback.reviewer}</strong>
            <span className="status-pill info">{verdictLabel(feedback.verdict)}</span>
          </div>
          {feedback.comment && <p style={{ marginTop: 0 }}>{feedback.comment}</p>}
          <p className="muted" style={{ marginTop: '0.4rem' }}>
            Finding: {feedback.finding_id} • {new Date(feedback.created_at).toLocaleString()}
          </p>
        </li>
      ))}
    </ul>
  );
}

export default FeedbackList;
