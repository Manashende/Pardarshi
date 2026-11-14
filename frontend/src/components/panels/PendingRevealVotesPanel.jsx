import { useEffect, useState } from 'react';
import { listPendingRevealRequests, voteToApproveReveal } from '../../api/client';

export default function PendingRevealVotesPanel() {
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
      const data = await listPendingRevealRequests();
      setPending(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleVote(requestId) {
    setVotingId(requestId);
    setError(null);
    try {
      await voteToApproveReveal(requestId);
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
        Approve requests to reveal a question's contributor. Requires a second Auditor's approval.
      </span>

      {error && <p className="login-error">{error}</p>}

      {pending.length === 0 ? (
        <p className="empty-state" style={{ marginTop: 12 }}>No reveal requests awaiting approval.</p>
      ) : (
        <table className="item-bank-table">
          <thead>
            <tr>
              <th>Question ID</th>
              <th>Reason</th>
              <th>Votes</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {pending.map((r) => (
              <tr key={r.request_id}>
                <td className="ledger-cell-mono">{r.question_id}</td>
                <td>{r.reason}</td>
                <td>{r.votes_cast}/{r.votes_required}</td>
                <td>
                  <button
                    type="button"
                    disabled={r.already_voted_by_me || votingId === r.request_id}
                    onClick={() => handleVote(r.request_id)}
                  >
                    {r.already_voted_by_me
                      ? '✓ You approved'
                      : votingId === r.request_id
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