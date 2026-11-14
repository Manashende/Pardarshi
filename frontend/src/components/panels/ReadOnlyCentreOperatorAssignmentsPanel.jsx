import { useEffect, useState } from 'react';
import { listCentreOperatorAssignments } from '../../api/client';

export default function ReadOnlyCentreOperatorAssignmentsPanel() {
  const [assignments, setAssignments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    listCentreOperatorAssignments()
      .then(setAssignments)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p className="empty-state">Loading…</p>;
  if (error) return <p className="login-error">{error}</p>;

  return assignments.length === 0 ? (
    <p className="empty-state">No centre-operator assignments yet.</p>
  ) : (
    <table className="item-bank-table">
      <thead>
        <tr>
          <th>Operator</th>
          <th>Centre Code</th>
          <th>Centre Name</th>
        </tr>
      </thead>
      <tbody>
        {assignments.map((a) => (
          <tr key={a.id}>
            <td>{a.user_email}</td>
            <td>{a.centre_code}</td>
            <td>{a.centre_name}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}