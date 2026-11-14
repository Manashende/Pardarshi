import { useEffect, useRef, useState } from 'react';
import { registerDevice } from '../../api/client';
import { getOrCreateDeviceFingerprint } from '../../utils/deviceFingerprint';
import './DeviceRegistration.css';

const POLL_INTERVAL_MS = 5000;

/**
 * registerDevice() is idempotent on the backend — calling it again for an
 * already-registered fingerprint just returns its current status instead
 * of erroring. That means this same call doubles as a "check my device
 * status" request, so no separate status endpoint is needed. Polling
 * every few seconds while pending means an admin approving your device
 * shows up here without a manual page refresh.
 */
export default function DeviceRegistration() {
  const [fingerprint] = useState(() => getOrCreateDeviceFingerprint());
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // React 18 StrictMode intentionally double-invokes effects in
  // development to surface impure-effect bugs. Without this guard, that
  // would fire two register calls back-to-back on mount. This only
  // prevents the double call from THIS component instance — the real,
  // permanent fix is the backend-level uniqueness constraint (see the
  // migration), since any race between independent requests could still
  // create duplicate rows without it.
  const hasCheckedRef = useRef(false);

  useEffect(() => {
    if (hasCheckedRef.current) return;
    hasCheckedRef.current = true;
    checkOrRegister();

    const interval = setInterval(() => {
      // Stop polling once approved — no need to keep hitting the endpoint.
      setStatus((current) => {
        if (current?.is_active) {
          clearInterval(interval);
          return current;
        }
        checkOrRegister();
        return current;
      });
    }, POLL_INTERVAL_MS);

    return () => clearInterval(interval);
  }, []);

  async function checkOrRegister() {
    setError(null);
    try {
      const result = await registerDevice(fingerprint);
      setStatus(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="panel device-registration-panel">
      <p className="panel-eyebrow">This Device</p>
      <p className="login-hint">
        Sensitive actions (like submitting a share) only work from a device an admin has approved.
        This device's ID is generated once and reused automatically — nothing to type or manage.
      </p>
      <div className="device-fingerprint-row">
        <code className="device-fingerprint-value">{fingerprint}</code>
        {loading ? (
          <span className="device-status-pending">Checking…</span>
        ) : error ? (
          <span className="login-error">{error}</span>
        ) : status?.is_active ? (
          <span className="device-status-approved">Approved</span>
        ) : (
          <span className="device-status-pending">Pending admin approval — checking automatically</span>
        )}
      </div>
    </div>
  );
}