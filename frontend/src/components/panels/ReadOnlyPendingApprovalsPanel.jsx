import { useEffect, useState } from 'react';
import { listPendingUsers, listPendingDevices } from '../../api/client';
import './PendingApprovalsPanel.css';

/**
 * Auditor's twin of PendingApprovalsPanel — same data, same endpoints,
 * but NO approve buttons at all. Not a prop toggling visibility on the
 * same component: this is a separate component that simply never
 * renders an action, so there's nothing to accidentally leave reachable.
 */
export default function ReadOnlyPendingApprovalsPanel() {
  const [pendingUsers, setPendingUsers] = useState([]);
  const [pendingDevices, setPendingDevices] = useState([]);
  const [error, setError] = useState(null);

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, 10000);
    return () => clearInterval(interval);
  }, []);

  async function refresh() {
    try {
      const [users, devices] = await Promise.all([listPendingUsers(), listPendingDevices()]);
      setPendingUsers(users);
      setPendingDevices(devices);
      setError(null);
    } catch (e) {
      setError(e.message);
    }
  }

  if (error) {
    return <div className="panel"><p className="panel-error">{error}</p></div>;
  }

  const totalPending = pendingUsers.length + pendingDevices.length;

  return (
    <div className="panel">
      <div className="flagged-header">
        <p className="panel-eyebrow" style={{ margin: 0 }}>Pending Approvals (read-only)</p>
        {totalPending > 0 && <span className="flagged-count">{totalPending}</span>}
      </div>

      {totalPending === 0 && <p className="panel-empty" style={{ marginTop: 12 }}>Nothing pending.</p>}

      {pendingUsers.length > 0 && (
        <>
          <p className="pending-subheading">Accounts</p>
          <ul className="pending-list">
            {pendingUsers.map((u) => (
              <li key={u.id} className="pending-item">
                <div>
                  <span className="pending-item-name">{u.full_name}</span>
                  <span className="pending-item-detail">{u.email} — requested {u.role}</span>
                </div>
              </li>
            ))}
          </ul>
        </>
      )}

      {pendingDevices.length > 0 && (
        <>
          <p className="pending-subheading">Devices</p>
          <ul className="pending-list">
            {pendingDevices.map((d) => (
              <li key={d.id} className="pending-item">
                <div>
                  <span className="pending-item-name">{d.fingerprint}</span>
                  <span className="pending-item-detail">user {d.user_id.slice(0, 8)}…</span>
                </div>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}