import { useState } from 'react';
import { createExamCentre } from '../../api/client';
import './ExamEventForm.css';

export default function CentreForm({ onCreated }) {
  const [centreCode, setCentreCode] = useState('');
  const [name, setName] = useState('');
  const [latitude, setLatitude] = useState('');
  const [longitude, setLongitude] = useState('');
  const [radius, setRadius] = useState(500);
  const [candidateCount, setCandidateCount] = useState(200);
  const [error, setError] = useState(null);
  const [successMessage, setSuccessMessage] = useState(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const centre = await createExamCentre({
        centre_code: centreCode,
        name,
        latitude: Number(latitude),
        longitude: Number(longitude),
        acceptable_radius_m: Number(radius),
        expected_candidate_count: Number(candidateCount),
      });
      onCreated(centre);
      setSuccessMessage(`Registered ${centre.centre_code} — ${centre.name}`);
      setCentreCode('');
      setName('');
      setLatitude('');
      setLongitude('');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="panel exam-event-form">
      <p className="panel-eyebrow">Register Exam Centre</p>

      <div className="form-row">
        <div className="form-field">
          <label>Centre Code</label>
          <input value={centreCode} onChange={(e) => setCentreCode(e.target.value)} placeholder="PUNE-042" required />
        </div>
        <div className="form-field">
          <label>Centre Name</label>
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Pune Central Centre" required />
        </div>
      </div>

      <div className="form-row form-row-quad">
        <div className="form-field">
          <label>Latitude</label>
          <input type="number" step="any" value={latitude} onChange={(e) => setLatitude(e.target.value)} required />
        </div>
        <div className="form-field">
          <label>Longitude</label>
          <input type="number" step="any" value={longitude} onChange={(e) => setLongitude(e.target.value)} required />
        </div>
        <div className="form-field">
          <label>Radius (m)</label>
          <input type="number" min={50} value={radius} onChange={(e) => setRadius(e.target.value)} required />
        </div>
        <div className="form-field">
          <label>Candidates</label>
          <input type="number" min={1} value={candidateCount} onChange={(e) => setCandidateCount(e.target.value)} required />
        </div>
      </div>

      {successMessage && <p className="form-success">{successMessage}</p>}
      {error && <p className="login-error">{error}</p>}

      <button type="submit" disabled={loading} className="login-submit">
        {loading ? 'Registering…' : 'Register Centre'}
      </button>
    </form>
  );
}