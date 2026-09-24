import { useEffect, useState } from 'react';
import { getSystemFlaggedAttempts } from '../../api/client';
import { formatTimestamp, summarizeFailedChecks } from '../../utils/formatters';
import './FlaggedAttemptsPanel.css';

export default function FlaggedAttemptsPanel() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  async function refresh() {
    try {
      const result = await getSystemFlaggedAttempts();
      setData(result);
      setError(null);
    } catch (e) {
      setError(e.message);
    }
  }

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, 8000);
    return () => clearInterval(interval);
  }, []);

  if (error) {
    return <div className="panel"><p className="panel-error">{error}</p></div>;
  }
  if (!data) {
    return <div className="panel"><p className="panel-empty">Loading…</p></div>;
  }

  return (
    <div className="panel">
      <div className="flagged-header">
        <p className="panel-eyebrow" style={{ margin: 0 }}>Flagged Access Attempts</p>
        <span className="flagged-count">{data.total_flagged}</span>
      </div>

      {data.recent.length === 0 && (
        <p className="panel-empty" style={{ marginTop: 12 }}>No flagged attempts recorded.</p>
      )}

      <ul className="flagged-list">
        {data.recent.map((attempt, i) => (
          <li key={i} className="flagged-item">
            <div className="flagged-item-top">
              <span className="flagged-action">{attempt.action}</span>
              <span className="flagged-time">{formatTimestamp(attempt.timestamp)}</span>
            </div>
            <div className="flagged-reason">{summarizeFailedChecks(attempt)}</div>
          </li>
        ))}
      </ul>
    </div>
  );
}