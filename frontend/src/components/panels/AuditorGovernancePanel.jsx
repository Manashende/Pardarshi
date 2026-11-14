import { useEffect, useState } from 'react';
import { listPendingAuditors, voteToApproveAuditor } from '../../api/client';

export default function AuditorGovernancePanel() {
  const [pending, setPending] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [votingId, setVotingId] = useState(null);

  useEffect(() => {
    load();
  }, []);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const data = await listPendingAuditors();
      setPending(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleVote(userId) {
    setVotingId(userId);
    setError(null);
    try {
      await voteToApproveAuditor(userId);
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setVotingId(null);
    }
  }

  if (loading) return <p className="empty-state">Loading…</p>;

  return (
    <>
      <span className="login-hint">
        New Auditor accounts activate only once existing Auditors reach consensus here — Admin has
        no role in this decision. Each applicant needs votes from distinct Auditors to activate.
      </span>

      {error && <p className="login-error">{error}</p>}

      {pending.length === 0 ? (
        <p className="empty-state">No Auditor applications awaiting approval.</p>
      ) : (
        <table className="item-bank-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Email</th>
              <th>Votes</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {pending.map((p) => (
              <tr key={p.user_id}>
                <td>{p.full_name}</td>
                <td>{p.email}</td>
                <td>{p.votes_cast}/{p.votes_required}</td>
                <td>
                  <button
                    type="button"
                    disabled={p.already_voted_by_me || votingId === p.user_id}
                    onClick={() => handleVote(p.user_id)}
                  >
                    {p.already_voted_by_me
                      ? '✓ You approved'
                      : votingId === p.user_id
                        ? 'Voting…'
                        : 'Approve'}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  );
}