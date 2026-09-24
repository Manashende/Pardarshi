import { useEffect, useState } from 'react';
import { submitQuestion, listMyQuestions } from '../../api/client';
import ConfirmModal from '../common/ConfirmModal';
import './QuestionForm.css';

const DIFFICULTY_OPTIONS = [
  { value: 'easy', label: 'Easy' },
  { value: 'medium', label: 'Medium' },
  { value: 'hard', label: 'Hard' },
];

const QUESTION_TYPE_OPTIONS = [
  { value: 'single_correct', label: 'Single Correct (one right answer)' },
  { value: 'multiple_correct', label: 'Multiple Correct (one or more right answers)' },
];

const DRAFTS_STORAGE_KEY = 'pardarshi_item_bank_drafts';
const MIN_OPTIONS = 2;
const MAX_OPTIONS = 6;

function emptyFormState() {
  return {
    questionType: 'single_correct',
    questionText: '',
    options: ['', ''],
    correctIndices: [],
    topic: '',
    difficulty: 'medium',
    tagsInput: '',
  };
}

function loadDraftsFromStorage() {
  try {
    const raw = localStorage.getItem(DRAFTS_STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveDraftsToStorage(drafts) {
  try {
    localStorage.setItem(DRAFTS_STORAGE_KEY, JSON.stringify(drafts));
  } catch {
    // If storage is unavailable (private browsing, quota, etc.) drafts just
    // won't survive a refresh — not fatal, so we swallow this quietly.
  }
}

function makeLocalId() {
  return `draft_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
}

/** Mirrors the backend's SubmitQuestionRequest validation so contributors get
 * instant feedback instead of a round-trip error. */
function validateDraftForm(form) {
  const errors = [];
  if (!form.questionText.trim()) errors.push('Question text cannot be blank.');

  const cleanedOptions = form.options.map((o) => o.trim());
  if (cleanedOptions.some((o) => !o)) errors.push('Options cannot be blank.');
  if (new Set(cleanedOptions).size !== cleanedOptions.length) errors.push('Options must be unique.');
  if (cleanedOptions.length < MIN_OPTIONS) errors.push(`At least ${MIN_OPTIONS} options are required.`);

  if (form.correctIndices.length === 0) errors.push('Mark at least one option as correct.');
  if (form.questionType === 'single_correct' && form.correctIndices.length > 1) {
    errors.push('Single-correct questions can only have one correct option.');
  }
  if (!form.topic.trim()) errors.push('Topic cannot be blank.');

  return errors;
}

export default function QuestionForm() {
  const [form, setForm] = useState(emptyFormState());
  const [editingId, setEditingId] = useState(null);
  const [formErrors, setFormErrors] = useState([]);

  const [drafts, setDrafts] = useState(() => loadDraftsFromStorage());

  const [submitted, setSubmitted] = useState([]);
  const [submittedLoading, setSubmittedLoading] = useState(true);
  const [submittedError, setSubmittedError] = useState(null);

  const [showConfirm, setShowConfirm] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitProgress, setSubmitProgress] = useState(null); // { done, total }
  const [draftErrors, setDraftErrors] = useState({}); // localId -> message

  useEffect(() => {
    saveDraftsToStorage(drafts);
  }, [drafts]);

  useEffect(() => {
    refreshSubmitted();
  }, []);

  async function refreshSubmitted() {
    setSubmittedLoading(true);
    setSubmittedError(null);
    try {
      const data = await listMyQuestions();
      setSubmitted(data);
    } catch (err) {
      setSubmittedError(err.message);
    } finally {
      setSubmittedLoading(false);
    }
  }

  function resetForm() {
    setForm(emptyFormState());
    setEditingId(null);
    setFormErrors([]);
  }

  function handleTypeChange(newType) {
    setForm((f) => ({
      ...f,
      questionType: newType,
      // Switching to single-correct with multiple already marked would be an
      // invalid state — trim down to the first marked option.
      correctIndices: newType === 'single_correct' ? f.correctIndices.slice(0, 1) : f.correctIndices,
    }));
  }

  function handleOptionTextChange(index, value) {
    setForm((f) => {
      const options = [...f.options];
      options[index] = value;
      return { ...f, options };
    });
  }

  function handleAddOption() {
    setForm((f) => (f.options.length >= MAX_OPTIONS ? f : { ...f, options: [...f.options, ''] }));
  }

  function handleRemoveOption(index) {
    setForm((f) => {
      if (f.options.length <= MIN_OPTIONS) return f;
      const options = f.options.filter((_, i) => i !== index);
      const correctIndices = f.correctIndices
        .filter((i) => i !== index)
        .map((i) => (i > index ? i - 1 : i));
      return { ...f, options, correctIndices };
    });
  }

  function handleToggleCorrect(index) {
    setForm((f) => {
      if (f.questionType === 'single_correct') {
        return { ...f, correctIndices: [index] };
      }
      const has = f.correctIndices.includes(index);
      return {
        ...f,
        correctIndices: has
          ? f.correctIndices.filter((i) => i !== index)
          : [...f.correctIndices, index],
      };
    });
  }

  function handleSaveDraft(e) {
    e.preventDefault();
    const errors = validateDraftForm(form);
    if (errors.length > 0) {
      setFormErrors(errors);
      return;
    }

    const cleanedDraft = {
      localId: editingId ?? makeLocalId(),
      questionType: form.questionType,
      questionText: form.questionText.trim(),
      options: form.options.map((o) => o.trim()),
      correctIndices: [...form.correctIndices].sort((a, b) => a - b),
      topic: form.topic.trim(),
      difficulty: form.difficulty,
      tags: form.tagsInput.split(',').map((t) => t.trim()).filter(Boolean),
    };

    setDrafts((prev) => {
      if (editingId) {
        return prev.map((d) => (d.localId === editingId ? cleanedDraft : d));
      }
      return [...prev, cleanedDraft];
    });

    resetForm();
  }

  function handleEditDraft(draft) {
    setForm({
      questionType: draft.questionType,
      questionText: draft.questionText,
      options: draft.options,
      correctIndices: draft.correctIndices,
      topic: draft.topic,
      difficulty: draft.difficulty,
      tagsInput: draft.tags.join(', '),
    });
    setEditingId(draft.localId);
    setFormErrors([]);
  }

  function handleDeleteDraft(localId) {
    setDrafts((prev) => prev.filter((d) => d.localId !== localId));
    if (editingId === localId) resetForm();
    setDraftErrors((prev) => {
      const next = { ...prev };
      delete next[localId];
      return next;
    });
  }

  async function handleConfirmSubmitAll() {
    setSubmitting(true);
    setShowConfirm(false);
    setDraftErrors({});

    const toSubmit = [...drafts];
    let succeededIds = [];
    const errors = {};

    for (let i = 0; i < toSubmit.length; i++) {
      const draft = toSubmit[i];
      setSubmitProgress({ done: i, total: toSubmit.length });
      try {
        await submitQuestion({
          question_type: draft.questionType,
          question_text: draft.questionText,
          options: draft.options,
          correct_option_indices: draft.correctIndices,
          topic: draft.topic,
          difficulty: draft.difficulty,
          tags: draft.tags,
        });
        succeededIds.push(draft.localId);
      } catch (err) {
        errors[draft.localId] = err.message;
      }
    }

    setSubmitProgress({ done: toSubmit.length, total: toSubmit.length });
    setDrafts((prev) => prev.filter((d) => !succeededIds.includes(d.localId)));
    setDraftErrors(errors);
    setSubmitting(false);
    setSubmitProgress(null);

    await refreshSubmitted();
  }

  function formatSubmittedAt(unixSeconds) {
    return new Date(unixSeconds * 1000).toLocaleString();
  }

  const canSubmitAll = drafts.length > 0 && !submitting;

  return (
    <div className="item-bank-workspace">
      {/* ---- Composer ---- */}
      <form onSubmit={handleSaveDraft} className="panel exam-event-form">
        <p className="panel-eyebrow">{editingId ? 'Edit Draft Question' : 'Compose Question'}</p>

        <div className="form-row">
          <div className="form-field">
            <label>Question Type</label>
            <select
              value={form.questionType}
              onChange={(e) => handleTypeChange(e.target.value)}
              className="form-select"
            >
              {QUESTION_TYPE_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          </div>
          <div className="form-field">
            <label>Difficulty</label>
            <select
              value={form.difficulty}
              onChange={(e) => setForm((f) => ({ ...f, difficulty: e.target.value }))}
              className="form-select"
            >
              {DIFFICULTY_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          </div>
        </div>

        <div className="form-field">
          <label>Question Text</label>
          <textarea
            value={form.questionText}
            onChange={(e) => setForm((f) => ({ ...f, questionText: e.target.value }))}
            placeholder="Enter the question text..."
            rows={4}
            className="form-textarea"
          />
        </div>

        <div className="form-field">
          <label>
            Options — {form.questionType === 'single_correct'
              ? 'select the one correct answer'
              : 'select all correct answers'}
          </label>
          <div className="option-list">
            {form.options.map((opt, i) => (
              <div className="option-row" key={i}>
                <input
                  type={form.questionType === 'single_correct' ? 'radio' : 'checkbox'}
                  name="correct-option"
                  checked={form.correctIndices.includes(i)}
                  onChange={() => handleToggleCorrect(i)}
                />
                <input
                  type="text"
                  value={opt}
                  onChange={(e) => handleOptionTextChange(i, e.target.value)}
                  placeholder={`Option ${i + 1}`}
                  className="option-text-input"
                />
                {form.options.length > MIN_OPTIONS && (
                  <button
                    type="button"
                    className="option-remove-btn"
                    onClick={() => handleRemoveOption(i)}
                    aria-label={`Remove option ${i + 1}`}
                  >
                    ✕
                  </button>
                )}
              </div>
            ))}
          </div>
          {form.options.length < MAX_OPTIONS && (
            <button type="button" className="option-add-btn" onClick={handleAddOption}>
              + Add option
            </button>
          )}
        </div>

        <div className="form-row">
          <div className="form-field">
            <label>Topic</label>
            <input
              value={form.topic}
              onChange={(e) => setForm((f) => ({ ...f, topic: e.target.value }))}
              placeholder="e.g. Thermodynamics"
            />
          </div>
          <div className="form-field">
            <label>Tags (comma-separated, optional)</label>
            <input
              value={form.tagsInput}
              onChange={(e) => setForm((f) => ({ ...f, tagsInput: e.target.value }))}
              placeholder="numerical, formula-based"
            />
          </div>
        </div>

        {formErrors.length > 0 && (
          <ul className="form-error-list">
            {formErrors.map((msg, i) => <li key={i}>{msg}</li>)}
          </ul>
        )}

        <div className="composer-actions">
          <button type="submit" className="login-submit">
            {editingId ? 'Update Draft' : 'Add to Draft List'}
          </button>
          {editingId && (
            <button type="button" className="confirm-modal-cancel" onClick={resetForm}>
              Cancel Edit
            </button>
          )}
        </div>
      </form>

      {/* ---- Draft list ---- */}
      <div className="panel draft-list-panel">
        <p className="panel-eyebrow">Draft Questions ({drafts.length})</p>
        <span className="login-hint">
          Nothing here is saved to the server yet — review, edit, or delete freely. Once you submit
          all drafts, they are encrypted immediately and locked forever, including for you.
        </span>

        {drafts.length === 0 ? (
          <p className="empty-state">No drafts yet — compose a question above to add one.</p>
        ) : (
          <table className="item-bank-table">
            <thead>
              <tr>
                <th>Question</th>
                <th>Type</th>
                <th>Difficulty</th>
                <th>Topic</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {drafts.map((d) => (
                <tr key={d.localId}>
                  <td className="truncate-cell">{d.questionText}</td>
                  <td>{d.questionType === 'single_correct' ? 'Single' : 'Multiple'}</td>
                  <td className="capitalize-cell">{d.difficulty}</td>
                  <td>{d.topic}</td>
                  <td className="row-actions">
                    <button type="button" onClick={() => handleEditDraft(d)}>Edit</button>
                    <button type="button" onClick={() => handleDeleteDraft(d.localId)}>Delete</button>
                  </td>
                </tr>
              ))}
              {Object.entries(draftErrors).map(([localId, msg]) => (
                <tr key={`err_${localId}`} className="draft-error-row">
                  <td colSpan={5}>Failed to submit one question: {msg}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        <button
          type="button"
          className="login-submit submit-all-btn"
          disabled={!canSubmitAll}
          onClick={() => setShowConfirm(true)}
        >
          {submitting
            ? `Submitting ${submitProgress ? submitProgress.done + 1 : 1} of ${submitProgress?.total ?? drafts.length}…`
            : `Submit All Questions (${drafts.length})`}
        </button>
      </div>

      {/* ---- Submitted (locked) list ---- */}
      <div className="panel submitted-list-panel">
        <p className="panel-eyebrow">Submitted Questions</p>
        {submittedLoading ? (
          <p className="empty-state">Loading…</p>
        ) : submittedError ? (
          <p className="login-error">{submittedError}</p>
        ) : submitted.length === 0 ? (
          <p className="empty-state">You haven't submitted any questions yet.</p>
        ) : (
          <table className="item-bank-table">
            <thead>
              <tr>
                <th>Type</th>
                <th>Difficulty</th>
                <th>Topic</th>
                <th>Tags</th>
                <th>Submitted</th>
              </tr>
            </thead>
            <tbody>
              {submitted.map((q) => (
                <tr key={q.question_id}>
                  <td>{q.question_type === 'single_correct' ? 'Single' : 'Multiple'}</td>
                  <td className="capitalize-cell">{q.difficulty}</td>
                  <td>{q.topic}</td>
                  <td>{q.tags.join(', ') || '—'}</td>
                  <td>{formatSubmittedAt(q.submitted_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {showConfirm && (
        <ConfirmModal
          title="Submit and lock these questions?"
          message={`You're about to submit ${drafts.length} question${drafts.length !== 1 ? 's' : ''}. Once submitted, each is encrypted immediately — no one, including you, will be able to view or edit them again.`}
          checkboxLabel="I have cross-checked these questions and their answers. I understand I will not be able to view or edit them again."
          requireCheckbox
          confirmLabel="Confirm and Submit"
          onConfirm={handleConfirmSubmitAll}
          onCancel={() => setShowConfirm(false)}
        />
      )}
    </div>
  );
}