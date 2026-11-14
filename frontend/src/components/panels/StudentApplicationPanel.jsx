import { useEffect, useState } from 'react';
import { listExamEvents, listExamCentres, applyForExam, getMyApplications } from '../../api/client';
import { getCurrentLocation } from '../../utils/geolocation';
import SearchableSelect from '../common/SearchableSelect';
import ConfirmModal from '../common/ConfirmModal';
import './StudentApplicationPanel.css';

const NUM_PREFERENCES = 3;

export default function StudentApplicationPanel() {
  const [examEvents, setExamEvents] = useState([]);
  const [centres, setCentres] = useState([]);
  const [appliedExamIds, setAppliedExamIds] = useState([]); // already-submitted, non-editable
  const [selectedExamId, setSelectedExamId] = useState('');
  const [preferences, setPreferences] = useState(['', '', '']);
  const [location, setLocation] = useState(null);
  const [locationError, setLocationError] = useState(null);

  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [error, setError] = useState(null);
  const [justSubmitted, setJustSubmitted] = useState(false);

  useEffect(() => {
    loadAll();
    getCurrentLocation()
      .then(setLocation)
      .catch((err) => setLocationError(err.message));
  }, []);

  async function loadAll() {
    setLoading(true);
    setError(null);
    try {
      const [events, centreList, applications] = await Promise.all([
        listExamEvents(), listExamCentres(), getMyApplications(),
      ]);
      const appliedIds = applications.map((a) => a.exam_event_id);
      setAppliedExamIds(appliedIds);
      const applicable = events.filter((ev) => !appliedIds.includes(ev.id));
      setExamEvents(applicable);
      setCentres(centreList);
      if (applicable.length > 0) setSelectedExamId(applicable[0].id);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  function handlePreferenceChange(index, centreId) {
    setPreferences((prev) => {
      const next = [...prev];
      next[index] = centreId;
      // Changing an earlier preference resets everything after it —
      // keeps the sequential fill-in-order behavior consistent instead
      // of leaving a stale later choice behind a now-locked field.
      for (let i = index + 1; i < next.length; i++) next[i] = '';
      return next;
    });
  }

  function optionsForSlot(index) {
    const chosenElsewhere = preferences.filter((p, i) => i !== index && p);
    return centres.filter((c) => !chosenElsewhere.includes(c.id));
  }

  const chosenIds = preferences.filter(Boolean);

  function handleSubmitClick(e) {
    e.preventDefault();
    setError(null);
    if (chosenIds.length === 0) {
      setError('Choose at least one preferred centre.');
      return;
    }
    setShowConfirm(true);
  }

  async function confirmSubmit() {
    setShowConfirm(false);
    setSubmitting(true);
    try {
      await applyForExam(
        selectedExamId,
        chosenIds,
        location?.latitude ?? null,
        location?.longitude ?? null,
      );
      setJustSubmitted(true);
      await loadAll();
      setPreferences(['', '', '']);
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) return <div className="panel"><p className="empty-state">Loading…</p></div>;

  return (
    <div className="panel student-application-panel">
      <p className="panel-eyebrow">Apply for an Exam</p>
      <span className="login-hint">
        Choose up to {NUM_PREFERENCES} preferred centres, most preferred first — same as JEE Main / MHT-CET.
        Once submitted, your preferences are locked and cannot be edited.
        {locationError && ' (Location unavailable — the nearest-centre fallback won\'t apply to your application if all your preferences are full.)'}
      </span>

      {justSubmitted && (
        <p className="form-success">Application submitted — see the My Exams page for status.</p>
      )}

      {examEvents.length === 0 ? (
        <p className="empty-state">
          {appliedExamIds.length > 0
            ? 'You have applied to every available exam — check My Exams for status.'
            : 'No exam events available to apply for yet.'}
        </p>
      ) : (
        <form onSubmit={handleSubmitClick} className="student-application-form">
          <div className="form-field">
            <label>Exam</label>
            <SearchableSelect
              options={examEvents}
              value={selectedExamId}
              onChange={setSelectedExamId}
              getLabel={(ev) => ev.exam_name}
              getValue={(ev) => ev.id}
              placeholder="Select an exam…"
            />
          </div>

          {[0, 1, 2].map((i) => {
            const isLocked = i > 0 && !preferences[i - 1];
            return (
              <div className="form-field" key={i}>
                <label>Preference {i + 1}{i === 0 ? ' (most preferred)' : ''}</label>
                <SearchableSelect
                  options={optionsForSlot(i)}
                  value={preferences[i]}
                  onChange={(id) => handlePreferenceChange(i, id)}
                  getLabel={(c) => `${c.centre_code} — ${c.name}`}
                  getValue={(c) => c.id}
                  placeholder={isLocked ? `Choose preference ${i} first` : '— none —'}
                  disabled={isLocked}
                />
              </div>
            );
          })}

          {error && <p className="login-error">{error}</p>}

          <button type="submit" className="login-submit" disabled={submitting}>
            {submitting ? 'Submitting…' : 'Submit Application'}
          </button>
        </form>
      )}

      {showConfirm && (
        <ConfirmModal
          title="Submit application?"
          message="Once submitted, your centre preferences are locked and cannot be changed. Double-check your choices before continuing."
          confirmLabel="Submit Application"
          onConfirm={confirmSubmit}
          onCancel={() => setShowConfirm(false)}
        />
      )}
    </div>
  );
}