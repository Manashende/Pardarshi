import { useState, useEffect } from 'react';
import { editExamEvent, listExamCentres } from '../../api/client';
import '../common/ConfirmModal.css';

const DELIVERY_OPTIONS = [
  { value: 'CBT', label: 'CBT — Computer-Based Test' },
  { value: 'PRINT', label: 'PRINT — Traditional offline exam' },
];

function toDatetimeLocal(epoch) {
  const d = new Date(epoch * 1000);
  const pad = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function fromDatetimeLocal(value) {
  return new Date(value).getTime() / 1000;
}

export default function EditExamEventModal({ event, onClose, onSaved }) {
  const [examName, setExamName] = useState(event.exam_name);
  const [deliveryMode, setDeliveryMode] = useState(event.delivery_mode);
  const [examStart, setExamStart] = useState(toDatetimeLocal(event.exam_start_epoch));
  const [overrideWindowEnd, setOverrideWindowEnd] = useState(toDatetimeLocal(event.override_window_end_epoch));
  const [numVariants, setNumVariants] = useState(event.num_variants);
  const [questionsPerVariant, setQuestionsPerVariant] = useState(event.questions_per_variant);
  const [examDurationMinutes, setExamDurationMinutes] = useState(event.exam_duration_minutes);
  const [threshold, setThreshold] = useState(event.threshold);
  const [totalCustodians, setTotalCustodians] = useState(event.total_custodians);
  const [overrideThreshold, setOverrideThreshold] = useState(event.override_threshold);
  const [printWindowHours, setPrintWindowHours] = useState(event.print_window_hours);
  const [requiredOfficialsCount, setRequiredOfficialsCount] = useState(event.required_officials_count);
  const [selectedCentreIds, setSelectedCentreIds] = useState(event.centre_ids || []);
  const [centres, setCentres] = useState([]);
  const [centresError, setCentresError] = useState(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  const isPrintMode = deliveryMode === 'PRINT';

  // A CBT-only centre stores 0 printers and can't run a PRINT exam, so
  // PRINT mode only offers centres that have at least one.
  const availableCentres = isPrintMode ? centres.filter((c) => c.num_printers >= 1) : centres;
  const hiddenCentreCount = centres.length - availableCentres.length;

  // Switching to PRINT unticks any selected centre that has no printers.
  useEffect(() => {
    if (!isPrintMode || centres.length === 0) return;
    setSelectedCentreIds((prev) =>
      prev.filter((id) => (centres.find((c) => c.id === id)?.num_printers ?? 0) >= 1)
    );
  }, [isPrintMode, centres]);

  useEffect(() => {
    listExamCentres().then(setCentres).catch((e) => setCentresError(e.message));
  }, []);

  function toggleCentre(id) {
    setSelectedCentreIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  }

  async function handleSave() {
    setError(null);

    if (!examStart || !overrideWindowEnd) {
      setError('Both exam start time and the standard threshold deadline are required.');
      return;
    }
    if (fromDatetimeLocal(overrideWindowEnd) <= fromDatetimeLocal(examStart)) {
      setError('The standard threshold deadline must be after the exam start time.');
      return;
    }
    if (Number(threshold) > Number(totalCustodians)) {
      setError('Threshold cannot exceed total custodians.');
      return;
    }
    if (Number(overrideThreshold) <= Number(threshold) || Number(overrideThreshold) > Number(totalCustodians)) {
      setError('Override threshold must be greater than the standard threshold and no more than total custodians.');
      return;
    }
    if (selectedCentreIds.length === 0) {
      setError('Select at least one centre.');
      return;
    }
    if (isPrintMode && Number(requiredOfficialsCount) < 2) {
      setError('Required On-Site Officials must be at least 2 — one official confirming their own presence provides no real accountability.');
      return;
    }

    setSaving(true);
    try {
      await editExamEvent(event.id, {
        exam_name: examName,
        exam_start_epoch: fromDatetimeLocal(examStart),
        override_window_end_epoch: fromDatetimeLocal(overrideWindowEnd),
        num_variants: Number(numVariants),
        questions_per_variant: Number(questionsPerVariant),
        exam_duration_minutes: Number(examDurationMinutes),
        centre_ids: selectedCentreIds,
        threshold: Number(threshold),
        total_custodians: Number(totalCustodians),
        override_threshold: Number(overrideThreshold),
        delivery_mode: deliveryMode,
        print_window_hours: isPrintMode ? Number(printWindowHours) : 2,
        required_officials_count: isPrintMode ? Number(requiredOfficialsCount) : 2,
      });
      onSaved();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="confirm-modal-backdrop">
      <div className="confirm-modal">
        <h3 className="confirm-modal-title">Edit Exam Event</h3>

        <div className="form-field">
          <label>Exam Name</label>
          <input value={examName} onChange={(e) => setExamName(e.target.value)} />
        </div>

        <div className="form-field">
          <label>Delivery Mode</label>
          <select value={deliveryMode} onChange={(e) => setDeliveryMode(e.target.value)} className="form-select">
            {DELIVERY_OPTIONS.map((opt) => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
          </select>
        </div>

        <div className="form-row">
          <div className="form-field">
            <label>Exam Start Time</label>
            <input type="datetime-local" value={examStart} onChange={(e) => setExamStart(e.target.value)} />
          </div>
          <div className="form-field">
            <label>Standard Threshold Deadline</label>
            <input type="datetime-local" value={overrideWindowEnd} onChange={(e) => setOverrideWindowEnd(e.target.value)} />
          </div>
        </div>

        <div className="form-row">
          <div className="form-field">
            <label>Variants</label>
            <input type="number" min={1} value={numVariants} onChange={(e) => setNumVariants(e.target.value)} />
          </div>
                  <div className="form-field">
          <label>Questions per Variant</label>
          <input type="number" min={1} value={questionsPerVariant} onChange={(e) => setQuestionsPerVariant(e.target.value)} />
          </div>
          <div className="form-field">
            <label>Exam Duration (minutes)</label>
            <input type="number" min={1} value={examDurationMinutes} onChange={(e) => setExamDurationMinutes(e.target.value)} />
          </div>
        </div>

        <div className="form-row">
          <div className="form-field">
            <label>Threshold</label>
            <input type="number" min={2} value={threshold} onChange={(e) => setThreshold(e.target.value)} />
          </div>
          <div className="form-field">
            <label>Total Custodians</label>
            <input type="number" min={2} value={totalCustodians} onChange={(e) => setTotalCustodians(e.target.value)} />
          </div>
          <div className="form-field">
            <label>Override Threshold</label>
            <input type="number" min={2} value={overrideThreshold} onChange={(e) => setOverrideThreshold(e.target.value)} />
          </div>
        </div>

        {isPrintMode && (
          <div className="form-row">
            <div className="form-field">
              <label>Print Window (hours)</label>
              <input type="number" min={0} step="0.5" value={printWindowHours} onChange={(e) => setPrintWindowHours(e.target.value)} />
            </div>
            <div className="form-field">
              <label>Required On-Site Officials</label>
              <input type="number" min={2} value={requiredOfficialsCount} onChange={(e) => setRequiredOfficialsCount(e.target.value)} />
            </div>
          </div>
        )}

        <div className="form-field">
          <label>Centres</label>
          {hiddenCentreCount > 0 && (
            <p className="login-hint">
              {hiddenCentreCount} centre{hiddenCentreCount === 1 ? '' : 's'} hidden — no printers registered, so PRINT exams can't run there.
            </p>
          )}
          {centresError && (
            <p className="login-error">
              Couldn't load centres ({centresError}). Saving will keep this exam's currently selected centres.
            </p>
          )}
          <div className="centre-checkbox-list">
            {availableCentres.map((c) => (
              <label key={c.id} className="centre-checkbox-item">
                <input
                  type="checkbox"
                  checked={selectedCentreIds.includes(c.id)}
                  onChange={() => toggleCentre(c.id)}
                />
                <span>{c.centre_code} — {c.name}</span>
              </label>
            ))}
          </div>
        </div>

        {error && <p className="login-error">{error}</p>}

        <div className="confirm-modal-actions">
          <button type="button" className="confirm-modal-cancel" onClick={onClose}>Cancel</button>
          <button type="button" className="confirm-modal-confirm" disabled={saving} onClick={handleSave}>
            {saving ? 'Saving…' : 'Save Changes'}
          </button>
        </div>
      </div>
    </div>
  );
}