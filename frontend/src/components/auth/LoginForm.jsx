import { useState } from 'react';
import { login } from '../../api/client';
import { getOrCreateDeviceFingerprint } from '../../utils/deviceFingerprint';
import Seal from '../common/Seal';
import ThemeToggle from '../common/ThemeToggle';
import './LoginForm.css';

export default function LoginForm({ onLoginSuccess, theme, onToggleTheme, onGoToRegister }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [deviceFingerprint] = useState(() => getOrCreateDeviceFingerprint());
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const result = await login(email, password, deviceFingerprint);
      onLoginSuccess(result.user, result.access_token);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="login-wrap">
      <div className="login-theme-toggle-wrap">
        <ThemeToggle theme={theme} onToggle={onToggleTheme} />
      </div>
      <form onSubmit={handleSubmit} className="login-card">
        <div className="login-seal-row">
          <Seal size={44} />
          <div>
            <p className="login-eyebrow">System Access</p>
            <h2 className="login-title">Pardarshi</h2>
          </div>
        </div>

        <div className="login-field">
          <label>Email</label>
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </div>
        <div className="login-field">
          <label>Password</label>
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        </div>
        <div className="login-field">
          <label>Device ID</label>
          <input type="text" value={deviceFingerprint} readOnly />
          <span className="login-hint">Generated automatically for this device. Must be admin-approved to pass sensitive actions.</span>
        </div>

        {error && <p className="login-error">{error}</p>}

        <button type="submit" disabled={loading} className="login-submit">
          {loading ? 'Authenticating…' : 'Log in'}
        </button>

        <button type="button" onClick={onGoToRegister}
          style={{
            width: '100%', marginTop: 12, padding: 10, background: 'transparent',
            border: 'none', color: 'var(--text-dim)', fontSize: 13, cursor: 'pointer'
          }}>
          Don't have an account? Register
        </button>
      </form>
    </div>
  );
}