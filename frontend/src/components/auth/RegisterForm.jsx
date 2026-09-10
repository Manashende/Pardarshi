import { useState } from 'react';
import { register } from '../../api/client';
import Seal from '../common/Seal';
import './LoginForm.css';

const ROLES = ['CONTRIBUTOR', 'CUSTODIAN', 'CENTRE_OPERATOR', 'AUDITOR'];

export default function RegisterForm({ onBackToLogin }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [requestedRole, setRequestedRole] = useState('CONTRIBUTOR');
  const [error, setError] = useState(null);
  const [successMessage, setSuccessMessage] = useState(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const result = await register(email, password, fullName, requestedRole);
      setSuccessMessage(result.message);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  if (successMessage) {
    return (
      <div className="login-wrap">
        <div className="login-card">
          <div className="login-seal-row">
            <Seal size={44} />
            <div>
              <p className="login-eyebrow">Registration Submitted</p>
              <h2 className="login-title">Pardarshi</h2>
            </div>
          </div>
          <p style={{ fontSize: 14, lineHeight: 1.6, color: 'var(--text)' }}>{successMessage}</p>
          <button className="login-submit" onClick={onBackToLogin} style={{ marginTop: 8 }}>
            Back to login
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="login-wrap">
      <form onSubmit={handleSubmit} className="login-card">
        <div className="login-seal-row">
          <Seal size={44} />
          <div>
            <p className="login-eyebrow">Request Access</p>
            <h2 className="login-title">Register</h2>
          </div>
        </div>

        <div className="login-field">
          <label>Full Name</label>
          <input type="text" value={fullName} onChange={(e) => setFullName(e.target.value)} required />
        </div>
        <div className="login-field">
          <label>Email</label>
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </div>
        <div className="login-field">
          <label>Password</label>
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
                 required minLength={8} />
        </div>
        <div className="login-field">
          <label>Requested Role</label>
          <select value={requestedRole} onChange={(e) => setRequestedRole(e.target.value)}
                  style={{ width: '100%', padding: '11px 14px', background: 'var(--bg)',
                           border: '1px solid var(--border)', borderRadius: 6, color: 'var(--text)', fontSize: 14 }}>
            {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
          </select>
          <span className="login-hint">An administrator must approve your account before you can log in.</span>
        </div>

        {error && <p className="login-error">{error}</p>}

        <button type="submit" disabled={loading} className="login-submit">
          {loading ? 'Submitting…' : 'Request access'}
        </button>

        <button type="button" onClick={onBackToLogin}
                style={{ width: '100%', marginTop: 12, padding: 10, background: 'transparent',
                         border: 'none', color: 'var(--text-dim)', fontSize: 13, cursor: 'pointer' }}>
          Already have an account? Log in
        </button>
      </form>
    </div>
  );
}