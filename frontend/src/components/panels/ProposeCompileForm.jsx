import { useEffect, useState } from 'react';
import { listExamEvents, listUsersByRole, proposeCompile } from '../../api/client';
import SearchableSelect from '../common/SearchableSelect';
import './ExamEventForm.css';

const CUSTODIAN_TYPES = [
  'EXAM_BOARD_REP', 'INDEPENDENT_REGULATOR', 'MAGISTRATE_OBSERVER',
  'STATE_EDU_OFFICER', 'JUDICIARY_AUDITOR',
];

export default function ProposeCompileForm() {
  const [examEvents, setExamEvents] = useState([]);
  const [ownExcludedCount, setOwnExcludedCount] = useState(0);
  const [selectedExamId, setSelectedExamId] = useState('');
  const [custodianUsers, setCustodianUsers] = useState([]);
  const [assignments, setAssignments] = useState({}); // { userId: custodianType }
  const [error, setError] = useState(null);
  const [successMessage, setSuccessMessage] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    Promise.all([listExamEvents(), listUsersByRole('CUSTODIAN')])
      .then(([events, custodians]) => {
        const draftEvents = events.filter((e) => e.status === 'DRAFT' && !e.created_by_is_self);
        const excludedCount = events.filter((e) => e.status === 'DRAFT' && e.created_by_is_self).length;
        setExamEvents(draftEvents);
        setOwnExcludedCount(excludedCount);
        if (draftEvents.length > 0) setSelectedExamId(draftEvents[0].id);
        setCustodianUsers(custodians);
      })
      .catch((e) => setError(e.message));
  }, []);

  const selectedExam = examEvents.find((e) => e.id === selectedExamId);
  const totalCustodians = selectedExam ? selectedExam.total_custodians : 0;

  function toggleCustodian(userId) {
    setAssignments((prev) => {
      const next = { ...prev };
      if (userId in next) {
        delete next[userId];
      } else {
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

    if (!selectedExamId) {
      setError('Select a DRAFT exam event to propose a compile for.');
      return;
    }
    if (countMismatch) {
      setError(`This exam event requires exactly ${totalCustodians} custodians — you've selected ${selectedCount}.`);
      return;
    }

    setLoading(true);
    try {
      await proposeCompile(selectedExamId, {
        custodian_user_ids: Object.keys(assignments),
        custodian_types: Object.values(assignments),
      });
      setSuccessMessage('Proposal submitted — a different admin must confirm it from Compile Queue.');
      setAssignments({});
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="panel exam-event-form">
      <p className="panel-eyebrow">Propose Compile</p>
      <span className="login-hint">
        Proposing only selects custodians — a different admin must confirm before anything compiles.
      </span>
      {ownExcludedCount > 0 && (
        <span className="login-hint">
          {ownExcludedCount} of your own exam event(s) aren't listed — another admin must propose those.
        </span>
      )}

      <div className="form-field" style={{ marginTop: 14 }}>
        <label>Exam Event (DRAFT only)</label>
        {examEvents.length === 0 ? (
          <p className="login-hint">No draft exams available.</p>
        ) : (
          <SearchableSelect
            options={examEvents}
            value={selectedExamId}
            onChange={setSelectedExamId}
            getLabel={(ev) => ev.exam_name}
            getValue={(ev) => ev.id}
            placeholder="Select an exam event…"
          />
        )}
      </div>

      {selectedExam && (
        <p className="login-hint">
          Questions per variant: <strong>{selectedExam.questions_per_variant}</strong> (set by the exam's creator)
        </p>
      )}

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

      <button type="submit" disabled={loading || countMismatch || !selectedExamId} className="login-submit">
        {loading ? 'Submitting…' : 'Submit Proposal'}
      </button>
    </form>
  );
}