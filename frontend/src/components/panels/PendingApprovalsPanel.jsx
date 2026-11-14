import { useEffect, useState } from 'react';
import { listPendingUsers, approveUser, listPendingDevices, approveDevice } from '../../api/client';
import './PendingApprovalsPanel.css';

export default function PendingApprovalsPanel() {
  const [pendingUsers, setPendingUsers] = useState([]);
  const [pendingDevices, setPendingDevices] = useState([]);
  const [error, setError] = useState(null);
  const [busyId, setBusyId] = useState(null);

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

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, 10000);
    return () => clearInterval(interval);
  }, []);

  async function handleApproveUser(userId) {
    setBusyId(userId);
    try {
      await approveUser(userId);
      await refresh();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusyId(null);
    }
  }

  async function handleApproveDevice(deviceId) {
    setBusyId(deviceId);
    try {
      await approveDevice(deviceId);
      await refresh();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusyId(null);
    }
  }

  if (error) {
    return <div className="panel"><p className="panel-error">{error}</p></div>;
  }

  const totalPending = pendingUsers.length + pendingDevices.length;

  return (
    <div className="panel">
      <div className="flagged-header">
        <p className="panel-eyebrow" style={{ margin: 0 }}>Pending Approvals</p>
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
                <button className="pending-approve-btn" disabled={busyId === u.id}
                        onClick={() => handleApproveUser(u.id)}>
                  {busyId === u.id ? '…' : 'Approve'}
                </button>
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
                <button className="pending-approve-btn" disabled={busyId === d.id}
                        onClick={() => handleApproveDevice(d.id)}>
                  {busyId === d.id ? '…' : 'Approve'}
                </button>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}