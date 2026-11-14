import { useEffect, useState } from 'react';
import { listExamEvents, runAllocation } from '../../api/client';
import SearchableSelect from '../common/SearchableSelect';
import './CandidateAllocationPanel.css';

function methodLabel(method) {
  if (method === 'preference') return 'Preference match';
  if (method === 'nearest_fallback') return 'Nearest-centre fallback';
  if (method === 'manual_override') return 'Manual override';
  return 'Unallocated';
}

export default function CandidateAllocationPanel() {
  const [examEvents, setExamEvents] = useState([]);
  const [selectedExamId, setSelectedExamId] = useState('');
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [results, setResults] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    listExamEvents()
      .then((events) => {
        setExamEvents(events);
        if (events.length > 0) setSelectedExamId(events[0].id);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  async function handleRunAllocation() {
    if (!selectedExamId) return;
    setRunning(true);
    setError(null);
    setResults(null);
    try {
      const outcome = await runAllocation(selectedExamId);
      setResults(outcome);
    } catch (err) {
      setError(err.message);
    } finally {
      setRunning(false);
    }
  }

  if (loading) return <div className="panel"><p className="empty-state">Loading…</p></div>;

  return (
    <div className="panel candidate-allocation-panel">
      <p className="panel-eyebrow">Candidate Allocation</p>
      <span className="login-hint">
        Allocates all pending applications for the selected exam to centres.
      </span>

      {examEvents.length === 0 ? (
        <p className="empty-state">No exam events created yet.</p>
      ) : (
        <div className="allocation-controls">
          <SearchableSelect
            options={examEvents}
            value={selectedExamId}
            onChange={setSelectedExamId}
            getLabel={(ev) => ev.exam_name}
            getValue={(ev) => ev.id}
            placeholder="Select an exam…"
          />
          <button type="button" className="login-submit" disabled={running} onClick={handleRunAllocation}>
            {running ? 'Allocating…' : 'Run Allocation'}
          </button>
        </div>
      )}

      {error && <p className="login-error">{error}</p>}

      {results && (
        results.length === 0 ? (
          <p className="empty-state">No pending applications to allocate.</p>
        ) : (
          <table className="item-bank-table">
            <thead>
              <tr>
                <th>Candidate</th>
                <th>Centre</th>
                <th>Method</th>
                <th>Preference Rank</th>
              </tr>
            </thead>
            <tbody>
              {results.map((r) => (
                <tr key={r.user_id} className={r.centre_id ? '' : 'draft-error-row'}>
                  <td>{r.user_email}</td>
                  <td>{r.centre_code || '—'}</td>
                  <td>{methodLabel(r.method)}</td>
                  <td>{r.preference_rank ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )
      )}
    </div>
  );
}