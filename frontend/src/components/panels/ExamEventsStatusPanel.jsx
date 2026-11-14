import { useEffect, useState } from 'react';
import { listExamEvents, cancelExamEvent } from '../../api/client';
import EditExamEventModal from './EditExamEventModal';

function statusBadgeClass(status) {
  if (status === 'COMPILED') return 'status-badge status-badge-success';
  if (status === 'DRAFT') return 'status-badge status-badge-pending';
  if (status === 'LIVE') return 'status-badge status-badge-live';
  if (status === 'CLOSED') return 'status-badge status-badge-closed';
  if (status === 'CANCELLED') return 'status-badge status-badge-danger';
  return 'status-badge';
}

const STATUS_FILTERS = ['All', 'DRAFT', 'COMPILED', 'LIVE', 'CLOSED', 'CANCELLED'];

export default function ExamEventsStatusPanel() {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [statusFilter, setStatusFilter] = useState('All');
  const [search, setSearch] = useState('');
  const [editingEvent, setEditingEvent] = useState(null);
  const [cancellingId, setCancellingId] = useState(null);

  useEffect(() => {
    load();
  }, []);

  function load() {
    setLoading(true);
    listExamEvents()
      .then(setEvents)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }

  async function handleCancel(eventId) {
    setCancellingId(eventId);
    setError(null);
    try {
      await cancelExamEvent(eventId);
      load();
    } catch (err) {
      setError(err.message);
    } finally {
      setCancellingId(null);
    }
  }

  if (loading) return <div className="panel"><p className="empty-state">Loading…</p></div>;
  if (error) return <div className="panel"><p className="login-error">{error}</p></div>;

  const filtered = events.filter((ev) => {
    const matchesStatus = statusFilter === 'All' || ev.effective_status === statusFilter;
    const matchesSearch = ev.exam_name.toLowerCase().includes(search.toLowerCase());
    return matchesStatus && matchesSearch;
  });

  return (
    <div className="panel">
      <p className="panel-eyebrow">Exam Events</p>

      <div className="form-row" style={{ marginBottom: 16 }}>
        <div className="form-field">
          <label>Search by Name</label>
          <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search exams…" />
        </div>
        <div className="form-field">
          <label>Status</label>
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="form-select">
            {STATUS_FILTERS.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
      </div>

      {filtered.length === 0 ? (
        <p className="empty-state">No exam events match.</p>
      ) : (
        <table className="item-bank-table">
          <thead>
            <tr>
              <th>Exam</th>
              <th>Mode</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((ev) => (
              <tr key={ev.id}>
                <td>{ev.exam_name}</td>
                <td>{ev.delivery_mode}</td>
                <td><span className={statusBadgeClass(ev.effective_status)}>{ev.effective_status}</span></td>
                <td className="row-actions">
                  {ev.status === 'DRAFT' && (
                    <>
                      <button type="button" onClick={() => setEditingEvent(ev)}>Edit</button>
                      <button
                        type="button"
                        disabled={cancellingId === ev.id}
                        onClick={() => handleCancel(ev.id)}
                      >
                        {cancellingId === ev.id ? 'Cancelling…' : 'Cancel'}
                      </button>
                    </>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {editingEvent && (
        <EditExamEventModal
          event={editingEvent}
          onClose={() => setEditingEvent(null)}
          onSaved={() => { setEditingEvent(null); load(); }}
        />
      )}
    </div>
  );
}