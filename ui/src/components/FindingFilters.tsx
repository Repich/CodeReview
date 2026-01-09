interface Props {
  severity: string;
  setSeverity: (value: string) => void;
  query: string;
  setQuery: (value: string) => void;
}

function FindingFilters({ severity, setSeverity, query, setQuery }: Props) {
  return (
    <div className="form-grid" style={{ marginBottom: '1rem' }}>
      <div className="field">
        <label htmlFor="severity">Severity</label>
        <select id="severity" value={severity} onChange={(event) => setSeverity(event.target.value)}>
          <option value="">Все</option>
          <option value="critical">Critical</option>
          <option value="major">Major</option>
          <option value="minor">Minor</option>
          <option value="info">Info</option>
        </select>
      </div>
      <div className="field">
        <label htmlFor="finding-query">Поиск</label>
        <input
          id="finding-query"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Текст или norm_id"
        />
      </div>
    </div>
  );
}

export default FindingFilters;
