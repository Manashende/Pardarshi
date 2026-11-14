import { useEffect, useState } from 'react';
import { getMyApplications, getMyExamAssignments } from '../../api/client';
import SectionHeader from '../common/SectionHeader';
import './MyExamsPanel.css';

function formatDate(epochSeconds) {
  return new Date(epochSeconds * 1000).toLocaleString();
}

export default function MyExamsPanel({ onEnterExam }) {
  const [pending, setPending] = useState([]);
  const [allocated, setAllocated] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    load();
  }, []);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const [applications, assignments] = await Promise.all([getMyApplications(), getMyExamAssignments()]);
      const allocatedIds = new Set(assignments.map((a) => a.exam_event_id));
      setPending(applications.filter((a) => !allocatedIds.has(a.exam_event_id)));
      setAllocated(assignments);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  if (loading) return <p className="empty-state">Loading…</p>;
  if (error) return <p className="login-error">{error}</p>;

  return (
    <div className="panel my-exams-panel">
      <SectionHeader title="Awaiting Allocation" />
      {pending.length === 0 ? (
          <p className="empty-state">No applications currently awaiting allocation.</p>
        ) : (
          <table className="item-bank-table">
            <thead>
              <tr><th>Exam</th><th>Applied</th></tr>
            </thead>
            <tbody>
              {pending.map((p) => (
                <tr key={p.exam_event_id}>
                  <td>{p.exam_name}</td>
                  <td>{formatDate(p.applied_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
      )}

      <SectionHeader title="Allocated Exams" />
      {allocated.length === 0 ? (
          <p className="empty-state">No exams allocated yet.</p>
        ) : (
          <table className="item-bank-table">
            <thead>
              <tr><th>Exam</th><th>Centre</th><th>Starts</th><th>Status</th><th></th></tr>
            </thead>
            <tbody>
              {allocated.map((a) => (
                <tr key={a.exam_event_id}>
                  <td>{a.exam_name}</td>
                  <td>{a.centre_code} — {a.centre_name}</td>
                  <td>{formatDate(a.exam_start_epoch)}</td>
                  <td>
                    {a.has_submitted
                      ? 'Submitted'
                      : a.paper_delivered
                        ? 'Paper delivered — ready to begin'
                        : 'Waiting for exam window'}
                  </td>
                  <td>
                    {a.paper_delivered && !a.has_submitted && (
                      <button type="button" onClick={() => onEnterExam(a.variant_id)}>
                        Enter Exam
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
      )}
    </div>
  );
}