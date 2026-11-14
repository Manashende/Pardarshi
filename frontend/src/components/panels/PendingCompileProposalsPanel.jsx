import { useEffect, useState } from 'react';
import { listCompileProposals, confirmCompile } from '../../api/client';
import '../common/ConfirmModal.css';
import './PendingCompileProposalsPanel.css';

const SECRET_STORAGE_PREFIX = 'pardarshi_assignment_secret_';

function getSavedSecret(examEventId) {
  try {
    return localStorage.getItem(SECRET_STORAGE_PREFIX + examEventId) || '';
  } catch {
    return '';
  }
}

export default function PendingCompileProposalsPanel() {
  const [proposals, setProposals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [confirmTarget, setConfirmTarget] = useState(null); // exam_event_id
  const [secretInput, setSecretInput] = useState('');
  const [autoFilled, setAutoFilled] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [modalError, setModalError] = useState(null);

  useEffect(() => {
    refresh();
  }, []);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      const data = await listCompileProposals();
      setProposals(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  function openConfirm(examEventId) {
    setModalError(null);
    const saved = getSavedSecret(examEventId);
    setSecretInput(saved);
    setAutoFilled(!!saved);
    setConfirmTarget(examEventId);
  }

  async function handleConfirm() {
    if (!secretInput.trim()) {
      setModalError('Enter the assignment secret to confirm.');
      return;
    }
    setConfirming(true);
    setModalError(null);
    try {
      await confirmCompile(confirmTarget, secretInput.trim());
      setConfirmTarget(null);
      await refresh();
    } catch (err) {
      setModalError(err.message);
    } finally {
      setConfirming(false);
    }
  }

  if (loading) return <div className="panel"><p className="empty-state">Loading…</p></div>;

  return (
    <div className="panel pending-compile-proposals-panel">
      <div className="flagged-header">
        <p className="panel-eyebrow" style={{ margin: 0 }}>Pending Compile Proposals</p>
        {proposals.length > 0 && <span className="flagged-count">{proposals.length}</span>}
      </div>
      <span className="login-hint">
        A different admin must confirm each proposal — you can't confirm your own.
      </span>

      {error && <p className="login-error">{error}</p>}

      {proposals.length === 0 ? (
        <p className="empty-state" style={{ marginTop: 12 }}>No pending compile proposals.</p>
      ) : (
        <table className="item-bank-table">
          <thead>
            <tr>
              <th>Exam</th>
              <th>Custodians</th>
              <th>Questions/Variant</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {proposals.map((p) => (
              <tr key={p.exam_event_id}>
                <td>{p.exam_name}</td>
                <td>{p.custodian_user_ids.length}</td>
                <td>{p.questions_per_variant}</td>
                <td>
                  {p.is_own_proposal ? (
                    <span className="login-hint">Awaiting a different admin</span>
                  ) : (
                    <button type="button" onClick={() => openConfirm(p.exam_event_id)}>
                      Confirm…
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {confirmTarget && (
        <div className="confirm-modal-backdrop">
          <div className="confirm-modal">
            <h3 className="confirm-modal-title">Confirm compile?</h3>
            <p className="confirm-modal-message">
              Enter the assignment secret to confirm and execute this compile. This will encrypt
              the paper, split shares among the proposed custodians, and assign variants to
              centres — it cannot be undone.
            </p>
            <input
              type="text"
              className="secret-input-field"
              placeholder="Assignment secret (hex)"
              value={secretInput}
              onChange={(e) => { setSecretInput(e.target.value); setAutoFilled(false); }}
              autoFocus
            />
            {autoFilled && (
              <p className="login-hint" style={{ marginTop: -6, marginBottom: 12 }}>
                Auto-filled from this browser's saved secret for this exam.
              </p>
            )}
            {modalError && <p className="login-error">{modalError}</p>}
            <div className="confirm-modal-actions">
              <button type="button" className="confirm-modal-cancel" onClick={() => setConfirmTarget(null)}>
                Cancel
              </button>
              <button
                type="button"
                className="confirm-modal-confirm"
                disabled={confirming}
                onClick={handleConfirm}
              >
                {confirming ? 'Confirming…' : 'Confirm Compile'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}