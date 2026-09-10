import { useState, useEffect } from 'react';
import { LocalizationProvider } from '@mui/x-date-pickers';
import { MobileDateTimePicker } from '@mui/x-date-pickers/MobileDateTimePicker';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import { renderTimeViewClock } from '@mui/x-date-pickers/timeViewRenderers';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import { createExamEvent, listExamCentres } from '../../api/client';
import './ExamEventForm.css';

function toEpoch(dateObj) {
  return dateObj ? dateObj.getTime() / 1000 : null;
}

/**
 * Reads the app's existing dark/light theme (set as a data-theme
 * attribute on <html> by useTheme.js) and mirrors it into a matching
 * MUI theme — self-contained here so no other file needs to be touched
 * to thread a theme prop through the page tree.
 */
function useMuiTheme() {
  const [mode, setMode] = useState(
    document.documentElement.getAttribute('data-theme') || 'dark'
  );

  useEffect(() => {
    const observer = new MutationObserver(() => {
      setMode(document.documentElement.getAttribute('data-theme') || 'dark');
    });
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
    return () => observer.disconnect();
  }, []);

  return createTheme({
    palette: {
      mode,
      primary: { main: '#4E9B87' }, // matches --verdigris
      background: {
        paper: mode === 'dark' ? '#1E1723' : '#FFFFFF',
        default: mode === 'dark' ? '#150F19' : '#F4F5F2',
      },
      text: {
        primary: mode === 'dark' ? '#EDE7EE' : '#241A2C',
        secondary: mode === 'dark' ? '#9C8FA6' : '#6B6473',
      },
    },
    typography: { fontFamily: "'Inter', -apple-system, sans-serif" },
    shape: { borderRadius: 6 },
  });
}

export default function ExamEventForm({ onCreated }) {
  const [examName, setExamName] = useState('');
  const [examStart, setExamStart] = useState(null);
  const [overrideWindowEnd, setOverrideWindowEnd] = useState(null);
  const [numVariants, setNumVariants] = useState(3);
  const [threshold, setThreshold] = useState(3);
  const [totalCustodians, setTotalCustodians] = useState(5);
  const [overrideThreshold, setOverrideThreshold] = useState(4);
  const [centres, setCentres] = useState([]);
  const [selectedCentreIds, setSelectedCentreIds] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const muiTheme = useMuiTheme();

  useEffect(() => {
    listExamCentres().then(setCentres).catch((e) => setError(e.message));
  }, []);

  function toggleCentre(id) {
    setSelectedCentreIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  }

  const thresholdInvalid = threshold > totalCustodians;
  const overrideThresholdInvalid = overrideThreshold <= threshold || overrideThreshold > totalCustodians;

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);

    if (!examStart || !overrideWindowEnd) {
      setError('Both exam start time and override window end are required.');
      return;
    }
    if (overrideWindowEnd <= examStart) {
      setError('Override window must end after the exam start time.');
      return;
    }
    if (thresholdInvalid) {
      setError('Threshold cannot exceed total custodians.');
      return;
    }
    if (overrideThresholdInvalid) {
      setError('Override threshold must be greater than the standard threshold and no more than total custodians.');
      return;
    }
    if (selectedCentreIds.length === 0) {
      setError('Select at least one centre.');
      return;
    }

    setLoading(true);
    try {
      const result = await createExamEvent({
        exam_name: examName,
        exam_start_epoch: toEpoch(examStart),
        override_window_end_epoch: toEpoch(overrideWindowEnd),
        num_variants: Number(numVariants),
        threshold: Number(threshold),
        total_custodians: Number(totalCustodians),
        override_threshold: Number(overrideThreshold),
        centre_ids: selectedCentreIds,
      });
      onCreated(result, Number(totalCustodians));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="panel exam-event-form">
      <p className="panel-eyebrow">Create Exam Event</p>

      <div className="form-field">
        <label>Exam Name</label>
        <input value={examName} onChange={(e) => setExamName(e.target.value)}
               placeholder="e.g. JEE-Main-2027-Jan-S1" required />
      </div>

      <ThemeProvider theme={muiTheme}>
        <LocalizationProvider dateAdapter={AdapterDateFns}>
          <div className="form-row">
            <div className="form-field">
              <label>Exam Start Time</label>
              <MobileDateTimePicker
                value={examStart}
                onChange={setExamStart}
                ampm={true}
                format="dd-MM-yyyy hh:mm a"
                viewRenderers={{
                  hours: renderTimeViewClock,
                  minutes: renderTimeViewClock,
                  seconds: renderTimeViewClock,
                }}
                slotProps={{ textField: { fullWidth: true, placeholder: 'Select date & time' } }}
              />
            </div>
            <div className="form-field">
              <label>Override Window Ends</label>
              <MobileDateTimePicker
                value={overrideWindowEnd}
                onChange={setOverrideWindowEnd}
                ampm={true}
                format="dd-MM-yyyy hh:mm a"
                viewRenderers={{
                  hours: renderTimeViewClock,
                  minutes: renderTimeViewClock,
                  seconds: renderTimeViewClock,
                }}
                minDateTime={examStart || undefined}
                slotProps={{ textField: { fullWidth: true, placeholder: 'Select date & time' } }}
              />
            </div>
          </div>
        </LocalizationProvider>
      </ThemeProvider>

      <div className="form-row form-row-quad">
        <div className="form-field">
          <label>Variants</label>
          <input type="number" min={1} value={numVariants} onChange={(e) => setNumVariants(e.target.value)} required />
        </div>
        <div className="form-field">
          <label>Threshold</label>
          <input type="number" min={2} value={threshold} onChange={(e) => setThreshold(e.target.value)} required
                 className={thresholdInvalid ? 'form-input-invalid' : ''} />
        </div>
        <div className="form-field">
          <label>Total Custodians</label>
          <input type="number" min={2} value={totalCustodians} onChange={(e) => setTotalCustodians(e.target.value)} required />
        </div>
        <div className="form-field">
          <label>Override Threshold</label>
          <input type="number" min={2} value={overrideThreshold} onChange={(e) => setOverrideThreshold(e.target.value)} required
                 className={overrideThresholdInvalid ? 'form-input-invalid' : ''} />
        </div>
      </div>

      <div className="form-field">
        <label>Centres</label>
        {centres.length === 0 && (
          <p className="login-hint">No centres registered yet — register one above first.</p>
        )}
        <div className="centre-checkbox-list">
          {centres.map((c) => (
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

      <button type="submit" disabled={loading} className="login-submit">
        {loading ? 'Creating…' : 'Create Exam Event'}
      </button>
    </form>
  );
}