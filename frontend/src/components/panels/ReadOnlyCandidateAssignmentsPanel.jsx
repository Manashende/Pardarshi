import { useEffect, useState } from 'react';
import { listCandidateAssignments } from '../../api/client';

export default function ReadOnlyCandidateAssignmentsPanel() {
  const [assignments, setAssignments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    listCandidateAssignments()
      .then(setAssignments)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p className="empty-state">Loading…</p>;
  if (error) return <p className="login-error">{error}</p>;

  return assignments.length === 0 ? (
    <p className="empty-state">No candidates allocated yet.</p>
  ) : (
    <table className="item-bank-table">
      <thead>
        <tr>
          <th>Candidate</th>
          <th>Exam</th>
          <th>Centre</th>
        </tr>
      </thead>
      <tbody>
        {assignments.map((a) => (
          <tr key={a.id}>
            <td>{a.user_email}</td>
            <td>{a.exam_name}</td>
            <td>{a.centre_code}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}