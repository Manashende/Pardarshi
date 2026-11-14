import { useEffect, useState } from 'react';
import { listUsersByRole, listExamCentres, assignCentreOperator, listCentreOperatorAssignments } from '../../api/client';
import './CentreOperatorAssignmentPanel.css';

export default function CentreOperatorAssignmentPanel() {
  const [operators, setOperators] = useState([]);
  const [centres, setCentres] = useState([]);
  const [assignments, setAssignments] = useState([]);
  const [selectedUserId, setSelectedUserId] = useState('');
  const [selectedCentreId, setSelectedCentreId] = useState('');
  const [loading, setLoading] = useState(true);
  const [assigning, setAssigning] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    loadAll();
  }, []);

  async function loadAll() {
    setLoading(true);
    setError(null);
    try {
      const [operatorList, centreList, assignmentList] = await Promise.all([
        listUsersByRole('CENTRE_OPERATOR'),
        listExamCentres(),
        listCentreOperatorAssignments(),
      ]);
      setOperators(operatorList);
      setCentres(centreList);
      setAssignments(assignmentList);
      if (operatorList.length > 0) setSelectedUserId(operatorList[0].id);
      if (centreList.length > 0) setSelectedCentreId(centreList[0].id);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleAssign(e) {
    e.preventDefault();
    if (!selectedUserId || !selectedCentreId) return;
    setAssigning(true);
    setError(null);
    try {
      await assignCentreOperator(selectedUserId, selectedCentreId);
      const assignmentList = await listCentreOperatorAssignments();
      setAssignments(assignmentList);
    } catch (err) {
      setError(err.message);
    } finally {
      setAssigning(false);
    }
  }

  if (loading) return <div className="panel"><p className="empty-state">Loading…</p></div>;

  return (
    <div className="panel centre-operator-assignment-panel">
      <p className="panel-eyebrow">Centre Operator Assignments</p>
      <span className="login-hint">
        Assign which centre each operator can unlock exams for.
      </span>

      <form onSubmit={handleAssign} className="form-row centre-assign-form">
        <div className="form-field">
          <label>Operator</label>
          {operators.length === 0 ? (
            <p className="empty-state">No approved CENTRE_OPERATOR users yet.</p>
          ) : (
            <select value={selectedUserId} onChange={(e) => setSelectedUserId(e.target.value)} className="form-select">
              {operators.map((u) => (
                <option key={u.id} value={u.id}>{u.email}</option>
              ))}
            </select>
          )}
        </div>
        <div className="form-field">
          <label>Centre</label>
          {centres.length === 0 ? (
            <p className="empty-state">No exam centres registered yet.</p>
          ) : (
            <select value={selectedCentreId} onChange={(e) => setSelectedCentreId(e.target.value)} className="form-select">
              {centres.map((c) => (
                <option key={c.id} value={c.id}>{c.centre_code} — {c.name}</option>
              ))}
            </select>
          )}
        </div>
        <div className="form-field centre-assign-submit-field">
          <label style={{ visibility: 'hidden' }}>Assign</label>
          <button
            type="submit"
            className="login-submit"
            disabled={assigning || operators.length === 0 || centres.length === 0}
          >
            {assigning ? 'Assigning…' : 'Assign'}
          </button>
        </div>
      </form>

      {error && <p className="login-error">{error}</p>}

      {assignments.length === 0 ? (
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
      )}
    </div>
  );
}