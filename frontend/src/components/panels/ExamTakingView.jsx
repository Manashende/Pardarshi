import { useEffect, useMemo, useState } from 'react';
import { getMyPaper, submitExamAnswers } from '../../api/client';
import ConfirmModal from '../common/ConfirmModal';
import './ExamTakingView.css';

function formatTimeRemaining(seconds) {
  if (seconds <= 0) return '00:00:00';
  const hrs = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);
  return [hrs, mins, secs].map((n) => String(n).padStart(2, '0')).join(':');
}

export default function ExamTakingView({ variantId, onExit }) {
  const [paper, setPaper] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [answers, setAnswers] = useState({}); // question_id -> array of selected indices
  const [currentIndex, setCurrentIndex] = useState(0);
  const [nowTick, setNowTick] = useState(() => Date.now());

  const [showConfirm, setShowConfirm] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [submitError, setSubmitError] = useState(null);

  useEffect(() => {
    load();
  }, [variantId]);

  useEffect(() => {
    const interval = setInterval(() => setNowTick(Date.now()), 1000);
    return () => clearInterval(interval);
  }, []);

  // Real browser fullscreen for the whole time this view is mounted — same
  // idea as JEE/NEET-style exam software: keeps the browser chrome and
  // this app's own TopBar/sidebar out of view to discourage tab-switching
  // during a timed exam. Best-effort: some browsers block requestFullscreen
  // without a direct user gesture, or a user can press Esc to leave it
  // early — either way the CSS full-viewport overlay below still covers
  // the app's own chrome regardless, so the exam stays usable either way.
  useEffect(() => {
    const el = document.documentElement;
    if (el.requestFullscreen) {
      el.requestFullscreen().catch(() => {
        // Blocked by browser policy or lack of a user gesture — non-fatal.
      });
    }
    return () => {
      if (document.fullscreenElement) {
        document.exitFullscreen().catch(() => {});
      }
    };
  }, []);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const data = await getMyPaper(variantId);
      setPaper(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  const remainingSeconds = paper ? paper.exam_end_epoch - nowTick / 1000 : null;

  // Auto-submit the instant time runs out — matches real exam behavior:
  // whatever is answered gets submitted, no further input accepted.
  useEffect(() => {
    if (paper && remainingSeconds !== null && remainingSeconds <= 0 && !submitted && !submitting) {
      doSubmit();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [remainingSeconds, paper, submitted, submitting]);

  function selectOption(question, optionIndex) {
    setAnswers((prev) => {
      const current = prev[question.question_id] || [];
      if (question.question_type === 'single_correct') {
        return { ...prev, [question.question_id]: [optionIndex] };
      }
      const has = current.includes(optionIndex);
      return {
        ...prev,
        [question.question_id]: has
          ? current.filter((i) => i !== optionIndex)
          : [...current, optionIndex],
      };
    });
  }

  async function doSubmit() {
    setSubmitting(true);
    setSubmitError(null);
    try {
      await submitExamAnswers(variantId, answers);
      setSubmitted(true);
    } catch (err) {
      setSubmitError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  function handleSubmitClick() {
    setShowConfirm(true);
  }

  function confirmSubmit() {
    setShowConfirm(false);
    doSubmit();
  }

  const answeredCount = useMemo(
    () => (paper ? paper.questions.filter((q) => (answers[q.question_id] || []).length > 0).length : 0),
    [answers, paper]
  );

  if (loading) {
    return (
      <div className="exam-taking-view exam-taking-view-centered">
        <p className="empty-state">Loading exam paper…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="exam-taking-view exam-taking-view-centered">
        <div className="panel">
          <p className="login-error">{error}</p>
          <button type="button" className="login-submit" onClick={onExit}>Back to My Exams</button>
        </div>
      </div>
    );
  }

  if (submitted) {
    return (
      <div className="exam-taking-view exam-taking-view-centered">
        <div className="panel exam-submitted-panel">
          <p className="panel-eyebrow">Submitted</p>
          <p className="login-hint">Your answers have been recorded. You cannot make further changes.</p>
          <button type="button" className="login-submit" onClick={onExit}>Back to My Exams</button>
        </div>
      </div>
    );
  }

  const currentQuestion = paper.questions[currentIndex];
  const currentAnswer = answers[currentQuestion.question_id] || [];

  return (
    <div className="exam-taking-view">
      <div className="exam-taking-inner">
        <div className="exam-header">
          <div className="exam-header-status">
            <span className="exam-progress">
              {answeredCount}/{paper.questions.length} answered
            </span>
            <span className={`exam-timer ${remainingSeconds < 300 ? 'exam-timer-low' : ''}`}>
              {formatTimeRemaining(remainingSeconds)}
            </span>
          </div>
          <button type="button" className="login-submit exam-submit-btn" disabled={submitting} onClick={handleSubmitClick}>
            {submitting ? 'Submitting…' : 'Submit Exam'}
          </button>
        </div>

        {submitError && <p className="login-error exam-submit-error">{submitError}</p>}

        <div className="exam-body">
          <div className="exam-question-nav">
            {paper.questions.map((q, i) => {
              const isAnswered = (answers[q.question_id] || []).length > 0;
              return (
                <button
                  type="button"
                  key={q.question_id}
                  className={[
                    'exam-nav-btn',
                    i === currentIndex ? 'exam-nav-btn-current' : '',
                    isAnswered ? 'exam-nav-btn-answered' : '',
                  ].join(' ').trim()}
                  onClick={() => setCurrentIndex(i)}
                >
                  {i + 1}
                </button>
              );
            })}
          </div>

          <div className="exam-question-panel panel">
            <p className="login-hint">Question {currentIndex + 1} of {paper.questions.length}</p>
            <p className="exam-question-text">{currentQuestion.question_text}</p>

            <div className="exam-options">
              {currentQuestion.options.map((opt, i) => (
                <label className="exam-option-row" key={i}>
                  <input
                    type={currentQuestion.question_type === 'single_correct' ? 'radio' : 'checkbox'}
                    name={`q-${currentQuestion.question_id}`}
                    checked={currentAnswer.includes(i)}
                    onChange={() => selectOption(currentQuestion, i)}
                  />
                  <span>{opt}</span>
                </label>
              ))}
            </div>

            <div className="exam-nav-actions">
              <button
                type="button"
                disabled={currentIndex === 0}
                onClick={() => setCurrentIndex((i) => Math.max(0, i - 1))}
              >
                Previous
              </button>
              <button
                type="button"
                disabled={currentIndex === paper.questions.length - 1}
                onClick={() => setCurrentIndex((i) => Math.min(paper.questions.length - 1, i + 1))}
              >
                Next
              </button>
            </div>
          </div>
        </div>

      </div>

      {showConfirm && (
        <ConfirmModal
          title="Submit exam?"
          message={`You have answered ${answeredCount} of ${paper.questions.length} questions. Once submitted, you cannot make further changes.`}
          confirmLabel="Submit Exam"
          onConfirm={confirmSubmit}
          onCancel={() => setShowConfirm(false)}
        />
      )}
    </div>
  );
}