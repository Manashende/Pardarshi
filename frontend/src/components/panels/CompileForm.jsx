import { useEffect, useState } from 'react';
import { listUsersByRole, compileExamEvent } from '../../api/client';
import './ExamEventForm.css';

const CUSTODIAN_TYPES = [
  'EXAM_BOARD_REP', 'INDEPENDENT_REGULATOR', 'MAGISTRATE_OBSERVER',
  'STATE_EDU_OFFICER', 'JUDICIARY_AUDITOR',
];

export default function CompileForm({ examEventId, totalCustodians, assignmentSecret, onCompiled }) {
  const [custodianUsers, setCustodianUsers] = useState([]);
  const [assignments, setAssignments] = useState({}); // { userId: custodianType }
  const [questionsPerVariant, setQuestionsPerVariant] = useState(5);
  const [examDate, setExamDate] = useState('');
  const [error, setError] = useState(null);
  const [successMessage, setSuccessMessage] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    listUsersByRole('CUSTODIAN').then(setCustodianUsers).catch((e) => setError(e.message));
  }, []);

  function toggleCustodian(userId) {
    setAssignments((prev) => {
      const next = { ...prev };
      if (userId in next) {
        delete next[userId];
      } else {
        // default to the next unused custodian type, cycling if more
        // custodians are selected than distinct types exist
        const usedTypes = Object.values(next);
        const nextType = CUSTODIAN_TYPES.find((t) => !usedTypes.includes(t)) || CUSTODIAN_TYPES[0];
        next[userId] = nextType;
      }
      return next;
    });
  }

  function setCustodianType(userId, type) {
    setAssignments((prev) => ({ ...prev, [userId]: type }));
  }

  const selectedCount = Object.keys(assignments).length;
  const countMismatch = selectedCount !== Number(totalCustodians);

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    setSuccessMessage(null);

    if (countMismatch) {
      setError(`This exam event requires exactly ${totalCustodians} custodians — you've selected ${selectedCount}.`);
      return;
    }

    setLoading(true);
    try {
      const result = await compileExamEvent(examEventId, {
        questions_per_variant: Number(questionsPerVariant),
        custodian_user_ids: Object.keys(assignments),
        custodian_types: Object.values(assignments),
        assignment_secret: assignmentSecret,
        exam_date: examDate,
      });
      setSuccessMessage(`Compiled successfully — ${result.variants.length} variant(s), ${result.assignments_created} centre assignment(s). Questions were auto-selected and assembled server-side; no one, including you, viewed the assembled paper.`);
      onCompiled(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="panel exam-event-form">
      <p className="panel-eyebrow">Compile Exam Event</p>

      <div className="form-field">
        <label>Questions per Variant</label>
        <input
          type="number"
          min={1}
          value={questionsPerVariant}
          onChange={(e) => setQuestionsPerVariant(e.target.value)}
          required
        />
        <span className="login-hint">
          Automatically selected from the encrypted item bank and assembled server-side — no
          human, including you, views the compiled paper at any point.
        </span>
      </div>

      <div className="form-field">
        <label>Exam Date</label>
        <input value={examDate} onChange={(e) => setExamDate(e.target.value)}
               placeholder="2027-01-15" required />
        <span className="login-hint">Used for deterministic variant-to-centre assignment (Algorithm E).</span>
      </div>

      <div className="form-field">
        <label>Assign Custodians ({selectedCount} / {totalCustodians} selected)</label>
        {custodianUsers.length === 0 && (
          <p className="login-hint">No approved custodian accounts found.</p>
        )}
        <div className="centre-checkbox-list">
          {custodianUsers.map((u) => (
            <div key={u.id} className="custodian-row">
              <label className="centre-checkbox-item">
                <input
                  type="checkbox"
                  checked={u.id in assignments}
                  onChange={() => toggleCustodian(u.id)}
                />
                <span>{u.full_name} ({u.email})</span>
              </label>
              {u.id in assignments && (
                <select
                  value={assignments[u.id]}
                  onChange={(e) => setCustodianType(u.id, e.target.value)}
                  className="custodian-type-select"
                >
                  {CUSTODIAN_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
                </select>
              )}
            </div>
          ))}
        </div>
        {countMismatch && selectedCount > 0 && (
          <p className="login-hint" style={{ color: 'var(--sindoor)' }}>
            Need exactly {totalCustodians}, currently have {selectedCount}.
          </p>
        )}
      </div>

      {error && <p className="login-error">{error}</p>}
      {successMessage && <p className="form-success">{successMessage}</p>}

      <button type="submit" disabled={loading || countMismatch} className="login-submit">
        {loading ? 'Compiling…' : 'Compile Exam Event'}
      </button>
    </form>
  );
}