import { useEffect, useState } from 'react';
import {
  listExamEvents, listVariantsForExamEvent, listVariantQuestions,
  listMyRevealRequests, requestQuestionReveal, viewRevealedIdentity,
} from '../../api/client';
import '../common/ConfirmModal.css';

export default function AllQuestionsPanel() {
  const [exams, setExams] = useState([]);
  const [selectedExamId, setSelectedExamId] = useState('');
  const [variants, setVariants] = useState([]);
  const [selectedVariantId, setSelectedVariantId] = useState('');
  const [questions, setQuestions] = useState([]);
  const [myRequests, setMyRequests] = useState([]);

  const [loadingExams, setLoadingExams] = useState(true);
  const [loadingVariants, setLoadingVariants] = useState(false);
  const [loadingQuestions, setLoadingQuestions] = useState(false);
  const [error, setError] = useState(null);

  const [reasonTarget, setReasonTarget] = useState(null); // question_id
  const [reasonInput, setReasonInput] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [modalError, setModalError] = useState(null);

  const [revealedByRequestId, setRevealedByRequestId] = useState({});
  const [viewingId, setViewingId] = useState(null);

  useEffect(() => {
    loadExams();
    refreshMyRequests();
  }, []);

  async function loadExams() {
    setLoadingExams(true);
    setError(null);
    try {
      const all = await listExamEvents();
      // Only exams that have actually been compiled have variants/questions
      // to investigate — a DRAFT exam has neither.
      const compiledOnly = all.filter((e) => e.status !== 'DRAFT');
      setExams(compiledOnly);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoadingExams(false);
    }
  }

  async function refreshMyRequests() {
    try {
      const reqs = await listMyRevealRequests();
      setMyRequests(reqs);
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleSelectExam(examId) {
    setSelectedExamId(examId);
    setSelectedVariantId('');
    setQuestions([]);
    setVariants([]);
    if (!examId) return;
    setLoadingVariants(true);
    setError(null);
    try {
      const data = await listVariantsForExamEvent(examId);
      setVariants(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoadingVariants(false);
    }
  }

  async function handleSelectVariant(variantId) {
    setSelectedVariantId(variantId);
    setQuestions([]);
    if (!variantId) return;
    setLoadingQuestions(true);
    setError(null);
    try {
      const data = await listVariantQuestions(variantId);
      setQuestions(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoadingQuestions(false);
    }
  }

  function requestForQuestion(questionId) {
    const matches = myRequests.filter((r) => r.question_id === questionId);
    if (matches.length === 0) return null;
    return matches.reduce((a, b) => (a.created_at > b.created_at ? a : b));
  }

  function openReasonModal(questionId) {
    setModalError(null);
    setReasonInput('');
    setReasonTarget(questionId);
  }

  async function handleSubmitRequest() {
    if (!reasonInput.trim()) {
      setModalError('Enter a reason for this reveal request — this is a forensic action, not routine browsing.');
      return;
    }
    setSubmitting(true);
    setModalError(null);
    try {
      await requestQuestionReveal(reasonTarget, reasonInput.trim());
      setReasonTarget(null);
      await refreshMyRequests();
    } catch (err) {
      setModalError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  async function handleViewIdentity(requestId) {
    setViewingId(requestId);
    setError(null);
    try {
      const identity = await viewRevealedIdentity(requestId);
      setRevealedByRequestId((prev) => ({ ...prev, [requestId]: identity }));
    } catch (err) {
      setError(err.message);
    } finally {
      setViewingId(null);
    }
  }

  return (
    <div className="panel all-questions-panel">
      <p className="panel-eyebrow">Item Bank — Investigate a Compiled Paper</p>
      <span className="login-hint">
        Select the exam and variant that leaked, then match its question number below. Revealing a
        contributor's identity requires Auditor approval.
      </span>

      {error && <p className="login-error">{error}</p>}

      <div className="form-row" style={{ marginTop: 14 }}>
        <div className="form-field">
          <label>Exam Event</label>
          {loadingExams ? (
            <p className="empty-state">Loading…</p>
          ) : exams.length === 0 ? (
            <p className="login-hint">No compiled exam events yet.</p>
          ) : (
            <select
              className="form-select"
              value={selectedExamId}
              onChange={(e) => handleSelectExam(e.target.value)}
            >
              <option value="">Select an exam event…</option>
              {exams.map((e) => (
                <option key={e.id} value={e.id}>{e.exam_name} ({e.status})</option>
              ))}
            </select>
          )}
        </div>

        <div className="form-field">
          <label>Variant</label>
          <select
            className="form-select"
            value={selectedVariantId}
            onChange={(e) => handleSelectVariant(e.target.value)}
            disabled={selectedExamId === '' || loadingVariants || variants.length === 0}
          >
            <option value="">
              {loadingVariants
                ? 'Loading…'
                : selectedExamId === ''
                  ? 'Select an exam event first'
                  : variants.length === 0
                    ? 'No variants found'
                    : 'Select a variant…'}
            </option>
            {variants.map((v) => (
              <option key={v.variant_id} value={v.variant_id}>
                Variant {v.variant_index + 1} — {v.num_questions} questions
              </option>
            ))}
          </select>
        </div>
      </div>

      {loadingQuestions ? (
        <p className="empty-state" style={{ marginTop: 16 }}>Loading…</p>
      ) : selectedVariantId === '' ? (
        <p className="empty-state" style={{ marginTop: 16 }}>Select a variant to see its questions.</p>
      ) : questions.length === 0 ? (
        <p className="empty-state" style={{ marginTop: 16 }}>No questions found for this variant.</p>
      ) : (
        <table className="item-bank-table" style={{ marginTop: 16 }}>
          <thead>
            <tr>
              <th>Question #</th>
              <th>Topic</th>
              <th>Type</th>
              <th>Difficulty</th>
              <th>Tags</th>
              <th>Contributor Identity</th>
            </tr>
          </thead>
          <tbody>
            {questions.map((q) => {
              const existing = requestForQuestion(q.question_id);
              const revealed = existing ? revealedByRequestId[existing.request_id] : null;
              return (
                <tr key={q.question_id}>
                  <td>Q{q.position}</td>
                  <td>{q.topic}</td>
                  <td>{q.question_type === 'single_correct' ? 'Single' : 'Multiple'}</td>
                  <td className="capitalize-cell">{q.difficulty}</td>
                  <td>{q.tags.join(', ') || '—'}</td>
                  <td>
                    {revealed ? (
                      <span className="ledger-cell-mono">
                        {revealed.contributor_name} ({revealed.contributor_email})
                      </span>
                    ) : existing && existing.is_approved ? (
                      <button
                        type="button"
                        disabled={viewingId === existing.request_id}
                        onClick={() => handleViewIdentity(existing.request_id)}
                      >
                        {viewingId === existing.request_id ? 'Loading…' : 'View Identity'}
                      </button>
                    ) : existing ? (
                      <span className="login-hint">
                        Pending — {existing.votes_cast}/{existing.votes_required} auditor votes
                      </span>
                    ) : (
                      <button type="button" onClick={() => openReasonModal(q.question_id)}>
                        Request Reveal…
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}

      {reasonTarget && (
        <div className="confirm-modal-backdrop">
          <div className="confirm-modal">
            <h3 className="confirm-modal-title">Request contributor identity reveal?</h3>
            <p className="confirm-modal-message">
              This is a forensic action — use it only for an actual leak investigation. A different,
              independent Auditor must approve this before the identity unlocks; you will not be
              able to approve your own request.
            </p>
            <textarea
              className="secret-input-field"
              placeholder="Reason (e.g. investigation reference, what leaked, why this question is a suspect)"
              value={reasonInput}
              onChange={(e) => setReasonInput(e.target.value)}
              rows={3}
              autoFocus
            />
            {modalError && <p className="login-error">{modalError}</p>}
            <div className="confirm-modal-actions">
              <button type="button" className="confirm-modal-cancel" onClick={() => setReasonTarget(null)}>
                Cancel
              </button>
              <button
                type="button"
                className="confirm-modal-confirm"
                disabled={submitting}
                onClick={handleSubmitRequest}
              >
                {submitting ? 'Submitting…' : 'Submit Request'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}