import { useEffect, useState } from 'react';
import { verifyLedger } from '../../api/client';
import Seal from '../common/Seal';
import './LedgerIntegrityBadge.css';

export default function LedgerIntegrityBadge() {
  const [status, setStatus] = useState(null);
  const [entriesChecked, setEntriesChecked] = useState(0);
  const [error, setError] = useState(null);

  async function check() {
    try {
      const result = await verifyLedger();
      setStatus(result.chain_intact);
      setEntriesChecked(result.entries_checked);
      setError(null);
    } catch (e) {
      setError(e.message);
    }
  }

  useEffect(() => {
    check();
    const interval = setInterval(check, 15000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className={`ledger-badge ${status === false ? 'ledger-badge-broken' : ''}`}>
      <Seal size={18} active={status !== false} />
      <span className="ledger-badge-label">Audit Chain:</span>
      {status === null && !error && <span className="ledger-badge-status">Verifying…</span>}
      {error && <span className="ledger-badge-status ledger-badge-error">{error}</span>}
      {status === true && <span className="ledger-badge-status">Intact — {entriesChecked} entries</span>}
      {status === false && <span className="ledger-badge-status ledger-badge-error">TAMPERED — investigate immediately</span>}
    </div>
  );
}