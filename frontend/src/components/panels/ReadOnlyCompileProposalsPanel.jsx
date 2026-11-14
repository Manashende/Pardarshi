import { useEffect, useState } from 'react';
import { listCompileProposals } from '../../api/client';

export default function ReadOnlyCompileProposalsPanel() {
  const [proposals, setProposals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    listCompileProposals()
      .then(setProposals)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p className="empty-state">Loading…</p>;
  if (error) return <p className="login-error">{error}</p>;

  return proposals.length === 0 ? (
    <p className="empty-state">No pending compile proposals.</p>
  ) : (
    <table className="item-bank-table">
      <thead>
        <tr>
          <th>Exam</th>
          <th>Custodians</th>
          <th>Questions/Variant</th>
        </tr>
      </thead>
      <tbody>
        {proposals.map((p) => (
          <tr key={p.exam_event_id}>
            <td>{p.exam_name}</td>
            <td>{p.custodian_user_ids.length}</td>
            <td>{p.questions_per_variant}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}